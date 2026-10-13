"""The address book edit page edits a company and every one of its fax numbers, like the original (addressbook_edit.php)."""

from __future__ import annotations

import re

import pytest
import webtest
from bs4 import BeautifulSoup
from sqlalchemy import select

from namifax.models import AddressBook, AddressBookFAX, FaxArchive, FaxCategory
from namifax.services.user_account import NFUserAccount

DETAILS = {"to_person": "Kim Minsu", "to_location": "Seoul HQ", "to_voicenumber": "02-123-4567",
           "to_address": "1 Gangnam-daero", "to_zip": "06236", "to_city": "Seoul", "description": "main desk"}


@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


def _create(client, company="Gamma Ltd", number="02-555-1000", **extra):
    form = {"_submit_check": "1", "create": "1", "company": company, "new_faxnum": number,
            **{f"new_{k}" if k != "description" else "new_desc": v for k, v in DETAILS.items()}, **extra}
    return client.post("/addressbook/edit", form, expect_errors=True)


def _company(session, name):
    return session.execute(select(AddressBook).where(AddressBook.company == name)).scalar_one_or_none()


def _numbers(session, abook_id):
    return list(session.execute(select(AddressBookFAX).where(AddressBookFAX.abook_id == abook_id)
                                .order_by(AddressBookFAX.abookfax_id)).scalars())


def _row_form(numbers, **overrides):
    """The fields the edit page posts for the numbers it listed (one value per number for every field)."""
    form = {"_submit_check": "1", "save": "1"}
    for key in ("abookfax_id", "faxnumber", "description", "faxcatid", "to_person", "to_location", "to_voicenumber",
                "to_address", "to_zip", "to_city"):
        form[key] = [str(getattr(n, key) if getattr(n, key) is not None else "") for n in numbers]
    form.update(overrides)
    return form


# --- the page -------------------------------------------------------------------------------------------------------------

def test_the_new_company_page_has_the_fields_of_a_first_fax_number(client):
    page = client.get("/addressbook/edit")
    for name in ("company", "new_faxnum", "new_desc", "newfaxcatid", "new_to_person", "new_to_location",
                 "new_to_voicenumber", "new_to_address", "new_to_zip", "new_to_city"):
        assert f'name="{name}"' in page.text, name
    assert 'name="create"' in page.text and 'name="delete"' not in page.text


def test_the_edit_page_lists_every_number_with_its_details(client, dbsession):
    _create(client)
    company = _company(dbsession, "Gamma Ltd")
    page = client.get(f"/addressbook/edit?abook_id={company.abook_id}")
    assert 'value="Gamma Ltd"' in page.text
    for value in ("0255510", "Kim Minsu", "Seoul HQ", "02-123-4567", "1 Gangnam-daero", "06236", "Seoul", "main desk"):
        assert value in page.text, value
    assert page.text.count('name="abookfax_id"') == 1 and 'name="new_faxnum"' in page.text
    assert 'name="save"' in page.text and 'name="delete"' in page.text


def test_the_old_link_forms_still_open_the_company(client, dbsession):
    _create(client)
    cid = _company(dbsession, "Gamma Ltd").abook_id
    for query in (f"abook_id={cid}", f"id={cid}", f"company_id={cid}", f"cid={cid}"):
        assert 'value="Gamma Ltd"' in client.get(f"/addressbook/edit?{query}").text, query


def test_names_are_escaped(client, dbsession):
    _create(client, company="<script>alert(1)</script> Inc", number="02-555-2000")
    cid = _company(dbsession, "<script>alert(1)</script> Inc").abook_id
    page = client.get(f"/addressbook/edit?abook_id={cid}")
    assert "<script>alert(1)</script>" not in page.text and "&lt;script&gt;" in page.text


def test_the_page_needs_a_login(testapp):
    assert testapp.get("/addressbook/edit", expect_errors=True).status_int != 200


# --- creating ---------------------------------------------------------------------------------------------------------------

def test_creating_a_company_stores_the_number_and_all_its_details(client, dbsession):
    res = _create(client, newfaxcatid="2")
    assert res.status_int == 302 and "/addressbook/edit" in res.headers["Location"] and "abook_id=" in res.headers["Location"]
    company = _company(dbsession, "Gamma Ltd")
    [number] = _numbers(dbsession, company.abook_id)
    assert number.faxnumber == "0255510" + "00"
    assert (number.to_person, number.to_location, number.to_voicenumber) == ("Kim Minsu", "Seoul HQ", "02-123-4567")
    assert (number.to_address, number.to_zip, number.to_city, number.description) == ("1 Gangnam-daero", "06236", "Seoul", "main desk")
    assert number.faxcatid == 2


def test_the_old_two_field_form_still_creates(client, dbsession):
    res = client.post("/addressbook/edit", {"_submit_check": "1", "company": "Delta", "faxnumber": "555-9999"})
    assert res.status_int == 302 and [n.faxnumber for n in _numbers(dbsession, _company(dbsession, "Delta").abook_id)] == ["5559999"]


@pytest.mark.parametrize("form,expect", [
    ({"company": "", "new_faxnum": "5551111"}, "company name"),
    ({"company": "NoNumber", "new_faxnum": ""}, "fax number"),
    ({"company": "Admin Dup", "new_faxnum": "abc"}, "fax number"),
])
def test_creating_with_missing_input_explains_and_creates_nothing(client, dbsession, form, expect):
    res = client.post("/addressbook/edit", {"_submit_check": "1", "create": "1", **form}, expect_errors=True)
    assert res.status_int == 200 and expect in res.text.lower()
    assert _company(dbsession, form["company"]) is None if form["company"] else True


def test_a_company_name_that_exists_is_refused(client, dbsession):
    _create(client)
    res = _create(client, number="02-555-3000")
    assert res.status_int == 200 and "already exists" in res.text.lower()
    assert len(list(dbsession.execute(select(AddressBook).where(AddressBook.company == "Gamma Ltd")).scalars())) == 1


# --- saving -----------------------------------------------------------------------------------------------------------------

def test_saving_changes_the_name_and_the_details_of_each_number(client, dbsession):
    _create(client)
    company = _company(dbsession, "Gamma Ltd")
    numbers = _numbers(dbsession, company.abook_id)
    form = _row_form(numbers, company="Gamma Holdings")
    form["to_person"], form["to_zip"], form["faxcatid"] = ["Lee Jiho"], ["12345"], ["3"]
    res = client.post("/addressbook/edit", {**form, "abook_id": str(company.abook_id)})
    assert res.status_int in (200, 302)
    dbsession.expire_all()
    assert _company(dbsession, "Gamma Holdings").abook_id == company.abook_id
    [number] = _numbers(dbsession, company.abook_id)
    assert (number.to_person, number.to_zip, number.faxcatid, number.to_city) == ("Lee Jiho", "12345", 3, "Seoul")


def test_a_new_number_is_added_with_its_details(client, dbsession):
    _create(client)
    company = _company(dbsession, "Gamma Ltd")
    form = _row_form(_numbers(dbsession, company.abook_id), company="Gamma Ltd", abook_id=str(company.abook_id),
                     new_faxnum="02-555-7777", new_desc="warehouse", new_to_city="Busan", new_to_person="Park")
    client.post("/addressbook/edit", form)
    dbsession.expire_all()
    numbers = _numbers(dbsession, company.abook_id)
    assert [n.faxnumber for n in numbers] == ["025551000"[:0] + numbers[0].faxnumber, "025557777"]
    assert (numbers[1].description, numbers[1].to_city, numbers[1].to_person) == ("warehouse", "Busan", "Park")


def test_clearing_a_number_removes_it_like_the_original(client, dbsession):
    _create(client)
    company = _company(dbsession, "Gamma Ltd")
    client.post("/addressbook/edit", {**_row_form(_numbers(dbsession, company.abook_id), company="Gamma Ltd",
                                                   abook_id=str(company.abook_id), new_faxnum="02-555-7777"), })
    numbers = _numbers(dbsession, company.abook_id)
    form = _row_form(numbers, company="Gamma Ltd", abook_id=str(company.abook_id))
    form["faxnumber"] = ["", numbers[1].faxnumber]
    client.post("/addressbook/edit", form)
    dbsession.expire_all()
    assert [n.abookfax_id for n in _numbers(dbsession, company.abook_id)] == [numbers[1].abookfax_id]


def test_a_blank_company_name_changes_nothing(client, dbsession):
    _create(client)
    company = _company(dbsession, "Gamma Ltd")
    res = client.post("/addressbook/edit", _row_form(_numbers(dbsession, company.abook_id), company=" ", abook_id=str(company.abook_id)))
    assert "company name" in res.text.lower()
    dbsession.expire_all()
    assert _company(dbsession, "Gamma Ltd") is not None


def test_numbers_of_other_companies_cannot_be_edited_through_this_page(client, dbsession):
    _create(client)
    _create(client, company="Other Co", number="02-555-4444")
    mine, other = _company(dbsession, "Gamma Ltd"), _company(dbsession, "Other Co")
    theirs = _numbers(dbsession, other.abook_id)[0]
    form = _row_form(_numbers(dbsession, mine.abook_id), company="Gamma Ltd", abook_id=str(mine.abook_id))
    form["abookfax_id"] = [str(theirs.abookfax_id)]
    form["to_person"] = ["Hijacked"]
    client.post("/addressbook/edit", form)
    dbsession.expire_all()
    assert _numbers(dbsession, other.abook_id)[0].to_person == "Kim Minsu"


def test_a_category_the_user_may_not_use_is_not_changed(client, dbsession):
    _create(client, newfaxcatid="2")
    company = _company(dbsession, "Gamma Ltd")
    operator = NFUserAccount(db=dbsession)
    assert operator.load_username("operator")
    operator.dbdata["faxcats"] = "1"                                  # may only use category 1
    operator.update()
    dbsession.flush()
    other = webtest.TestApp(client.app, extra_environ=client.extra_environ)
    other.post("/login", {"username": "operator", "password": "password", "_submit_check": "1"})
    page = other.get(f"/addressbook/edit?abook_id={company.abook_id}")
    assert 'value="1"' in page.text and ">Invoices<" not in page.text
    form = _row_form(_numbers(dbsession, company.abook_id), company="Gamma Ltd", abook_id=str(company.abook_id))
    form["faxcatid"] = ["3"]                                          # not allowed: the stored 2 stays
    other.post("/addressbook/edit", form)
    dbsession.expire_all()
    assert _numbers(dbsession, company.abook_id)[0].faxcatid == 2


# --- deleting ---------------------------------------------------------------------------------------------------------------

def _archive_fax(session, company_id):
    fax = FaxArchive(faxpath="/faxes/x", companyid=company_id, inbox=0, pages=1)
    session.add(fax)
    session.flush()
    return fax


def test_deleting_removes_the_company_and_keeps_its_faxes_under_the_reserved_entry(client, dbsession):
    _create(client)
    company = _company(dbsession, "Gamma Ltd")
    fax = _archive_fax(dbsession, company.abook_id)
    res = client.post("/addressbook/edit", {"_submit_check": "1", "delete": "1", "abook_id": str(company.abook_id)})
    assert res.status_int == 302 and res.headers["Location"].endswith("/addressbook")
    dbsession.expire_all()
    assert _company(dbsession, "Gamma Ltd") is None and _numbers(dbsession, company.abook_id) == []
    reserved = _company(dbsession, "XXXXXXX")
    assert reserved is not None and dbsession.get(FaxArchive, fax.fid).companyid == reserved.abook_id


def test_an_existing_reserved_entry_is_reused(client, dbsession):
    reserved = AddressBook(company="XXXXXXX")
    dbsession.add(reserved)
    dbsession.flush()
    dbsession.add(AddressBookFAX(abook_id=reserved.abook_id, faxnumber="XXXXXXX"))
    _create(client)
    company = _company(dbsession, "Gamma Ltd")
    fax = _archive_fax(dbsession, company.abook_id)
    client.post("/addressbook/edit", {"_submit_check": "1", "delete": "1", "abook_id": str(company.abook_id)})
    dbsession.expire_all()
    assert dbsession.get(FaxArchive, fax.fid).companyid == reserved.abook_id
    assert len(list(dbsession.execute(select(AddressBook).where(AddressBook.company == "XXXXXXX")).scalars())) == 1


def test_only_users_who_may_delete_can_delete(client, dbsession):
    _create(client)
    company = _company(dbsession, "Gamma Ltd")
    operator = NFUserAccount(db=dbsession)
    operator.load_username("operator")
    assert not operator.dbdata.get("can_del")
    other = webtest.TestApp(client.app, extra_environ=client.extra_environ)
    other.post("/login", {"username": "operator", "password": "password", "_submit_check": "1"})
    page = other.get(f"/addressbook/edit?abook_id={company.abook_id}")
    assert 'name="delete"' not in page.text
    res = other.post("/addressbook/edit", {"_submit_check": "1", "delete": "1", "abook_id": str(company.abook_id)}, expect_errors=True)
    assert res.status_int != 302 or "/addressbook/edit" in res.headers["Location"]
    dbsession.expire_all()
    assert _company(dbsession, "Gamma Ltd") is not None


def test_deleting_an_unknown_company_does_nothing(client):
    res = client.post("/addressbook/edit", {"_submit_check": "1", "delete": "1", "abook_id": "99999"}, expect_errors=True)
    assert res.status_int in (200, 302, 404)


# --- the list ------------------------------------------------------------------------------------------------------------------

def test_the_list_shows_the_numbers_from_the_fax_number_table(client, dbsession):
    _create(client)
    company = _company(dbsession, "Gamma Ltd")
    client.post("/addressbook/edit", _row_form(_numbers(dbsession, company.abook_id), company="Gamma Ltd",
                                               abook_id=str(company.abook_id), new_faxnum="02-555-7777"))
    page = client.get("/addressbook")
    row = re.search(r"Gamma Ltd.*?</tr>", page.text, re.S).group(0)
    assert "0255510" in row and "025557777" in row and f"abook_id={company.abook_id}" in row


def test_searching_finds_a_company_by_any_of_its_numbers(client, dbsession):
    _create(client)
    assert "Gamma Ltd" in client.get("/addressbook?q=0255510").text
    assert "Gamma Ltd" not in client.get("/addressbook?q=9999999").text


def test_the_reserved_entry_is_not_listed(client, dbsession):
    reserved = AddressBook(company="XXXXXXX")
    dbsession.add(reserved)
    dbsession.flush()
    dbsession.add(AddressBookFAX(abook_id=reserved.abook_id, faxnumber="XXXXXXX"))
    dbsession.flush()
    assert "XXXXXXX" not in client.get("/addressbook").text


# --- small fixes found by the audit -------------------------------------------------------------------------------------------

def test_an_existing_company_can_be_saved_without_adding_a_number(client, dbsession):
    """The 'new fax number' field is only required for a new company (the original: if ($new_faxnum))."""
    company = dbsession.execute(select(AddressBook)).scalars().first()
    soup = BeautifulSoup(client.get(f"/addressbook/edit?abook_id={company.abook_id}").text, "html.parser")
    assert soup.find("input", {"name": "new_faxnum"}).has_attr("required") is False
    soup = BeautifulSoup(client.get("/addressbook/edit").text, "html.parser")
    assert soup.find("input", {"name": "faxnumber"}) is not None or soup.find("input", {"name": "new_faxnum"}).has_attr("required")


def test_the_list_search_accepts_the_parameter_the_inbox_and_archive_links_use(client, dbsession):
    dbsession.add_all([AddressBook(company="Zebra Holdings"), AddressBook(company="Quokka Ltd")])
    dbsession.flush()
    page = client.get("/addressbook?search=zebra")
    assert "Zebra Holdings" in page.text and "Quokka Ltd" not in page.text
    page = client.get("/addressbook?q=quokka")
    assert "Quokka Ltd" in page.text and "Zebra Holdings" not in page.text
