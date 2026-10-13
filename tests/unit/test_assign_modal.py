"""Assign: rename a company, or fold it into another (the original assign.php, reached from the inbox sender link)."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import select

from namifax.models import AddressBook, AddressBookFAX, FaxArchive


@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


def _company(session, name, number=None):
    row = AddressBook(company=name)
    session.add(row)
    session.flush()
    if number:
        session.add(AddressBookFAX(abook_id=row.abook_id, faxnumber=number))
        session.flush()
    return row.abook_id


def _form(page):
    return next(f for f in page.forms.values() if "regexp" in f.fields)


def test_the_dialog_remembers_which_company_it_is_for(client, dbsession):
    cid = _company(dbsession, "5551234", "5551234")
    form = _form(client.get(f"/assign?abook_id={cid}"))
    assert form["abook_id"].value == str(cid)


def test_an_unknown_company_goes_back_to_the_inbox(client):
    res = client.get("/assign?abook_id=99999")
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox")


def test_typing_a_name_renames_that_company(client, dbsession):
    cid = _company(dbsession, "5551234", "5551234")
    other = _company(dbsession, "Bystander")
    form = _form(client.get(f"/assign?abook_id={cid}"))
    form["regexp"] = "Proper Name"
    res = form.submit()
    assert res.status_int == 302 or "assigned" in res.text.lower()
    dbsession.expire_all()
    assert dbsession.get(AddressBook, cid).company == "Proper Name" and dbsession.get(AddressBook, other).company == "Bystander"


def test_choosing_another_company_moves_the_numbers_and_the_faxes(client, dbsession):
    old = _company(dbsession, "5551234", "5551234")
    target = _company(dbsession, "Real Corp", "5559999")
    fax = FaxArchive(faxpath="/f/x", companyid=old, inbox=1, pages=1)
    dbsession.add(fax)
    dbsession.flush()
    form = _form(client.get(f"/assign?abook_id={old}"))
    form["myselect"] = str(target)
    form.submit()
    dbsession.expire_all()
    assert dbsession.get(AddressBook, old) is None
    assert {n.faxnumber for n in dbsession.execute(select(AddressBookFAX).where(AddressBookFAX.abook_id == target)).scalars()} == {"5551234", "5559999"}
    assert dbsession.get(FaxArchive, fax.fid).companyid == target


def test_nothing_chosen_says_so_and_changes_nothing(client, dbsession):
    cid = _company(dbsession, "5551234", "5551234")
    res = _form(client.get(f"/assign?abook_id={cid}")).submit()
    assert res.status_int == 200 and "company name" in res.text.lower()
    dbsession.expire_all()
    assert dbsession.get(AddressBook, cid).company == "5551234"
