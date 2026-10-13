"""namifax import-archive: load an existing HylaFAX / AvantFAX fax archive into the database.

Port of the original ``tools/import_archive.php``. The archive directory holds two trees:

* ``recvd/<anything>/fax.tif``: received faxes. The sender, page count and receive time come from the TIFF headers
  (``faxinfo``); the caller id (default ``CallID1``) identifies the sender in the address book, which gets a new entry
  for an unknown number.
* ``sent/YYYY/MM/DD/<fax number>/<time>/fax.pdf``: sent faxes; everything is read from the path.

Every fax is stored as an archived (not inbox) fax in the given category. A path counts only by the first directory
below the archive root: the original matched the words ``recvd``/``sent`` anywhere in the full path, so a base
directory such as ``sent-faxes`` confused it. It also overwrote the archive root it needed for the sent faxes while
walking the received ones; that is fixed here too.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Optional, Sequence

from namifax.common.helpers import avantfaxlog, faxinfo, hylafax_date_to_iso
from namifax.db.provider import cli_session, use_session
from namifax.services.addressbook import NFAddressBook
from namifax.services.archive_in import ArchiveIn
from namifax.services.archive_out import ArchiveOut

USAGE = """usage: import_archive.php faxPath faxCategoryId [--user-id N] [--modem DEVICE] [--callid CallID1]
Example: import_archive.php /var/www/avantfax/faxes/ 3
faxCategoryId is found in the database with "select * from FaxCategory;"
"""


def main(args: Optional[Sequence[str]] = None, *, session: Any = None) -> int:
    argv = list(sys.argv[1:] if args is None else args)
    if len(argv) < 2 or argv[0].startswith("-"):
        print(USAGE, end="")
        return 0
    parser = argparse.ArgumentParser(prog="namifax import-archive", add_help=False)
    parser.add_argument("faxpath")
    parser.add_argument("faxcatid", type=int)
    parser.add_argument("--user-id", type=int, default=1, help="user the sent faxes are attributed to (default 1)")
    parser.add_argument("--modem", default="ttyS0", help="device recorded for received faxes (default ttyS0)")
    parser.add_argument("--callid", default="CallID1", help="faxinfo field that holds the caller's number")
    options = parser.parse_args(argv)

    if session is not None:
        with use_session(session):
            return _import(options, session)
    with cli_session(ensure_schema=True) as opened:
        return _import(options, opened)


def _files(root: str) -> list[str]:
    found: list[str] = []
    for directory, subdirs, names in os.walk(root):
        subdirs.sort()
        found.extend(os.path.join(directory, n) for n in sorted(names))
    return found


def _import(options: argparse.Namespace, session: Any) -> int:
    root = os.path.abspath(options.faxpath)
    count = 0
    for path in _files(root):
        parts = os.path.relpath(path, root).split(os.sep)
        if parts[0] == "recvd" and path.endswith(".tif"):
            print(f"RECV: {path}")
            count += _import_received(path, options, session)
        elif parts[0] == "sent" and path.endswith(".pdf"):
            print(f"SEND: {path}")
            count += _import_sent(path, parts[1:], options, session)
    print(f"{count} records added")
    return 0


def _number_ids(session: Any, number: str, company: Optional[str] = None) -> tuple[Optional[int], Optional[int]]:
    """(faxnumid, companyid) for a number, registering it when new; None when it cannot be resolved."""
    book = NFAddressBook(db=session)
    faxnumid, companyid, outcome = book.find_or_create_number(number, company)
    if outcome == "multiple":
        avantfaxlog("> Found fax number with multiple companies", echo=True)
    elif outcome == "failed":
        avantfaxlog(f"> FAILED to register '{number}' - {book.get_error()}", echo=True)
    elif outcome != "found":
        avantfaxlog(f"> Created company '{company or number}' with cid '{companyid}'", echo=True)
    return faxnumid or None, companyid


def _import_received(path: str, options: argparse.Namespace, session: Any) -> int:
    info = faxinfo(path)
    if not info:
        avantfaxlog(f"> SKIPPED {path}: the fax headers cannot be read", echo=True)
        return 0
    sender = info.get("Sender") or ""
    caller = info.get(options.callid)
    number = sender if caller in (None, "", "<NONE>") else caller
    faxnumid, _ = _number_ids(session, number, sender or None)

    faxdir = os.path.dirname(path)
    inbox = ArchiveIn(db=session)
    if inbox.create(faxdir, faxnumid, number, options.modem, int(info.get("Pages") or 1),
                    hylafax_date_to_iso(info.get("Received")), None):
        fid = inbox.get_fid()
        inbox.set_category(options.faxcatid)
        inbox.set_archivebox(fid)
        avantfaxlog(f"> Inserted {faxdir} from {sender} ({faxnumid}) to Inbox", echo=True)
        return 1
    avantfaxlog(f"> FAILED to insert {faxdir} from {sender} ({faxnumid}) to Inbox - {inbox.get_error()}", echo=True)
    return 0


def _import_sent(path: str, below_sent: list[str], options: argparse.Namespace, session: Any) -> int:
    # sent/YYYY/MM/DD/<fax number>/<time>/fax.pdf
    if len(below_sent) < 5:
        avantfaxlog(f"> SKIPPED {path}: not in the sent/YYYY/MM/DD/<number>/<time>/ layout", echo=True)
        return 0
    number = below_sent[3]
    faxnumid, companyid = _number_ids(session, number)
    faxdir = os.path.dirname(path)
    outbox = ArchiveOut(db=session)
    if outbox.create(faxdir, options.user_id, companyid, number, 1):
        outbox.set_note(None, options.faxcatid, options.user_id)
        avantfaxlog(f"> Inserted {faxdir} from {number} ({faxnumid}) to Outbox", echo=True)
        return 1
    avantfaxlog(f"> FAILED to add Sent fax '{faxdir}' ({faxnumid}) to ArchiveOut", echo=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
