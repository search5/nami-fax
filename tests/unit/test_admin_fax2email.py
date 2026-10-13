"""Admin > Fax to Email: forwarding address, printer and category are set for each fax number of a company.

(The first version of the page applied one address and one printer to every number of a company, had no category, and
deleted a company without moving its faxes or removing its numbers.)
"""

from __future__ import annotations

import re

import pytest
import webtest
from sqlalchemy import select

from namifax.models import AddressBook, AddressBookFAX, FaxArchive, FaxCategory


@pytest.fixture
def client(testapp, dbsession):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


@pytest.fixture
def company(dbsession):
    """A company with two fax numbers, each with its own personal details (which this page must not touch)."""
    row = AddressBook(company="Omega Corp")
    dbsession.add(row)
    dbsession.flush()
    numbers = [AddressBookFAX(abook_id=row.abook_id, faxnumber=n, to_person=p, email=e, printer=pr)
               for n, p, e, pr in (("0255501", "Kim", "old1@omega.test", "lp1"), ("0255502", "Lee", None, None))]
    dbsession.add_all(numbers)
    dbsession.flush()
    return row, numbers


def _form(row, numbers, **overrides):
    form = {"_submit_check": "1", "save": "1", "abook_id": str(row.abook_id), "company": row.company,
            "abookfax_id": [str(n.abookfax_id) for n in numbers],
            "email": [n.email or "" for n in numbers], "printer": [n.printer or "" for n in numbers],
            "faxcatid": [str(n.faxcatid or "") for n in numbers]}
    form.update(overrides)
    return form


def _reload(session, row):
    session.expire_all()
    return list(session.execute(select(AddressBookFAX).where(AddressBookFAX.abook_id == row.abook_id)
                                .order_by(AddressBookFAX.abookfax_id)).scalars())


# --- the page ------------------------------------------------------------------------------------------------------------

def test_the_list_links_to_each_company(client, company):
    row, _ = company
    page = client.get("/admin/fax2email")
    assert "Omega Corp" in page.text and f"abook_id={row.abook_id}" in page.text


def test_the_selected_company_shows_every_number_with_its_own_settings(client, company, dbsession):
    row, numbers = company
    category = FaxCategory(name="Memo")
    dbsession.add(category)
    dbsession.flush()
    page = client.get(f"/admin/fax2email?abook_id={row.abook_id}")
    assert 'value="Omega Corp"' in page.text
    assert page.text.count('name="abookfax_id"') == 2
    assert page.text.count('name="email"') == 2 and page.text.count('name="printer"') == 2 and page.text.count('name="faxcatid"') == 2
    for number in ("0255501", "0255502", "old1@omega.test", "lp1"):
        assert number in page.text
    assert 'name="save"' in page.text and 'name="delete"' in page.text and 'name="create"' not in page.text
    assert re.search(rf'<option value="{category.catid}"[^>]*>Memo</option>', page.text)     # every category can be chosen


def test_the_old_company_id_parameter_still_works(client, company):
    row, _ = company
    assert 'value="Omega Corp"' in client.get(f"/admin/fax2email?c_id={row.abook_id}").text


def test_only_administrators_can_use_it(client, company):
    row, _ = company
    other = webtest.TestApp(client.app, extra_environ=client.extra_environ)
    other.post("/login", {"username": "operator", "password": "password", "_submit_check": "1"})
    assert other.get("/admin/fax2email", expect_errors=True).status_int == 403
    res = other.post("/admin/fax2email", _form(*company, email=["x@evil.test", "y@evil.test"]), expect_errors=True)
    assert res.status_int == 403


# --- saving --------------------------------------------------------------------------------------------------------------------

def test_each_number_gets_its_own_address_printer_and_category(client, dbsession, company):
    row, numbers = company
    form = _form(row, numbers, email=["one@omega.test", "two@omega.test"], printer=["lp9", ""], faxcatid=["2", "3"])
    res = client.post("/admin/fax2email", form)
    assert res.status_int == 200 and "saved" in res.text.lower()
    first, second = _reload(dbsession, row)
    assert (first.email, first.printer, first.faxcatid) == ("one@omega.test", "lp9", 2)
    assert (second.email, second.printer, second.faxcatid) == ("two@omega.test", "", 3)


def test_the_numbers_and_their_other_details_are_left_alone(client, dbsession, company):
    row, numbers = company
    client.post("/admin/fax2email", _form(row, numbers, email=["a@omega.test", "b@omega.test"]))
    first, second = _reload(dbsession, row)
    assert (first.faxnumber, first.to_person, second.faxnumber, second.to_person) == ("0255501", "Kim", "0255502", "Lee")


def test_the_company_can_be_renamed(client, dbsession, company):
    row, numbers = company
    client.post("/admin/fax2email", _form(row, numbers, company="Omega Holdings"))
    dbsession.expire_all()
    assert dbsession.get(AddressBook, row.abook_id).company == "Omega Holdings"


def test_a_blank_company_name_is_refused(client, dbsession, company):
    row, numbers = company
    res = client.post("/admin/fax2email", _form(row, numbers, company="  ", email=["z@omega.test", "z@omega.test"]))
    assert "company" in res.text.lower() and "enter" in res.text.lower()
    assert _reload(dbsession, row)[0].email == "old1@omega.test"


def test_a_number_of_another_company_cannot_be_changed_here(client, dbsession, company):
    row, numbers = company
    other = AddressBook(company="Other Co")
    dbsession.add(other)
    dbsession.flush()
    theirs = AddressBookFAX(abook_id=other.abook_id, faxnumber="0255599", email="keep@other.test")
    dbsession.add(theirs)
    dbsession.flush()
    client.post("/admin/fax2email", _form(row, numbers, abookfax_id=[str(theirs.abookfax_id)], email=["evil@omega.test"],
                                          printer=[""], faxcatid=[""]))
    dbsession.expire_all()
    assert dbsession.get(AddressBookFAX, theirs.abookfax_id).email == "keep@other.test"


@pytest.mark.parametrize("value", ["a@omega.test", "a@omega.test; b@omega.test", "a@omega.test,b@omega.test", ""])
def test_one_or_several_valid_addresses_are_accepted(client, dbsession, company, value):
    row, numbers = company
    client.post("/admin/fax2email", _form(row, numbers, email=[value, ""]))
    assert (_reload(dbsession, row)[0].email or "") == value


def test_a_changed_invalid_address_is_refused_and_nothing_is_saved(client, dbsession, company):
    row, numbers = company
    res = client.post("/admin/fax2email", _form(row, numbers, company="Renamed", email=["not-an-address", "ok@omega.test"]))
    assert "valid e-mail" in res.text.lower() and "not-an-address" in res.text
    first, second = _reload(dbsession, row)
    assert (first.email, second.email) == ("old1@omega.test", None)
    assert dbsession.get(AddressBook, row.abook_id).company == "Omega Corp"


def test_an_address_that_was_already_odd_does_not_block_other_changes(client, dbsession, company):
    """Data from the original may hold values we would not accept today; only what is changed is checked."""
    row, numbers = company
    numbers[0].email = "legacy odd value"
    dbsession.flush()
    client.post("/admin/fax2email", _form(row, numbers, email=["legacy odd value", "new@omega.test"], printer=["lp5", ""]))
    first, second = _reload(dbsession, row)
    assert (first.email, first.printer, second.email) == ("legacy odd value", "lp5", "new@omega.test")


def test_received_faxes_are_routed_by_the_address_of_their_own_number(client, dbsession, company):
    from namifax.services.addressbook import NFAddressBook

    row, numbers = company
    client.post("/admin/fax2email", _form(row, numbers, email=["one@omega.test", "two@omega.test"], printer=["lp1", "lp2"]))
    book = NFAddressBook(db=dbsession)
    assert book.loadbyfaxnum("0255502")[0] and (book.get_email(), book.get_printer()) == ("two@omega.test", "lp2")
    assert book.loadbyfaxnum("0255501")[0] and book.get_email() == "one@omega.test"


def test_posting_a_new_company_here_creates_nothing(client, dbsession):
    client.post("/admin/fax2email", {"_submit_check": "1", "create": "1", "company": "Sneaky Inc", "email": "x@x.test"})
    assert dbsession.execute(select(AddressBook).where(AddressBook.company == "Sneaky Inc")).first() is None


# --- deleting ------------------------------------------------------------------------------------------------------------------

def test_deleting_moves_the_faxes_to_the_reserved_entry_and_removes_the_numbers(client, dbsession, company):
    row, numbers = company
    fax = FaxArchive(faxpath="/faxes/y", companyid=row.abook_id, inbox=0, pages=1)
    dbsession.add(fax)
    dbsession.flush()
    res = client.post("/admin/fax2email", {"_submit_check": "1", "delete": "1", "abook_id": str(row.abook_id)})
    assert res.status_int == 200
    dbsession.expire_all()
    assert dbsession.get(AddressBook, row.abook_id) is None and _reload(dbsession, row) == []
    reserved = dbsession.execute(select(AddressBook).where(AddressBook.company == "XXXXXXX")).scalar_one()
    assert dbsession.get(FaxArchive, fax.fid).companyid == reserved.abook_id


def test_deleting_an_unknown_company_is_harmless(client):
    res = client.post("/admin/fax2email", {"_submit_check": "1", "delete": "1", "abook_id": "99999"}, expect_errors=True)
    assert res.status_int == 200
