"""Who a received fax is from, as the original inbox shows it (get_company_details + inbox.tpl), and the assignx dialog that
names an unknown sender: an unknown number or the reserved company leads to "assignx", a company that is only the number
leads to "assign", an assigned one to its address book entry."""

from __future__ import annotations

import re

import pytest
from bs4 import BeautifulSoup

from namifax.models import AddressBook, AddressBookFAX, FaxArchive
from namifax.services.addressbook import RESERVED_FAX_NUM
from test_fax_access_control import _login, world  # noqa: F401


def _entry(world, company, number, description=None):
    book = AddressBook(company=company)
    world.db.add(book)
    world.db.flush()
    row = AddressBookFAX(abook_id=book.abook_id, faxnumber=number, description=description)
    world.db.add(row)
    world.db.flush()
    return book.abook_id, row.abookfax_id


def _fax(world, number, faxnumid=None, companyid=None, key="A"):
    fax = world.db.get(FaxArchive, world.fax[key])
    fax.origfaxnum, fax.faxnumid, fax.companyid = number, faxnumid, companyid
    world.db.flush()
    return fax


def _links(world, user="alice"):
    page = _login(world, user).get("/inbox")
    return BeautifulSoup(page.text, "html.parser"), page


def _from_link(soup, fid):
    row = soup.find(id=f"faxid_{fid}") or soup.find(attrs={"data-fid": str(fid)})
    return row


def _hrefs(world, fid, user="alice"):
    soup, _ = _links(world, user)
    cell = soup.find("td", attrs={"data-sender": str(fid)})
    assert cell is not None, "no sender cell for the fax"
    return cell


# --- the inbox shows the sender ---------------------------------------------------------------------------------------------

def test_an_unknown_number_leads_to_assignx(world):
    _fax(world, "5559999")
    cell = _hrefs(world, world.fax["A"])
    link = cell.find("a", href=f"/assignx?fid={world.fax['A']}")
    assert link is not None and "5559999" in link.get_text()


def test_the_reserved_company_leads_to_assignx(world):
    _, numid = _entry(world, RESERVED_FAX_NUM, "5551111")
    _fax(world, "5551111", faxnumid=numid)
    assert _hrefs(world, world.fax["A"]).find("a", href=f"/assignx?fid={world.fax['A']}") is not None


def test_a_company_named_after_its_number_leads_to_assign(world):
    cid, numid = _entry(world, "5552222", "5552222")
    _fax(world, "5552222", faxnumid=numid)
    assert _hrefs(world, world.fax["A"]).find("a", href=f"/assign?abook_id={cid}") is not None


def test_an_assigned_company_leads_to_its_entry_and_shows_the_description(world):
    cid, numid = _entry(world, "Acme", "5553333", "Sales")
    _fax(world, "5553333", faxnumid=numid)
    cell = _hrefs(world, world.fax["A"])
    assert cell.find("a", href=f"/addressbook/edit?abook_id={cid}") is not None
    assert "Acme" in cell.get_text() and "Sales" in cell.get_text()


def test_a_fax_given_a_company_by_assignx_shows_it(world):
    cid, _ = _entry(world, "Zenith", "5554444")
    _fax(world, "5559999", companyid=cid)
    cell = _hrefs(world, world.fax["A"])
    assert "Zenith" in cell.get_text() and cell.find("a", href=f"/assignx?fid={world.fax['A']}") is None


# --- the assignx dialog -------------------------------------------------------------------------------------------------------

def _dialog(client, fid):
    page = client.get(f"/assignx?fid={fid}")
    return page, next(f for f in page.forms.values() if "regexp" in f.fields)


def test_the_dialog_offers_the_companies_and_a_new_name(world):
    cid, _ = _entry(world, "Zenith", "5554444")
    _fax(world, "5559999")
    page, form = _dialog(_login(world, "alice"), world.fax["A"])
    assert form["fid"].value == str(world.fax["A"]) and form["csrf_token"].value
    assert str(cid) in [v for v, _, _ in form["abook_id"].options] and "Zenith" in page.text


def test_choosing_a_company_assigns_it_to_the_fax(world):
    cid, _ = _entry(world, "Zenith", "5554444")
    _fax(world, "5559999")
    client = _login(world, "alice")
    _, form = _dialog(client, world.fax["A"])
    form["abook_id"] = str(cid)
    res = form.submit()
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox")
    world.db.expire_all()
    fax = world.db.get(FaxArchive, world.fax["A"])
    assert fax.companyid == cid and not fax.faxnumid


def test_typing_a_new_name_creates_the_company_and_assigns_it(world):
    _fax(world, "5559999")
    client = _login(world, "alice")
    _, form = _dialog(client, world.fax["A"])
    form["regexp"] = "Brand New Co"
    assert form.submit().status_int == 302
    world.db.expire_all()
    from sqlalchemy import select
    created = world.db.execute(select(AddressBook).where(AddressBook.company == "Brand New Co")).scalar_one()
    assert world.db.get(FaxArchive, world.fax["A"]).companyid == created.abook_id


def test_nothing_chosen_says_so_and_changes_nothing(world):
    _fax(world, "5559999")
    _, form = _dialog(_login(world, "alice"), world.fax["A"])
    res = form.submit()
    assert res.status_int == 200 and "company name" in res.text.lower()
    world.db.expire_all()
    assert world.db.get(FaxArchive, world.fax["A"]).companyid is None


def test_a_user_without_the_right_to_the_fax_cannot_assign(world):
    cid, _ = _entry(world, "Zenith", "5554444")
    _fax(world, "5559999")
    client = _login(world, "alice")
    token = _dialog(client, world.fax["A"])[1]["csrf_token"].value
    bob = _login(world, "bob")
    bob.post("/assignx", {"fid": str(world.fax["A"]), "abook_id": str(cid), "csrf_token": _token_of(bob)}, expect_errors=True)
    world.db.expire_all()
    assert world.db.get(FaxArchive, world.fax["A"]).companyid is None


def _token_of(client):
    return BeautifulSoup(client.get("/inbox").text, "html.parser").find("input", {"name": "csrf_token"})["value"]


@pytest.mark.parametrize("token", [None, "wrong"])
def test_the_post_needs_the_csrf_token(world, token):
    cid, _ = _entry(world, "Zenith", "5554444")
    _fax(world, "5559999")
    data = {"fid": str(world.fax["A"]), "abook_id": str(cid)}
    if token:
        data["csrf_token"] = token
    assert _login(world, "alice").post("/assignx", data, expect_errors=True).status_int == 400
    world.db.expire_all()
    assert world.db.get(FaxArchive, world.fax["A"]).companyid is None


def test_an_unknown_fax_goes_back_to_the_inbox(world):
    res = _login(world, "alice").get("/assignx?fid=99999")
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox")
