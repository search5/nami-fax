"""A sent fax to a new number registers the receiver in the address book (company, number, to_person/location/voice) and the
sent fax carries that company (the original notify.php); a number of several companies leaves the fax unassigned."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import select

from namifax.cli.notify import run_notify
from namifax.models import AddressBook, AddressBookFAX, FaxArchive


def _qfile(tmp_path, number="5559001", extra=""):
    q = tmp_path / "q1"
    q.write_text(f"totpages:2\nstatus:Normal\nexternal:{number}\njobid:77\nmailaddr:admin@example.com\nowner:admin\n"
                 f"company:Receiver Inc\nreceiver:Rita\nlocation:Paris\nvoice:+33-1\npostscript:0:0:/tmp/doc.ps\n{extra}")
    return str(q)


@pytest.fixture
def notified(dbsession, tmp_path, monkeypatch):
    monkeypatch.setattr("namifax.cli.notify.TMPDIR", str(tmp_path) + "/")
    monkeypatch.setattr("namifax.cli.notify.ARCHIVE_SENT", str(tmp_path / "sent"))

    def fake_pdf(folder, files):
        import os
        os.makedirs(folder, exist_ok=True)
        open(os.path.join(folder, "fax.pdf"), "wb").write(b"%PDF-1.4")
        return True

    with patch("namifax.cli.notify.send_mail"), patch("namifax.cli.notify.convert2pdf", side_effect=fake_pdf), \
            patch("namifax.cli.notify.pdf_preview"):
        yield lambda q: run_notify(["notify.py", q, "done", "00:01:00"], session=dbsession)


def test_a_new_number_creates_the_company_and_the_number(notified, dbsession, tmp_path):
    assert notified(_qfile(tmp_path)) == 0
    company = dbsession.execute(select(AddressBook).where(AddressBook.company == "Receiver Inc")).scalar_one()
    number = dbsession.execute(select(AddressBookFAX).where(AddressBookFAX.faxnumber == "5559001")).scalar_one()
    assert number.abook_id == company.abook_id
    assert (number.to_person, number.to_location, number.to_voicenumber) == ("Rita", "Paris", "+33-1")
    assert number.faxto == 1


def test_the_sent_fax_carries_the_company(notified, dbsession, tmp_path):
    notified(_qfile(tmp_path))
    company = dbsession.execute(select(AddressBook).where(AddressBook.company == "Receiver Inc")).scalar_one()
    sent = dbsession.execute(select(FaxArchive).where(FaxArchive.inbox == 0).order_by(FaxArchive.fid.desc())).scalars().first()
    assert sent.companyid == company.abook_id


def test_a_known_number_is_counted_again(notified, dbsession, tmp_path):
    notified(_qfile(tmp_path))
    notified(_qfile(tmp_path))
    number = dbsession.execute(select(AddressBookFAX).where(AddressBookFAX.faxnumber == "5559001")).scalar_one()
    assert number.faxto == 2


def test_a_number_of_several_companies_leaves_the_fax_unassigned(notified, dbsession, tmp_path):
    for name in ("Co One", "Co Two"):
        ab = AddressBook(company=name)
        dbsession.add(ab)
        dbsession.flush()
        dbsession.add(AddressBookFAX(abook_id=ab.abook_id, faxnumber="5559002"))
    dbsession.flush()
    notified(_qfile(tmp_path, number="5559002"))
    sent = dbsession.execute(select(FaxArchive).where(FaxArchive.inbox == 0).order_by(FaxArchive.fid.desc())).scalars().first()
    assert not sent.companyid
