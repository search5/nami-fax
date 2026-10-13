import hashlib
import os
import re
import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from namifax.common import settings
from namifax.db.repository import MDBOData
from namifax.common.passwords import hash_password, needs_rehash, verify_password
from namifax.services import hylafax_users
from namifax.services.user_passwords import NFUserPasswords




def genpasswd(length: int = 8) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def md5_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


class NFUserAccount:
    """Core User Account Domain Service managing user profiles, authentication, authorization, and password policies.

    ``db`` is a SQLAlchemy ``Session`` (portable across SQLite, MySQL, MariaDB and PostgreSQL) or the legacy
    ``Any``.
    """

    def __init__(
        self,
        db: Any = None,
        user_passwords: Optional[NFUserPasswords] = None,
    ) -> None:
        self.db = db
        self.userpasswords = user_passwords or NFUserPasswords(db=self.db)
        self.useraccount = MDBOData("UserAccount", db=self.db)

        self.uid: Optional[int] = None
        self.dbdata: Dict[str, Any] = {}
        self.error: Optional[str] = None
        self.logged_in: bool = False
        self.admin_logged_in: bool = False
        self.pwdexpired: bool = False

    def init_db(self) -> None:
        self.useraccount = MDBOData("UserAccount", db=self.db)
        if self.uid:
            self.load(self.uid)

    def get_error(self) -> Optional[str]:
        return self.error

    def get_uid(self) -> Optional[int]:
        return self.uid

    def is_expired(self) -> bool:
        return self.pwdexpired

    def check_login(self) -> bool:
        return self.logged_in

    def check_admin_login(self) -> bool:
        return self.admin_logged_in

    def get_allvalues(self) -> Dict[str, Any]:
        return dict(self.dbdata)

    def load_vals(self, data: Dict[str, Any]) -> None:
        self.dbdata.update(data)
        if "uid" in self.dbdata and self.dbdata["uid"] is not None:
            self.uid = int(self.dbdata["uid"])

    def create(self, details: Dict[str, Any]) -> bool:
        self.load_vals(details)

        username = str(self.dbdata.get("username", "")).strip()
        if not username or not re.match(r"^[\.\w]+$", username):
            self.error = "Invalid username format. Only letters, numbers, dot and underscore allowed."
            return False

        email = str(self.dbdata.get("email", "")).strip()
        if not email:
            self.error = "Email address required"
            return False

        # Check existing username
        existing_user = self.useraccount.find({"username": username})
        if existing_user:
            self.error = "Username already in use"
            return False

        # Check existing email
        existing_email = self.useraccount.find({"email": email})
        if existing_email:
            self.error = "Email already in use"
            return False

        # Password handling
        raw_pwd = self.dbdata.get("password")
        self.generated_password: Optional[str] = None
        if not raw_pwd:
            pwdxemail = genpasswd()
            self.generated_password = pwdxemail                # (the caller mails it; it is never stored in clear)
            self.dbdata["password"] = hash_password(pwdxemail)
            self.dbdata["wasreset"] = 1
        else:
            pwdxemail = str(raw_pwd)
            self.dbdata["password"] = hash_password(pwdxemail)
            self.dbdata["wasreset"] = 0

        # Default flags
        if "acc_enabled" not in self.dbdata or self.dbdata["acc_enabled"] is None:
            self.dbdata["acc_enabled"] = 1
        if "is_admin" not in self.dbdata or self.dbdata["is_admin"] is None:
            self.dbdata["is_admin"] = 0
        if "deleted" not in self.dbdata or self.dbdata["deleted"] is None:
            self.dbdata["deleted"] = 0

        # Password expiration policy
        pwdcycle = str(self.dbdata.get("pwdcycle", "0"))
        if pwdcycle == "3":
            self.dbdata["pwdexpire"] = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        elif pwdcycle == "6":
            self.dbdata["pwdexpire"] = (datetime.now() + timedelta(days=180)).strftime("%Y-%m-%d")
        else:
            self.dbdata["pwdexpire"] = None

        if self.useraccount.new_entry(self.dbdata):
            self.uid = self.useraccount.get_id()
            self.dbdata["uid"] = self.uid
            # Log initial password
            if self.uid:
                self.userpasswords.log_password(pwdxemail, self.uid)
            hylafax_users.add_user(self.uid, str(self.dbdata.get("username") or ""), pwdxemail)
            if hasattr(self.db, "execute"):
                from namifax.services.login_throttle import LoginThrottle

                LoginThrottle(self.db).forget(str(self.dbdata.get("username") or ""))     # a stranger may have tried the name first
            return True

        self.error = "Account creation failed"
        return False

    def list_accounts(self) -> List[Dict[str, Any]]:
        return [r for r in self.useraccount.select(order_by="name") if not r.get("deleted")]

    def update(self) -> bool:
        if not self.uid:
            self.error = "No uid set"
            return False
        return bool(self.useraccount.update_entry(self.dbdata))

    def user_update(self) -> bool:
        return self.update()

    def change_password(self, pwd: str) -> bool:
        if not self.uid:
            self.error = "No uid set"
            return False

        if len(pwd) < settings.min_passwd_size():
            self.error = f"Password too short (minimum {settings.min_passwd_size()} characters)"
            return False

        if len(pwd) > settings.max_passwd_size():
            self.error = f"Password too long (maximum {settings.max_passwd_size()} characters)"
            return False

        # Reuse check
        pwd_reuse = bool(self.dbdata.get("pwd_reuse", False))
        if not pwd_reuse and self.userpasswords.password_used(pwd, self.uid):
            self.error = "Password has already been used before"
            return False

        # Expiration calculation
        pwdcycle = str(self.dbdata.get("pwdcycle", "0"))
        if pwdcycle == "3":
            self.dbdata["pwdexpire"] = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        elif pwdcycle == "6":
            self.dbdata["pwdexpire"] = (datetime.now() + timedelta(days=180)).strftime("%Y-%m-%d")
        else:
            self.dbdata["pwdexpire"] = None

        self.dbdata["password"] = hash_password(pwd)
        self.dbdata["wasreset"] = 0

        if self.useraccount.update_entry(self.dbdata):
            self.userpasswords.log_password(pwd, self.uid)
            hylafax_users.change_password(self.uid, str(self.dbdata.get("username") or ""), pwd)
            return True

        self.error = "Failed to update password"
        return False

    def reset_password(self, email: str) -> Tuple[bool, Optional[str]]:
        """Give the account with this e-mail address a new random password that must be changed at the next login.

        Returns ``(True, the new password)``; the caller mails it, and calls ``undo_reset`` if that fails. The address is
        matched ignoring case, and an account that was removed is not found. Several accounts with one address: the oldest.
        """
        from sqlalchemy import func, select

        from namifax.models import UserAccount

        email = (email or "").strip()
        if not email:
            self.error = "No email provided"
            return False, None

        rows = self.db.execute(select(UserAccount).where(func.lower(UserAccount.email) == email.lower())
                               .order_by(UserAccount.uid)).scalars().all()
        found = next((r for r in rows if not r.deleted), None)
        if found is None:
            self.error = "Sorry, no corresponding user was found."
            return False, None

        self.load(found.uid)
        self._before_reset = (self.dbdata.get("password"), self.dbdata.get("wasreset"))
        new_pwd = genpasswd()
        self.dbdata["password"] = hash_password(new_pwd)
        self.dbdata["wasreset"] = 1

        if self.useraccount.update_entry(self.dbdata):
            hylafax_users.change_password(self.uid, str(self.dbdata.get("username") or ""), new_pwd)
            return True, new_pwd

        self.error = f"Error resetting password for {found.username}"
        return False, None

    def undo_reset(self) -> bool:
        """Put back the password the account had before ``reset_password`` (the new one could not be delivered)."""
        before = getattr(self, "_before_reset", None)
        if not before or not self.uid:
            return False
        self.dbdata["password"], self.dbdata["wasreset"] = before
        return bool(self.useraccount.update_entry(self.dbdata))

    def set_newpassword(self, oldpwd: str, newpwd: str) -> bool:
        if not self.uid:
            self.error = "No uid set"
            return False

        if len(oldpwd) < settings.min_passwd_size():
            self.error = "Old password too short"
            return False

        rec = self.useraccount.find({"uid": self.uid})
        if isinstance(rec, list):
            rec = rec[0] if rec else None
        if not rec or not verify_password(rec.get("password"), oldpwd):
            self.error = "Incorrect old password"
            return False

        return self.change_password(newpwd)

    def login(
        self,
        username: str,
        password: str,
        admin: bool = False,
        remote_ip: str = "127.0.0.1",
    ) -> bool:
        creds: Dict[str, Any] = {"username": username}
        if admin:
            creds["is_admin"] = 1

        found = self.useraccount.find(creds, reduce_single=False) or []
        if isinstance(found, dict):
            found = [found]
        data = next((row for row in found if verify_password(row.get("password"), password)), None)

        if data:
            if data.get("acc_enabled") in (1, True, "1"):
                self._log(f"class UserAccount> Login successful for '{username}' from IP: '{remote_ip}'")
                self.pwdexpired = False
                today = datetime.now().strftime("%Y-%m-%d")

                # Expiration check
                pwdexpire = data.get("pwdexpire")
                if pwdexpire and today >= str(pwdexpire) and str(data.get("pwdcycle", "0")) != "0":
                    self.pwdexpired = True

                # First login check
                if data.get("last_login") is None:
                    self.pwdexpired = True

                # Was reset check
                if data.get("wasreset") in (1, True, "1"):
                    self.pwdexpired = True

                self.logged_in = True
                if data.get("is_admin") in (1, True, "1"):
                    self.admin_logged_in = True

                self.load_vals(data)

                # Update login timestamp & ip
                update_info = {
                    "uid": self.uid,
                    "last_login": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "last_ip": remote_ip,
                }
                if needs_rehash(data.get("password")):             # an MD5 account of the original: store Argon2id from now on
                    update_info["password"] = hash_password(password)
                self.useraccount.update_entry(update_info)
                return True
            else:
                self.logged_in = False
                self.error = "Account is disabled"
                self._failed(username, password, remote_ip)
                return False

        self.logged_in = False
        self.error = "Incorrect username or password"
        self._failed(username, password, remote_ip)
        return False

    def _log(self, text: str) -> None:
        """Write to the system log through this account's session."""
        from namifax.common.helpers import avantfaxlog

        avantfaxlog(text, session=self.db if hasattr(self.db, "execute") else None)

    def _failed(self, username: str, password: str, remote_ip: str) -> None:
        masked = "XXXXXX" + (password or "")[-3:]                  # never the whole password
        self._log(f"class UserAccount> failed login attempt for '{username}' pwd: '{masked}' from IP: '{remote_ip}'")

    def login_alternate_auth(
        self,
        username: str,
        password: str,
        admin: bool = False,
        remote_ip: str = "127.0.0.1",
    ) -> bool:
        """Log in with the system password (PAM, pwauth...) of an account that exists in AvantFAX (the original's
        login_alternate_auth). The reason for a refusal is left in ``get_error()``."""
        import os

        from namifax.auth import alternate

        authenticator = alternate.backend()
        name = os.environ.get("ALTERNATE_AUTH_CLASS", "PAMAuth")
        if authenticator is None or not authenticator.login(username, password):
            self._log(f"class UserAccount> failed '{name}' login attempt for user '{username}' from IP: '{remote_ip}'")
            self.error = "Incorrect username or password"
            self.logged_in = False
            return False
        return self._login_known_user(username, admin, remote_ip, f"'{name}' login successful")

    def login_webauth(
        self,
        username: str,
        admin: bool = False,
        remote_ip: str = "127.0.0.1",
    ) -> bool:
        """Log in a user the web server has already authenticated (REMOTE_USER)."""
        return self._login_known_user(username, admin, remote_ip, "Alternate Login successful")

    def _login_known_user(self, username: str, admin: bool, remote_ip: str, success_text: str) -> bool:
        creds: Dict[str, Any] = {"username": username}
        if admin:
            creds["is_admin"] = 1

        data = self.useraccount.find(creds)
        if isinstance(data, list) and data:
            data = data[0]

        if data:
            if data.get("acc_enabled") in (1, True, "1"):
                self._log(f"class UserAccount> {success_text} for user '{username}' from IP: '{remote_ip}'")
                self.logged_in = True
                if data.get("is_admin") in (1, True, "1"):
                    self.admin_logged_in = True
                self.load_vals(data)

                update_info = {
                    "uid": self.uid,
                    "last_login": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "last_ip": remote_ip,
                }
                self.useraccount.update_entry(update_info)
                return True
            else:
                self.logged_in = False
                self.error = "Account is disabled"
                self._log(f"class UserAccount> failed login attempt for user '{username}' from IP: '{remote_ip}' (account disabled)")
                return False

        self.logged_in = False
        self.error = f"User '{username}' not found for web authentication"
        self._log(f"class UserAccount> failed login attempt for user '{username}' from IP: '{remote_ip}' (no such account)")
        return False

    def load(self, userid: int) -> bool:
        if not userid:
            self.error = "No userid"
            return False

        if self.useraccount.load(userid):
            self.load_vals(self.useraccount.get_info())
            return True

        self.error = "Invalid userid"
        return False

    def load_by_username(self, username: str) -> bool:
        """Alias used by the SSO and passkey code."""
        return self.load_username(username)

    def load_by_id(self, userid: int) -> bool:
        """Alias of ``load`` used by the passkey code."""
        return self.load(userid)

    def create_user(
        self,
        username: str,
        password: str,
        name: str = "",
        email: str = "",
        is_admin: bool = False,
    ) -> bool:
        """Create an account from keyword arguments (single sign-on provisioning)."""
        return self.create({
            "username": username, "password": password, "name": name, "email": email,
            "is_admin": 1 if is_admin else 0,
        })

    def get_username(self) -> Optional[str]:
        return self.dbdata.get("username")

    def get_name(self) -> Optional[str]:
        return self.dbdata.get("name")

    @property
    def name(self) -> Optional[str]:
        return self.dbdata.get("name")

    @property
    def username(self) -> Optional[str]:
        return self.dbdata.get("username")

    @property
    def email(self) -> Optional[str]:
        return self.dbdata.get("email")

    @property
    def language(self) -> Optional[str]:
        return self.dbdata.get("language")

    def load_username(self, username: str) -> bool:
        if not username:
            self.error = "No username"
            return False

        data = self.useraccount.find({"username": username})
        if isinstance(data, list) and data:
            data = data[0]

        if data:
            self.load_vals(data)
            return True

        self.error = "Invalid username"
        return False

    def loadbyemail(self, email: str) -> bool:
        if not email:
            self.error = "No email"
            return False

        data = self.useraccount.find({"email": email})
        if isinstance(data, list) and data:
            data = data[0]

        if data:
            self.load_vals(data)
            return True

        self.error = "Invalid email"
        return False

    def remove(self, userid: int) -> bool:
        if not userid:
            self.error = "No UserAccount to remove"
            return False

        if not self.load(userid):
            self.error = f"Error deleting account {userid}: Not found"
            return False

        # Soft delete. The legacy code set username, email and password to NULL, which the NOT NULL columns
        # (and strict MySQL) reject, so nothing was ever deleted. A placeholder that is unique per account frees
        # the real username and address for reuse and can never match a login (no password hash is empty).
        soft_del = {
            "uid": userid,
            "deleted": 1,
            "acc_enabled": 0,
            "wasreset": 1,
            "email": f"deleted.{userid}@invalid.invalid",
            "username": f"deleted.{userid}",
            "password": "",
        }
        username = str(self.dbdata.get("username") or "")           # (the real name, before the placeholder is stored)
        self.useraccount.update_entry(soft_del)
        self.userpasswords.clear_hashes(userid)
        hylafax_users.remove_user(username)
        return True

    # Getters and Setters for permissions
    def get_modemdevs(self) -> List[str]:
        raw = self.dbdata.get("modemdevs")
        if raw:
            return [x for x in str(raw).split("|") if x]
        return []

    def set_modemdevs(self, val: Optional[List[Any]] = None) -> bool:
        if not self.uid:
            return False
        if val:
            self.dbdata["modemdevs"] = "|".join(str(x) for x in val if x)
        else:
            self.dbdata["modemdevs"] = None
        return True

    def get_faxcats(self) -> List[str]:
        raw = self.dbdata.get("faxcats")
        if raw:
            return [x for x in str(raw).split("|") if x]
        return []

    def set_faxcats(self, val: Optional[List[Any]] = None) -> bool:
        if not self.uid:
            return False
        if val:
            self.dbdata["faxcats"] = "|".join(str(x) for x in val if x)
        else:
            self.dbdata["faxcats"] = None
        return True

    def get_didrouting(self) -> List[str]:
        raw = self.dbdata.get("didrouting")
        if raw:
            return [x for x in str(raw).split("|") if x]
        return []

    def set_didrouting(self, val: Optional[List[Any]] = None) -> bool:
        if not self.uid:
            return False
        if val:
            self.dbdata["didrouting"] = "|".join(str(x) for x in val if x)
        else:
            self.dbdata["didrouting"] = None
        return True

    def set_username(self, username: str) -> bool:
        if not self.uid:
            return False

        if not re.match(r"^[\.\w]+$", username):
            self.error = "Invalid username format"
            return False

        others = self.useraccount.find({"username": username}, reduce_single=False) or []
        if any(int(r["uid"]) != int(self.uid) for r in others):
            self.error = "Username already in use"
            return False

        self.dbdata["username"] = username
        return True

    def set_email(self, email: str) -> bool:
        if not self.uid:
            return False

        others = self.useraccount.find({"email": email}, reduce_single=False) or []
        if any(int(r["uid"]) != int(self.uid) for r in others):
            self.error = "Email already in use"
            return False

        self.dbdata["email"] = email
        return True


# Modern Alias
UserAccountService = NFUserAccount
