import hashlib
import hmac
import logging
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import pyotp
from namifax.common.secretbox import SecretDecryptError, SecretKeyError, decrypt, encrypt
from namifax.db.repository import Repository


# Brute-force protection: a 6-digit code has only a million values, so wrong codes are counted per user
# (in the database, so every worker sees the same count) and the account is locked for a while.
MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 15
_TS = "%Y-%m-%d %H:%M:%S"


# Recovery codes: 10 characters from an alphabet without look-alikes (about 49 bits), shown as XXXXX-XXXXX. Only salted
# scrypt hashes are stored, so a copy of the database does not reveal usable codes. (Codes made by older versions are
# plain 8-character hex values; they are still accepted once.)
RECOVERY_CODE_COUNT = 8
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_SCRYPT = dict(n=2 ** 12, r=8, p=1, dklen=32)   # ~15 ms; the codes themselves carry ~49 bits


def _normalize_code(code: str) -> str:
    return re.sub(r"[\s-]", "", code or "").upper()


def new_recovery_code() -> str:
    raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(10))
    return f"{raw[:5]}-{raw[5:]}"


def hash_recovery_code(code: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(_normalize_code(code).encode(), salt=salt, **_SCRYPT)
    return f"scrypt${salt.hex()}${digest.hex()}"


def recovery_code_matches(stored: str, code: str) -> bool:
    """Does ``code`` match the stored entry (a hash, or an old plaintext code)?"""
    stored, typed = (stored or "").strip(), _normalize_code(code)
    if not typed:
        return False
    if stored.startswith("scrypt$"):
        try:
            _, salt, digest = stored.split("$")
            candidate = hashlib.scrypt(typed.encode(), salt=bytes.fromhex(salt), **_SCRYPT)
            return hmac.compare_digest(candidate, bytes.fromhex(digest))
        except ValueError:
            return False
    return hmac.compare_digest(stored.upper().encode(), typed.encode())


class TotpService:
    """RFC 6238 Time-based One-Time Password (TOTP) two-factor authentication service."""

    def __init__(self, db: Any = None) -> None:
        from namifax.db.missing import resolve_db

        self.db = db if not hasattr(db, "execute") else db   # a Session is used as is
        if db is None:
            self.db = resolve_db(None, "TotpService")

    @staticmethod
    def generate_secret() -> str:
        """Generate a random Base32 secret."""
        return pyotp.random_base32()

    @staticmethod
    def get_provisioning_uri(username: str, secret: str, issuer: str = "NamiFAX") -> str:
        """Generate standard otpauth:// provisioning URI for Authenticator apps."""
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=username, issuer_name=issuer)

    @staticmethod
    def verify_code(secret: str, code: str) -> bool:
        """Verify 6-digit TOTP challenge token within valid time window."""
        if not secret or not code:
            return False
        totp = pyotp.TOTP(secret)
        return totp.verify(code.strip())

    def _rows(self, uid: int) -> Any:
        return Repository("UserTOTP", db=self.db)

    def is_totp_enabled(self, uid: int) -> bool:
        """Check whether 2FA is currently active for the given user ID."""
        row = self._rows(uid).find({"uid": int(uid)})
        if isinstance(row, list):
            row = row[0] if row else None
        return bool(row and _flag(row.get("is_enabled")))

    def enable_totp(self, uid: int, secret: str, code: str) -> Dict[str, Any]:
        """Validate challenge code, persist configuration, and generate 8 emergency recovery codes."""
        if not self.verify_code(secret, code):
            return {"success": False, "message": "Invalid TOTP verification code."}

        # Generate single-use recovery codes; only their hashes are stored
        backup_codes = [new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        repo = self._rows(uid)
        repo.delete_where({"uid": int(uid)})
        repo.new_entry({
            "uid": int(uid), "secret_key": encrypt(secret), "is_enabled": 1,
            "backup_codes": ",".join(hash_recovery_code(c) for c in backup_codes), "created_at": datetime.now().isoformat(),
            "failed_attempts": 0, "locked_until": None,
        })
        return {
            "success": True,
            "backup_codes": backup_codes,
            "message": "Two-factor authentication enabled successfully.",
        }

    def disable_totp(self, uid: int) -> bool:
        """Disable two-factor authentication for the given user."""
        self._rows(uid).delete_where({"uid": int(uid)})
        return True

    def _row(self, uid: int) -> Optional[Dict[str, Any]]:
        row = self._rows(uid).find({"uid": int(uid)})
        if isinstance(row, list):
            row = row[0] if row else None
        return row

    @staticmethod
    def _lock_end(row: Optional[Dict[str, Any]]) -> Optional[datetime]:
        value = (row or {}).get("locked_until")
        try:
            return datetime.strptime(str(value), _TS) if value else None
        except ValueError:
            return None

    def lock_remaining_seconds(self, uid: int) -> int:
        """Seconds until the user may try a code again (0 when not locked)."""
        end = self._lock_end(self._row(uid))
        return max(0, int((end - datetime.now()).total_seconds()) + 1) if end and end > datetime.now() else 0

    def is_locked(self, uid: int) -> bool:
        return self.lock_remaining_seconds(uid) > 0

    def _count_attempt(self, uid: int) -> int:
        """Reserve one attempt (atomic increment, so parallel guesses cannot all see the old count)."""
        from sqlalchemy import func, update

        from namifax.models.usertotp import UserTOTP

        self.db.execute(update(UserTOTP).where(UserTOTP.uid == int(uid)).values(
            failed_attempts=func.coalesce(UserTOTP.failed_attempts, 0) + 1))
        row = self._row(uid)
        return int((row or {}).get("failed_attempts") or 0)

    def verify_user_login(self, uid: int, code: str) -> bool:
        """Verify user login challenge via TOTP code or single-use backup recovery code.

        Each try is counted before it is checked; after ``MAX_FAILED_ATTEMPTS`` wrong ones the user is locked
        out for ``LOCK_MINUTES`` and even a correct code is refused until then.
        """
        repo = self._rows(uid)
        row = self._row(uid)
        if not row or not _flag(row.get("is_enabled")):
            return True

        end = self._lock_end(row)
        if end and end > datetime.now():
            return False
        if end or row.get("locked_until"):                       # an expired lock: start with a clean count
            repo.update_where({"uid": int(uid)}, {"failed_attempts": 0, "locked_until": None})
            row = {**row, "failed_attempts": 0, "locked_until": None}

        attempts = self._count_attempt(uid)
        if attempts <= MAX_FAILED_ATTEMPTS and self._code_is_valid(repo, row, uid, code):
            repo.update_where({"uid": int(uid)}, {"failed_attempts": 0, "locked_until": None})
            return True

        if attempts >= MAX_FAILED_ATTEMPTS:
            until = (datetime.now() + timedelta(minutes=LOCK_MINUTES)).strftime(_TS)
            repo.update_where({"uid": int(uid)}, {"locked_until": until})
        return False

    def _code_is_valid(self, repo: Any, row: Dict[str, Any], uid: int, code: str) -> bool:
        try:
            secret = decrypt(row.get("secret_key"))
        except (SecretDecryptError, SecretKeyError):
            logging.getLogger("namifax").error("The 2FA seed of user %s cannot be decrypted; check NAMIFAX_SECRET_KEY", uid)
            return False                                     # fail closed
        clean_code = code.strip()

        # 1. Primary TOTP token check
        if secret and self.verify_code(secret, clean_code):
            return True

        # 2. Backup emergency recovery code check (each code works once). A 6-digit input is a TOTP attempt, never a
        # recovery code, so the (deliberately slow) hash comparison is skipped for it.
        if re.fullmatch(r"\d{6}", clean_code):
            return False
        entries = [c.strip() for c in (row.get("backup_codes") or "").split(",") if c.strip()]
        for index, stored in enumerate(entries):
            if recovery_code_matches(stored, clean_code):
                del entries[index]
                repo.update_where({"uid": int(uid)}, {"backup_codes": ",".join(entries)})
                return True
        return False

    def backup_codes_remaining(self, uid: int) -> int:
        row = self._row(uid)
        return len([c for c in ((row or {}).get("backup_codes") or "").split(",") if c.strip()])

    def regenerate_backup_codes(self, uid: int) -> list:
        """Replace every recovery code with new ones (returned once, stored hashed)."""
        if not self._row(uid):
            return []
        codes = [new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
        self._rows(uid).update_where({"uid": int(uid)}, {"backup_codes": ",".join(hash_recovery_code(c) for c in codes)})
        return codes


def _flag(value: Any) -> bool:
    """The legacy engine may hand back 0/1 or text; unknown text is off."""
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "t", "yes")
    return bool(value)
