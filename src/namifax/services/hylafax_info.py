"""Facts about the HylaFAX installation."""

from __future__ import annotations

import re
import subprocess
from typing import Optional

from namifax.common.settings import binary


def version() -> Optional[str]:
    """The HylaFAX version `faxstat -i` reports, or None when it cannot be asked (nothing is made up)."""
    faxstat = binary("faxstat")
    if not faxstat:
        return None
    try:
        out = subprocess.run([faxstat, "-i"], capture_output=True, text=True, timeout=5, check=False).stdout or ""
    except (OSError, subprocess.SubprocessError):
        return None
    found = re.search(r"version\s+(?:HylaFAX\s+)?([0-9][0-9A-Za-z.\-+]*)\s+built", out, re.I) \
        or re.search(r"HylaFAX\s+([0-9][0-9A-Za-z.\-+]*)\s+built", out, re.I)
    return found.group(1) if found else None
