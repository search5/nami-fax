"""SHOW_ALL_CONTACTS of the original's local_config.php (on by default).

On, every address book lookup may list all contacts, also for an empty search. Off, a lookup needs a search of at least two
characters, so that a book of thousands of contacts is not loaded on every page.
"""

from __future__ import annotations

import re

import pytest
from bs4 import BeautifulSoup

from namifax.common import settings
from namifax.models import AddressBook, AddressBookFAX


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("SHOW_ALL_CONTACTS", raising=False)


@pytest.fixture
def client(testapp, dbsession):
    for company, number in (("Alpha Co", "+1-555-6000"), ("Beta Ltd", "+1-555-6001")):
        ab = AddressBook(company=company)
        dbsession.add(ab)
        dbsession.flush()
        dbsession.add(AddressBookFAX(abook_id=ab.abook_id, faxnumber=number))
    dbsession.flush()
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


def _companies(res):
    return re.findall(r"<company>(.*?)</company>", res.text)


def _picked(res):
    soup = BeautifulSoup(res.text, "html.parser")
    return sorted(i.find_parent("label").get_text(" ", strip=True) for i in soup.select("input[data-pick]"))


# --- the switch --------------------------------------------------------------------------------------------------------------

def test_all_contacts_are_shown_by_default():
    assert settings.show_all_contacts() is True


@pytest.mark.parametrize("value,expected", [("0", False), ("false", False), ("1", True), ("true", True)])
def test_the_switch_reads_the_environment(monkeypatch, value, expected):
    monkeypatch.setenv("SHOW_ALL_CONTACTS", value)
    assert settings.show_all_contacts() is expected


@pytest.mark.parametrize("query,allowed", [("", False), ("a", False), ("al", True), ("alpha", True)])
def test_without_the_switch_a_lookup_needs_two_characters(monkeypatch, query, allowed):
    monkeypatch.setenv("SHOW_ALL_CONTACTS", "0")
    assert settings.contact_lookup_allowed(query) is allowed


def test_with_the_switch_any_lookup_is_allowed():
    assert settings.contact_lookup_allowed("") is True


# --- the lookups -------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/ajax/book", "/ajax/archivebook"])
def test_an_empty_search_lists_every_company_by_default(client, path):
    assert {"Alpha Co", "Beta Ltd"} <= {c.split(" - ")[0] for c in _companies(client.get(f"{path}?q="))}


@pytest.mark.parametrize("path", ["/ajax/book", "/ajax/archivebook"])
def test_without_the_switch_a_short_search_finds_nothing(client, monkeypatch, path):
    monkeypatch.setenv("SHOW_ALL_CONTACTS", "0")
    assert _companies(client.get(f"{path}?q=")) == []
    assert _companies(client.get(f"{path}?q=a")) == []


@pytest.mark.parametrize("path", ["/ajax/book", "/ajax/archivebook"])
def test_without_the_switch_a_longer_search_still_finds_companies(client, monkeypatch, path):
    monkeypatch.setenv("SHOW_ALL_CONTACTS", "0")
    assert [c.split(" - ")[0] for c in _companies(client.get(f"{path}?q=Alpha"))] == ["Alpha Co"]


def test_the_fax_picker_lists_every_number_by_default(client):
    assert {"Alpha Co - +1-555-6000", "Beta Ltd - +1-555-6001"} <= set(_picked(client.get("/helper/faxcontacts?target=x")))


def test_without_the_switch_the_fax_picker_waits_for_a_search(client, monkeypatch):
    monkeypatch.setenv("SHOW_ALL_CONTACTS", "0")
    assert _picked(client.get("/helper/faxcontacts?target=x")) == []
    assert _picked(client.get("/helper/faxcontacts?target=x&regexp=a")) == []
    assert _picked(client.get("/helper/faxcontacts?target=x&regexp=Alpha")) == ["Alpha Co - +1-555-6000"]
