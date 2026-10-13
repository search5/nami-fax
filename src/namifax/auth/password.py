"""Password hashing and external pwauth authentication backend replacing legacy PWAuth.php."""

from __future__ import annotations

import hashlib
import hmac
import subprocess

STATUS_VALID = 0
STATUS_NO_USER = 1
STATUS_BAD_PASSWORD = 2
STATUS_ERROR = 3


class PasswordManager:
    """Manages AvantFAX password hashing and verification."""

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using AvantFAX legacy MD5 digest."""
        if not isinstance(password, str):
            password = str(password)
        return hashlib.md5(password.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify plain password against hashed value in constant time."""
        computed_hash = PasswordManager.hash_password(plain_password)
        return hmac.compare_digest(computed_hash.lower(), hashed_password.lower())


class PWAuthBackend:
    """External pwauth executable PAM authenticator."""

    def __init__(self, binary_path: str = "/usr/local/bin/pwauth", timeout: int = 10) -> None:
        self.binary_path = binary_path
        self.timeout = timeout
        self.last_error: str | None = None

    def login(self, username: str, password: str) -> bool:
        """Authenticate user by calling the pwauth binary via stdin pipes."""
        self.last_error = None
        input_payload = f"{username}\n{password}\n"

        try:
            res = subprocess.run(
                [self.binary_path],
                input=input_payload,
                text=True,
                capture_output=True,
                timeout=self.timeout,
            )

            if res.returncode == STATUS_VALID:
                return True
            elif res.returncode == STATUS_NO_USER:
                self.last_error = f"User '{username}' does not exist"
            elif res.returncode == STATUS_BAD_PASSWORD:
                self.last_error = f"Incorrect password for user '{username}'"
            else:
                self.last_error = f"pwauth exited with code {res.returncode}"

            return False
        except FileNotFoundError:
            self.last_error = f"pwauth binary not found at '{self.binary_path}'"
            return False
        except Exception as exc:
            self.last_error = f"pwauth execution error: {exc}"
            return False


# Legacy alias
PWAuth = PWAuthBackend
