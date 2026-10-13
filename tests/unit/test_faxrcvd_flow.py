"""faxrcvd against a real database: the sender is looked up or registered in the address book and the fax is archived."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import select

from namifax.cli import faxrcvd as mod
from namifax.models import AddressBook, AddressBookFAX, FaxArchive


def _receive(tmp_path, session, sender="Newco Ltd", number="5557777", received="2026:10:01 10:05:09", **info):
    tiff = tmp_path / "fax00123.tif"
    tiff.write_bytes(b"mock tiff")
    finfo = {"Sender": sender, "Pages": "2", "Received": received, "CallID1": number, "CallID2": "<NONE>", "CallID3": "<NONE>"}
    finfo.update(info)
    with patch.object(mod, "ARCHIVE", str(tmp_path / "archive")), \
            patch.object(mod, "faxinfo", return_value=finfo), \
            patch.object(mod, "tiff2pdf"), patch.object(mod, "static_preview"), patch.object(mod, "send_mail"), \
            patch.object(mod, "bardecode", return_value=None), patch.object(mod, "ocr_faxcontent", return_value=""):
        return mod.run_faxrcvd(["faxrcvd.py", str(tiff), "ttyS0", "comm01", "none"], session=session)


def _book(session, company):
    return session.execute(select(AddressBook).where(AddressBook.company == company)).scalar_one_or_none()


def _number(session, number):
    return list(session.execute(select(AddressBookFAX).where(AddressBookFAX.faxnumber == number)).scalars())


def _archived(session):
    return session.execute(select(FaxArchive).order_by(FaxArchive.fid.desc())).scalars().first()


def test_a_new_sender_is_registered_and_the_fax_is_linked_to_it(tmp_path, dbsession):
    assert _receive(tmp_path, dbsession) == 0
    company = _book(dbsession, "Newco Ltd")
    numbers = _number(dbsession, "5557777")
    assert company is not None and len(numbers) == 1 and numbers[0].abook_id == company.abook_id
    fax = _archived(dbsession)
    # like the original, the fax points at the fax number; its company is found through the number
    assert (fax.faxnumid, fax.inbox, fax.pages, fax.modemdev) == (numbers[0].abookfax_id, 1, 2, "ttyS0")


def test_the_receive_time_is_stored_as_an_iso_timestamp(tmp_path, dbsession):
    _receive(tmp_path, dbsession)
    assert _archived(dbsession).archstamp == "2026-10-01 10:05:09"


def test_a_known_number_is_reused_and_counted(tmp_path, dbsession):
    _receive(tmp_path, dbsession)
    first = _number(dbsession, "5557777")[0]
    before = first.faxfrom or 0
    _receive(tmp_path, dbsession, received="2026:10:02 08:00:00")
    assert len(_number(dbsession, "5557777")) == 1 and len(list(dbsession.execute(
        select(AddressBook).where(AddressBook.company == "Newco Ltd")).scalars())) == 1
    dbsession.refresh(first)
    assert (first.faxfrom or 0) == before + 1 or (first.faxfrom or 0) > before
    assert _archived(dbsession).faxnumid == first.abookfax_id


def test_an_existing_company_gets_the_new_number_instead_of_a_duplicate(tmp_path, dbsession):
    dbsession.add(AddressBook(company="Newco Ltd"))
    dbsession.flush()
    existing = _book(dbsession, "Newco Ltd")
    _receive(tmp_path, dbsession)
    assert len(list(dbsession.execute(select(AddressBook).where(AddressBook.company == "Newco Ltd")).scalars())) == 1
    assert _number(dbsession, "5557777")[0].abook_id == existing.abook_id
    assert _archived(dbsession).faxnumid == _number(dbsession, "5557777")[0].abookfax_id


def test_a_number_shared_by_several_companies_is_flagged_not_guessed(tmp_path, dbsession, capsys):
    a, b = AddressBook(company="Alpha"), AddressBook(company="Beta")
    dbsession.add_all([a, b])
    dbsession.flush()
    dbsession.add_all([AddressBookFAX(abook_id=a.abook_id, faxnumber="5558888"), AddressBookFAX(abook_id=b.abook_id, faxnumber="5558888")])
    dbsession.flush()
    _receive(tmp_path, dbsession, sender="Whoever", number="5558888")
    assert "Multiple results" in capsys.readouterr().out
    assert not _archived(dbsession).faxnumid                   # 0: the fax is archived without a guess


def test_a_fax_with_no_caller_id_uses_the_sender_name(tmp_path, dbsession):
    _receive(tmp_path, dbsession, sender="5559191", number="<NONE>")
    assert len(_number(dbsession, "5559191")) == 1
