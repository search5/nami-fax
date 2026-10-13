"""Keep the HylaFAX users (hosts.hfaxd) in step with the AvantFAX accounts, like the original's faxadduser/faxdeluser calls.

Switched on with ``HYLAFAX_USER_SYNC=1`` (the web user needs sudo rights for exactly these two programs; see docs/ko/install/hylafax.md).
The programs run without a shell, and a failure is logged but never stops the account change.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from typing import Optional

from namifax.common.settings import flag, text


def enabled() -> bool:
    return flag("HYLAFAX_USER_SYNC", False)


def _program(name: str) -> str:
    return os.path.join(text("HYLAFAX_PREFIX", "/usr"), "sbin", name)


def _run(*args: str) -> bool:
    sudo = shlex.split(os.environ.get("SUDO", "sudo"))
    try:
        return subprocess.run([*sudo, *args], check=False).returncode == 0
    except OSError:
        return False


def add_user(uid: Optional[int], username: str, password: str) -> bool:
    if not enabled() or not username or not password:
        return False
    return _run(_program("faxadduser"), "-u", str(uid or ""), "-p", password, username)


def remove_user(username: str) -> bool:
    if not enabled() or not username:
        return False
    return _run(_program("faxdeluser"), username)


def change_password(uid: Optional[int], username: str, password: str) -> bool:
    """A new password replaces the HylaFAX user (the program cannot change a password in place)."""
    if not enabled():
        return False
    remove_user(username)
    return add_user(uid, username, password)
