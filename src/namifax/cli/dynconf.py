#!/usr/bin/env python3
"""AvantFAX modern CLI replacement for includes/dynconf.php.

Performs HylaFAX DynamicConfig lookup for incoming call filtering.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any, Sequence

# Ensure src directory is on sys.path
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from namifax.common.helpers import avantfaxlog
from namifax.db.provider import cli_session, use_session
from namifax.services.dynconf import DynamicConfig


def strip_sipinfo(text: str) -> str:
    """Strip SIP host/domain information from CallerID (regex: ^(.*)@(.*)$)."""
    match = re.match(r"^(.*)@(.*)$", text)
    if match:
        return match.group(1)
    return text


def run_dynconf(argv: Sequence[str], dc: DynamicConfig | None = None, *, db: Any = None) -> int:
    """Execute dynconf command logic."""
    if len(argv) <= 1:
        # Match legacy script output exactly for usage
        print("dynconf.php device CallID1 CallIDn...")
        return 0

    device = argv[1]

    if len(argv) < 3 or argv[2] == "":
        callid1 = "EMPTY CALLID"
    else:
        callid1 = strip_sipinfo(argv[2])

    if dc is None:
        if db is None:
            with cli_session(ensure_schema=True) as opened:
                return _dynconf_lookup(DynamicConfig(db=opened), device, callid1)
        dc = DynamicConfig(db=db)

    if db is not None:
        with use_session(db):                       # the log lines go to the same session
            return _dynconf_lookup(dc, device, callid1)
    return _dynconf_lookup(dc, device, callid1)


def _dynconf_lookup(dc: DynamicConfig, device: str, callid1: str) -> int:
    """Lookup CallID1 in DynamicConfig table; if exists, reject call."""
    avantfaxlog(f"dynconf> checking CallID1 {callid1} on device {device}", echo=False)
    if dc.lookup(device, callid1):
        avantfaxlog(f"dynconf> rejecting {callid1} on device {device}", echo=False)
        print("RejectCall: true")

    return 0


def main() -> None:
    sys.exit(run_dynconf(sys.argv))


if __name__ == "__main__":
    main()
