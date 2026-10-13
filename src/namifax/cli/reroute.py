"""namifax.cli.reroute

Reroute modem or DID routing contact email matching legacy tools/reroute.php.
"""

from __future__ import annotations

import os
import sys

from typing import Any

from namifax.db.provider import cli_session
from namifax.services.did import DIDRouting
from namifax.services.modem import FaxModem


def main(args=None, *, db: Any = None):
    if args is None:
        args = sys.argv[1:]

    if len(args) < 2:
        print("Usage: reroute.php [device | DIDnum] email-address")
        return 0

    if db is not None:
        return _reroute(args[0], args[1], db)
    with cli_session(ensure_schema=True) as opened:
        return _reroute(args[0], args[1], opened)


def _reroute(device: str, email: str, db: Any) -> int:
    enable_did = os.environ.get("ENABLE_DID_ROUTING", "0") in ("1", "true", "True")

    if not enable_did:
        modem = FaxModem(db=db)
        if not modem.load_device(device):
            print(f'Error loading device "{device}"; is it configured with AvantFAX?')
            return 1
        modem.set_contact(email)
    else:
        didr = DIDRouting(db=db)
        if not didr.load_route(device):
            print(f'Error loading DID route for "{device}"; is it configured with AvantFAX?')
            return 1
        didr.set_contact(email)

    return 0


if __name__ == "__main__":
    sys.exit(main())
