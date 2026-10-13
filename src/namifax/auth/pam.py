"""System PAM authentication backend replacing legacy PAMAuth.php."""

from __future__ import annotations

import ctypes
import ctypes.util
from typing import Callable


class PAMAuthBackend:
    """Linux/Unix Pluggable Authentication Module (PAM) authenticator."""

    def __init__(
        self,
        pam_driver: Callable[[str, str, str], tuple[bool, str | None]] | None = None,
    ) -> None:
        self.pam_driver = pam_driver
        self.last_error: str | None = None
        self._pam_available = True

        if self.pam_driver is None:
            self._init_system_driver()

    def _init_system_driver(self) -> None:
        """Initialize system PAM driver via python-pam or ctypes."""
        try:
            import pam  # type: ignore

            def _py_pam_driver(user: str, pwd: str, svc: str) -> tuple[bool, str | None]:
                p = pam.pam()
                res = p.authenticate(user, pwd, service=svc)
                err = None if res else getattr(p, "reason", "Authentication failed")
                return bool(res), err

            self.pam_driver = _py_pam_driver
            return
        except ImportError:
            pass

        # Try locating libpam via ctypes
        pam_lib_name = ctypes.util.find_library("pam")
        if pam_lib_name:
            try:
                ctypes.CDLL(pam_lib_name)
                # Found libpam.so/dylib
                # Provide a basic ctypes conversation handler if needed
            except OSError:
                self._pam_available = False
        else:
            self._pam_available = False

    def login(self, username: str, password: str, service: str = "login") -> bool:
        """Authenticate user against system PAM stack."""
        self.last_error = None

        if not username or not password:
            self.last_error = "Username and password cannot be empty"
            return False

        if not self._pam_available or self.pam_driver is None:
            self.last_error = "PAM is not supported or library is unavailable"
            return False

        try:
            success, error_msg = self.pam_driver(username, password, service)
            if not success:
                self.last_error = error_msg or "PAM authentication rejected"
            return success
        except Exception as exc:
            self.last_error = f"PAM authentication error: {exc}"
            return False


# Legacy alias
PAMAuth = PAMAuthBackend
