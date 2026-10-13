#!/usr/bin/env python3
"""AvantFAX modern CLI replacement for includes/phb.php.

Generates HylaFAX client phonebook file (PBOOK1.1 format) from the AvantFAX AddressBook.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Sequence

# Ensure src directory is on sys.path
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from namifax.db.provider import cli_session
from namifax.services.addressbook import NFAddressBook

from namifax.common import settings  # noqa: E402

DEFAULT_PHONEBOOK_PATH = settings.phonebook_path()


def generate_phonebook_content(addressbook: NFAddressBook, should_stop=None) -> str:
    """Generate HylaFAX PBOOK1.1 stream content from address book (``JobStopped`` when asked to stop: no half file is written)."""
    return build_phonebook(addressbook, should_stop)[0]


def build_phonebook(addressbook: NFAddressBook, should_stop=None) -> tuple[str, int]:
    """Like ``generate_phonebook_content`` but also gives the number of entries (companies) written."""
    out = ["PBOOK1.1"]
    count = 0

    companies = addressbook.get_companies()
    if companies:
        for entry in companies:
            if should_stop and should_stop():
                from namifax.services.job_control import JobStopped

                raise JobStopped()
            cname = entry.get("company", "")
            cid = entry.get("abook_id")
            out.append(f"{cname}|")

            addressbook.loadbycid(cid)
            faxnums = addressbook.get_faxnums()
            valid_nums = [f.get("faxnumber") for f in faxnums if f.get("faxnumber")]
            out.append(";".join(valid_nums))
            out.append("|||||||")
            count += 1

    return "".join(out), count


def run_phb(argv: Sequence[str] | None = None, addressbook: NFAddressBook | None = None, *, db: Any = None, should_stop=None) -> int:
    """Execute phonebook export logic (exit code 0)."""
    _run_phb(argv, addressbook, db=db, should_stop=should_stop)
    return 0


def _run_phb(argv: Sequence[str] | None, addressbook: NFAddressBook | None, *, db: Any, should_stop) -> int:
    """Export the phonebook file; returns the number of entries written."""
    parser = argparse.ArgumentParser(description="Generate HylaFAX phonebook from AvantFAX address book.")
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_PHONEBOOK_PATH,
        help=f"Target phonebook path (default: {DEFAULT_PHONEBOOK_PATH})",
    )
    args = parser.parse_args(argv[1:] if argv is not None else None)

    if addressbook is not None:
        content, count = build_phonebook(addressbook, should_stop)
    elif db is not None:
        content, count = build_phonebook(NFAddressBook(db=db), should_stop)
    else:
        with cli_session(ensure_schema=True) as opened:
            content, count = build_phonebook(NFAddressBook(db=opened), should_stop)

    out_path = os.path.abspath(args.output)
    parent_dir = os.path.dirname(out_path)
    if parent_dir and not os.path.exists(parent_dir):
        try:
            os.makedirs(parent_dir, exist_ok=True)
        except OSError:
            pass

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    return count


def export_phonebook(output_path: str = DEFAULT_PHONEBOOK_PATH, addressbook: NFAddressBook | None = None, *, db: Any = None,
                     should_stop=None) -> int:
    """Convenience helper to export phonebook directly."""
    return run_phb(["phb", "-o", output_path], addressbook=addressbook, db=db, should_stop=should_stop)


def export_phonebook_count(output_path: str = DEFAULT_PHONEBOOK_PATH, addressbook: NFAddressBook | None = None, *, db: Any = None,
                           should_stop=None) -> int:
    """Export the phonebook and return how many entries were written (``export_phonebook`` returns the exit code)."""
    return _run_phb(["phb", "-o", output_path], addressbook, db=db, should_stop=should_stop)


def main() -> None:
    sys.exit(run_phb(sys.argv))


if __name__ == "__main__":
    main()

