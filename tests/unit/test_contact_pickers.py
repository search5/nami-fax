"""The contact pickers of the original: fax numbers (Company - number), distribution lists and e-mail contacts open in a small window,
filter as you type, and put the chosen entries into the field that opened them; the Send Fax and e-mail pages offer them."""

from __future__ import annotations

import re

import pytest
from bs4 import BeautifulSoup

from namifax.models import AddressBook, AddressBookFAX, AddressBookEmail
from test_fax_access_control import _login, world  # noqa: F401


@pytest.fixture
def book(dbsession):
    for company, numbers in (("Picker Co", ["+1-555-4000", "+1-555-4001"]), ("Other Ltd", ["+1-555-5000"])):
        ab = AddressBook(company=company)
        dbsession.add(ab)
        dbsession.flush()
        for n in numbers:
            dbsession.add(AddressBookFAX(abook_id=ab.abook_id, faxnumber=n))
    dbsession.add(AddressBookEmail(contact_name="Pat Picker", contact_email="pat@picker.test"))
    dbsession.flush()


@pytest.fixture
def client(testapp, book):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


def _items(res):
    soup = BeautifulSoup(res.text, "html.parser")
    return {i["value"]: i.find_parent("label").get_text(" ", strip=True) for i in soup.select("input[data-pick]")}, soup


def test_the_fax_picker_lists_numbers_as_company_dash_number(client):
    items, _ = _items(client.get("/helper/faxcontacts?target=faxnumber&regexp=Picker"))
    assert sorted(items.values()) == ["Picker Co - +1-555-4000", "Picker Co - +1-555-4001"]
    assert sorted(items) == ["+1-555-4000", "+1-555-4001"]


def test_the_picker_knows_which_field_to_fill(client):
    _, soup = _items(client.get("/helper/faxcontacts?target=faxnumber&regexp=Picker"))
    assert soup.find("body")["data-target"] == "faxnumber" and soup.find("body")["data-separator"] == "; "


def test_the_target_cannot_carry_script(client):
    _, soup = _items(client.get('/helper/faxcontacts?target=x"><script>alert(1)</script>&regexp=Picker'))
    assert "<script>alert" not in str(soup)
    assert soup.find("body")["data-target"] == ""


def test_the_email_picker_lists_contacts(client):
    items, soup = _items(client.get("/helper/emailcontacts?target=emails&regexp=Pat"))
    assert list(items) == ['"Pat Picker" <pat@picker.test>'] and soup.find("body")["data-separator"] == ", "


def test_the_group_picker_lists_the_lists_and_fetches_their_numbers(client):
    client.post("/distrolist/edit", {"listname": "Everyone", "_submit_check": "1"})
    soup = BeautifulSoup(client.get("/helper/distrocontacts?target=faxnumber").text, "html.parser")
    assert soup.find("body")["data-fetch"] == "/ajax/dlist?dl_id="
    assert any("Everyone" in l.get_text() for l in soup.select("label"))


def test_a_search_with_no_match_says_so(client):
    assert "No contacts found" in client.get("/helper/faxcontacts?target=faxnumber&regexp=zzzz").text


def test_the_send_fax_page_offers_the_pickers(client):
    html = client.get("/sendfax").text
    assert "/helper/faxcontacts?target=faxnumber" in html and "/helper/distrocontacts?target=faxnumber" in html


def test_the_email_dialog_offers_the_picker(world):
    html = _login(world, "alice").get(f"/email?fid={world.fax['A']}").text
    assert "/helper/emailcontacts?target=emails" in html


def test_a_fax_number_carries_its_id_so_the_cover_fields_can_be_filled(client):
    soup = BeautifulSoup(client.get("/helper/faxcontacts?target=faxnumber&regexp=Other").text, "html.parser")
    box = soup.select_one("input[data-pick]")
    assert box["data-fnid"].isdigit() and soup.find("body")["data-prefill"] == "1"


def test_the_prefill_answer_has_the_cover_page_fields(client, dbsession):
    from sqlalchemy import select

    number = dbsession.execute(select(AddressBookFAX).where(AddressBookFAX.faxnumber == "+1-555-5000")).scalar_one()
    number.to_person = "Olga"
    dbsession.flush()
    res = client.get(f"/ajax/prefillto?fnid={number.abookfax_id}")
    assert "<to_person>Olga</to_person>" in res.text and "<to_company>Other Ltd</to_company>" in res.text
