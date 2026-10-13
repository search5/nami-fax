"""namifax import-archive: load an existing HylaFAX/AvantFAX fax archive directory into the database."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import select

from namifax.models import AddressBook, AddressBookFAX, FaxArchive


# --- the date format -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("2026:10:01 10:05:09", "2026-10-01 10:05:09"),             # what faxinfo prints
    ("2026/10/01 10:05:09", "2026-10-01 10:05:09"),
    ("2026-10-01 10:05:09", "2026-10-01 10:05:09"),
    ("2026:10:01", "2026-10-01 00:00:00"),
])
def test_hylafax_dates_become_iso(raw, expected):
    from namifax.common.helpers import hylafax_date_to_iso

    assert hylafax_date_to_iso(raw) == expected


def test_an_unreadable_date_becomes_now():
    from datetime import datetime

    from namifax.common.helpers import hylafax_date_to_iso

    got = hylafax_date_to_iso("garbage")
    assert abs((datetime.strptime(got, "%Y-%m-%d %H:%M:%S") - datetime.now()).total_seconds()) < 5


# --- the archive tree -------------------------------------------------------------------------------------------------

def _tree(tmp_path):
    root = tmp_path / "faxes"
    recv = root / "recvd" / "2026" / "05" / "06" / "5551234" / "00042"
    recv.mkdir(parents=True, exist_ok=True)
    (recv / "fax.tif").write_bytes(b"tiff")
    (recv / "fax.pdf").write_bytes(b"%PDF")
    sent = root / "sent" / "2026" / "04" / "03" / "5559999" / "101530"
    sent.mkdir(parents=True, exist_ok=True)
    (sent / "fax.pdf").write_bytes(b"%PDF")
    other = root / "misc"
    other.mkdir(exist_ok=True)
    (other / "notes.txt").write_text("x")
    return root, recv, sent


def _faxinfo(**kw):
    info = {"Sender": "Acme Fax", "CallID1": "5551234", "Pages": "3", "Received": "2026:05:06 09:30:00"}
    info.update(kw)
    return lambda path: info


def _run(tmp_path, dbsession, extra=(), info=None):
    from namifax.cli import import_archive

    root, recv, sent = _tree(tmp_path)
    with patch.object(import_archive, "faxinfo", info or _faxinfo()):
        code = import_archive.main([str(root) + "/", "1", *extra], session=dbsession)
    return code, root, recv, sent


def test_usage_when_arguments_are_missing(capsys):
    from namifax.cli import import_archive

    assert import_archive.main([]) == 0
    assert "usage:" in capsys.readouterr().out


def test_received_and_sent_faxes_are_imported_into_the_archive(tmp_path, dbsession, capsys):
    dbsession.execute(FaxArchive.__table__.delete())
    code, root, recv, sent = _run(tmp_path, dbsession)
    assert code == 0 and "2 records added" in capsys.readouterr().out

    rows = list(dbsession.execute(select(FaxArchive).order_by(FaxArchive.fid)).scalars())
    assert len(rows) == 2
    received = next(r for r in rows if r.faxpath == str(recv))
    assert (received.inbox, received.pages, received.modemdev, received.faxcatid) == (0, 3, "ttyS0", 1)   # archived, not inbox
    assert received.archstamp == "2026-05-06 09:30:00" and received.origfaxnum == "5551234"
    sent_row = next(r for r in rows if r.faxpath == str(sent))
    assert (sent_row.inbox, sent_row.userid, sent_row.origfaxnum, sent_row.pages, sent_row.faxcatid) == (0, 1, "5559999", 1, 1)


def test_unknown_senders_get_an_address_book_entry_and_known_ones_are_reused(tmp_path, dbsession):
    dbsession.execute(FaxArchive.__table__.delete())
    _run(tmp_path, dbsession)
    company = dbsession.execute(select(AddressBook).where(AddressBook.company == "Acme Fax")).scalar_one()
    number = dbsession.execute(select(AddressBookFAX).where(AddressBookFAX.faxnumber == "5551234")).scalar_one()
    assert number.abook_id == company.abook_id
    received = dbsession.execute(select(FaxArchive).where(FaxArchive.faxpath.like("%00042"))).scalar_one()
    assert received.faxnumid == number.abookfax_id                       # received faxes point at the number
    sent = dbsession.execute(select(FaxArchive).where(FaxArchive.faxpath.like("%101530"))).scalar_one()
    sent_company = dbsession.execute(select(AddressBook).where(AddressBook.company == "5559999")).scalar_one()
    assert sent.companyid == sent_company.abook_id                      # sent faxes point at the company

    # a second run finds the number again and does not duplicate the company
    dbsession.execute(FaxArchive.__table__.delete())
    _run(tmp_path, dbsession)
    assert len(list(dbsession.execute(select(AddressBook).where(AddressBook.company == "Acme Fax")).scalars())) == 1


def test_a_fax_without_readable_headers_is_skipped_and_the_rest_continue(tmp_path, dbsession, capsys):
    dbsession.execute(FaxArchive.__table__.delete())
    code, *_ = _run(tmp_path, dbsession, info=lambda path: None)
    out = capsys.readouterr().out
    assert code == 0 and "1 records added" in out                 # only the sent fax (its info comes from the path)


def test_the_options_change_the_defaults(tmp_path, dbsession):
    dbsession.execute(FaxArchive.__table__.delete())
    _run(tmp_path, dbsession, extra=("--user-id", "2", "--modem", "ttyS1", "--callid", "CallID3"),
         info=_faxinfo(**{"CallID3": "5551234", "CallID1": "<NONE>"}))
    rows = {r.faxpath.rsplit("/", 1)[-1]: r for r in dbsession.execute(select(FaxArchive)).scalars()}
    assert rows["00042"].modemdev == "ttyS1" and rows["101530"].userid == 2


def test_only_the_recvd_and_sent_trees_count_not_any_path_that_contains_the_words(tmp_path, dbsession, capsys):
    """The old tool matched the words anywhere in the path, so a base directory called 'sent-faxes' broke it."""
    from namifax.cli import import_archive

    dbsession.execute(FaxArchive.__table__.delete())
    root = tmp_path / "recvd-and-sent-faxes"
    (root / "recvd" / "2026" / "05" / "06" / "5551234" / "7").mkdir(parents=True, exist_ok=True)
    (root / "recvd" / "2026" / "05" / "06" / "5551234" / "7" / "fax.tif").write_bytes(b"t")
    (root / "archive" / "x").mkdir(parents=True, exist_ok=True)
    (root / "archive" / "x" / "other.tif").write_bytes(b"t")            # not in recvd/: ignored
    with patch.object(import_archive, "faxinfo", _faxinfo()):
        import_archive.main([str(root), "1"], session=dbsession)
    assert "1 records added" in capsys.readouterr().out


def test_the_command_is_registered():
    import importlib

    import inspect

    main_mod = importlib.import_module("namifax.main")
    assert "import-archive" in inspect.getsource(main_mod)
