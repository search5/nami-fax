"""Inbox: a fax whose sender number belongs to several address book entries asks which company it is (the original's
``mult_nums`` drop-down that posts to setcompany.php)."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from namifax.models import AddressBook, AddressBookFAX, FaxArchive
from test_fax_access_control import _login, world  # noqa: F401


def _entry(world, company, number, description=None):
    book = AddressBook(company=company)
    world.db.add(book)
    world.db.flush()
    row = AddressBookFAX(abook_id=book.abook_id, faxnumber=number, description=description)
    world.db.add(row)
    world.db.flush()
    return row.abookfax_id


def _fax(world, number="5550100", key="A"):
    fax = world.db.get(FaxArchive, world.fax[key])
    fax.origfaxnum, fax.faxnumid, fax.companyid = number, None, None
    world.db.flush()
    return fax


def _form(page, fid):
    soup = BeautifulSoup(page.text, "html.parser")
    return soup.find("form", {"action": "/setcompany"}, string=None) if False else next(
        (f for f in soup.find_all("form", {"action": "/setcompany"}) if f.find("input", {"name": "fid", "value": str(fid)})), None)


def test_a_number_with_several_companies_offers_a_choice(world):
    first = _entry(world, "Acme", "5550100", "Sales")
    second = _entry(world, "Beta", "5550100")
    _fax(world)
    form = _form(_login(world, "alice").get("/inbox"), world.fax["A"])
    assert form is not None and form["method"].lower() == "post"
    options = {o["value"]: o.get_text(strip=True) for o in form.find("select", {"name": "faxnumid"}).find_all("option")}
    assert options == {str(first): "Acme - Sales", str(second): "Beta"}
    assert form.find("input", {"name": "csrf_token"})["value"]


def test_choosing_one_assigns_the_company_and_the_choice_goes_away(world):
    first = _entry(world, "Acme", "5550100", "Sales")
    _entry(world, "Beta", "5550100")
    _fax(world)
    client = _login(world, "alice")
    page = client.get("/inbox")
    form = next(f for f in page.forms.values() if f.action == "/setcompany" and f["fid"].value == str(world.fax["A"]))
    form["faxnumid"] = str(first)
    res = form.submit()
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox")
    world.db.expire_all()
    assert world.db.get(FaxArchive, world.fax["A"]).faxnumid == first
    assert _form(client.get("/inbox"), world.fax["A"]) is None and "Acme" in client.get("/inbox").text


def test_a_number_with_one_company_has_no_choice(world):
    _entry(world, "Acme", "5550100")
    _fax(world)
    assert _form(_login(world, "alice").get("/inbox"), world.fax["A"]) is None


def test_a_number_nobody_knows_has_no_choice(world):
    _fax(world, "5559999")
    assert _form(_login(world, "alice").get("/inbox"), world.fax["A"]) is None


def test_a_fax_that_already_has_its_company_has_no_choice(world):
    first = _entry(world, "Acme", "5550100")
    _entry(world, "Beta", "5550100")
    fax = _fax(world)
    fax.faxnumid = first
    world.db.flush()
    assert _form(_login(world, "alice").get("/inbox"), world.fax["A"]) is None
