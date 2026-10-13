#!/usr/bin/env python3
"""CUPS Inbound Print-to-Fax CLI backend for NamiFAX.

Receives print job from CUPS virtual queue, extracts [[FAX: ...]] tag,
and automatically enqueues fax transmission.
"""

from __future__ import annotations

import os
import sys
from typing import Sequence

# Ensure src directory is on sys.path
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from namifax.services.printer import process_inbound_print_job


def main(argv: Sequence[str] | None = None) -> int:
    """CUPS backend entry point: job_id user title copies options [filename]."""
    args = list(argv[1:]) if argv is not None else list(sys.argv[1:])

    # CUPS passes: <job-id> <user> <title> <num-copies> <options> [filename]
    user = args[1] if len(args) > 1 else "cups_user"

    print_data = b""
    if len(args) > 5 and os.path.exists(args[5]):
        with open(args[5], "rb") as f:
            print_data = f.read()
    else:
        # Read from standard input
        if not sys.stdin.isatty():
            print_data = sys.stdin.buffer.read()

    if not print_data:
        print("[NamiFAX Print-to-Fax] No print data received.", file=sys.stderr)
        return 0

    from namifax.db.provider import cli_session

    with cli_session() as session:
        result = process_inbound_print_job(print_data, sender_user=user, db=session)

    if result.get("dispatched"):
        print(f"[NamiFAX Print-to-Fax] Job successfully enqueued for {result['destination']}.")
        return 0
    print(f"[NamiFAX Print-to-Fax] {result.get('message', 'Saved to drafts.')}", file=sys.stderr)
    return 1 if result.get("status") == "FAILED" else 0       # (a job without a tag is only saved as a draft: not a failure)


if __name__ == "__main__":
    sys.exit(main())
