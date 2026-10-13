"""Distribution lists like the original: members are address-book fax numbers shown as "Company - number", added through a
helper that searches the address book, removed from the list, a list is deleted only by a POST, errors are said."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import select

from namifax.models import AddressBook, AddressBookFAX, DistroList


@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


@pytest.fixture
def book(dbsession):
    """Acme (2 numbers) and Beta (1 number); returns {number: abookfax_id}."""
    ids = {}
    for company, numbers in (("Zeta Co", ["+1-555-0300"]), ("Acme Dist", ["+1-555-0100", "+1-555-0101"])):
        ab = AddressBook(company=company)
        dbsession.add(ab)
        dbsession.flush()
        for number in numbers:
            row = AddressBookFAX(abook_id=ab.abook_id, faxnumber=number)
            dbsession.add(row)
            dbsession.flush()
            ids[number] = row.abookfax_id
    return ids


def _make(client, name="Sales"):
    res = client.post("/distrolist/edit", {"listname": name, "_submit_check": "1"})
    assert res.status_int == 302
    return int(res.headers["Location"].split("dl_id=")[1])


def _members(client, dl_id):
    soup = BeautifulSoup(client.get(f"/distrolist?dl_id={dl_id}").text, "html.parser")
    return [(i["value"], i.find_parent("label").get_text(" ", strip=True)) for i in soup.select('input[name="dl_list[]"]')]


def _add(client, dl_id, *entries):
    return client.post("/helper/distrolist", {"dl_id": str(dl_id), "myselect[]": list(entries), "add": "Add", "_submit_check": "1"})


def test_a_list_is_created_and_shown(client):
    dl_id = _make(client)
    assert "Sales" in client.get(f"/distrolist?dl_id={dl_id}").text


@pytest.mark.parametrize("name,message", [("", "Please enter a list name")])
def test_a_list_needs_a_name(client, name, message):
    res = client.post("/distrolist/edit", {"listname": name, "_submit_check": "1"})
    assert message in res.text


def test_a_list_name_must_be_new(client):
    _make(client)
    res = client.post("/distrolist/edit", {"listname": "Sales", "_submit_check": "1"})
    assert "already exists" in res.text


def test_the_helper_lists_the_fax_numbers_of_the_address_book(client, book):
    dl_id = _make(client)
    soup = BeautifulSoup(client.get(f"/helper/distrolist?dl_id={dl_id}&regexp=Acme+Dist").text, "html.parser")
    options = {o["value"]: o.get_text(strip=True) for o in soup.select('select[name="myselect[]"] option')}
    assert options == {f"{book['+1-555-0100']}|+1-555-0100": "Acme Dist - +1-555-0100",
                       f"{book['+1-555-0101']}|+1-555-0101": "Acme Dist - +1-555-0101"}


def test_added_numbers_show_as_company_dash_number_sorted(client, book):
    dl_id = _make(client)
    _add(client, dl_id, f"{book['+1-555-0300']}|+1-555-0300", f"{book['+1-555-0100']}|+1-555-0100")
    labels = [text for _v, text in _members(client, dl_id)]
    assert labels == ["Acme Dist - +1-555-0100", "Zeta Co - +1-555-0300"]


def test_adding_twice_does_not_duplicate(client, book):
    dl_id = _make(client)
    entry = f"{book['+1-555-0100']}|+1-555-0100"
    _add(client, dl_id, entry)
    _add(client, dl_id, entry)
    assert len(_members(client, dl_id)) == 1


def test_selected_members_are_removed(client, book):
    dl_id = _make(client)
    a, b = f"{book['+1-555-0100']}|+1-555-0100", f"{book['+1-555-0300']}|+1-555-0300"
    _add(client, dl_id, a, b)
    res = client.post("/distrolist/edit", {"dl_id": str(dl_id), "remove": "1", "dl_list[]": [a], "_submit_check": "1"})
    assert res.status_int in (200, 302)
    assert [v for v, _t in _members(client, dl_id)] == [b]


def test_the_list_can_be_renamed(client):
    dl_id = _make(client)
    client.post("/distrolist/edit", {"dl_id": str(dl_id), "listname": "Marketing", "savename": "1", "_submit_check": "1"})
    assert "Marketing" in client.get(f"/distrolist?dl_id={dl_id}").text


def test_a_list_is_deleted_only_by_a_post(client, dbsession):
    dl_id = _make(client)
    client.get(f"/distrolist?dl_id={dl_id}&delete=1")
    dbsession.expire_all()
    assert dbsession.get(DistroList, dl_id) is not None
    res = client.post("/distrolist/edit", {"dl_id": str(dl_id), "delete": "1", "_submit_check": "1"})
    assert res.status_int == 302
    dbsession.expire_all()
    assert dbsession.get(DistroList, dl_id) is None


def test_the_page_has_no_delete_link_that_changes_data(client):
    dl_id = _make(client)
    html = client.get(f"/distrolist?dl_id={dl_id}").text
    assert "delete=1" not in html


def test_the_fax_page_gets_only_the_numbers_of_a_list(client, book):
    dl_id = _make(client)
    _add(client, dl_id, f"{book['+1-555-0100']}|+1-555-0100", f"{book['+1-555-0300']}|+1-555-0300")
    res = client.get(f"/ajax/dlist?dl_id={dl_id}")
    assert sorted(res.text.split("; ")) == ["+1-555-0100", "+1-555-0300"]


def test_a_company_without_a_fax_number_is_not_offered_and_no_number_is_made_up(client, dbsession):
    dbsession.add(AddressBook(company="NoFax Dist"))
    dbsession.flush()
    dl_id = _make(client)
    page = client.get(f"/helper/distrolist?dl_id={dl_id}&regexp=NoFax").text
    assert "NoFax Dist" not in page and "1234567" not in page


def test_an_unknown_list_is_reported_by_the_ajax_call(client):
    assert "Invalid list id" in client.get("/ajax/dlist?dl_id=99999").text
