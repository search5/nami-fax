"""namifax.cli.import_blacklist

Blacklist/DynamicConfig batch import tool matching legacy tools/import_blacklist.php.
"""

from __future__ import annotations

import os
import sys

from typing import Any

from namifax.db.provider import cli_session
from namifax.services.dynconf import DynamicConfig


def main(args=None, *, db: Any = None):
    if args is None:
        args = sys.argv[1:]

    if len(args) < 1:
        print("""usage: import_blacklist.php filename [device]
Example: import_blacklist.php blacklist.txt ttyS0
One CallID (fax number) per line""")
        return 0

    filename = args[0]
    device = args[1] if len(args) > 1 else None

    if not os.path.isfile(filename):
        print(f"Error: File not found: {filename}")
        return 1

    with open(filename, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    if db is not None:
        return _import_blacklist(lines, device, db)
    with cli_session(ensure_schema=True) as opened:
        return _import_blacklist(lines, device, opened)


def _import_blacklist(lines: list[str], device: str | None, db: Any) -> int:
    cnt = 0
    for line in lines:
        callid = line.strip()
        if not callid:
            continue

        dc = DynamicConfig(db=db)
        if dc.create(device, callid):
            print(f"Created Rule: {callid}")
            cnt += 1
        else:
            print(f"Skipping existing rule: {callid}")

    print(f"Created {cnt} rules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
