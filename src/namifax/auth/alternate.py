"""Which alternate authentication is configured (the original's ALTERNATE_AUTH_ENABLE / _FALLBACK / _CLASS)."""

from __future__ import annotations

import os
from typing import Optional

from namifax.common.settings import flag, text


def enabled() -> bool:
    return flag("ALTERNATE_AUTH_ENABLE", False)


def fallback() -> bool:
    """May the local (AvantFAX) password still be used when the alternate login fails?"""
    return flag("ALTERNATE_AUTH_FALLBACK", True)


def webserver_login() -> bool:
    """Trust REMOTE_USER from a web server that authenticates (Basic auth, Kerberos...). Off unless asked for."""
    return flag("WEBSERVER_AUTH", False)


def backend() -> Optional[object]:
    """The authenticator named by ALTERNATE_AUTH_CLASS (``PAMAuth`` or ``PWAuth``), else None."""
    name = text("ALTERNATE_AUTH_CLASS", "PAMAuth")
    if name == "PAMAuth":
        from namifax.auth.pam import PAMAuthBackend

        return PAMAuthBackend()
    if name == "PWAuth":
        from namifax.auth.password import PWAuthBackend

        return PWAuthBackend(os.environ.get("PWAUTHPATH", "/usr/local/bin/pwauth"))
    return None
