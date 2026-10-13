"""WHITEPAGES of the original's local_config.php: the Assign Company window offers a look-up of the number in the White Pages
when the company is only a number (a name made of digits only, as the original's assign.php decides)."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from namifax.common import settings
from namifax.models import AddressBook

DEFAULT = "http://www.whitepages.com/search/ReversePhone?full_phone="


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("WHITEPAGES", raising=False)


@pytest.fixture
def client(testapp, dbsession):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


def _company(db, name):
    row = AddressBook(company=name)
    db.add(row)
    db.flush()
    return row.abook_id


def _link(client, abook_id):
    soup = BeautifulSoup(client.get(f"/assign?abook_id={abook_id}").text, "html.parser")
    return soup.find("a", attrs={"data-whitepages": True})


# --- the setting -------------------------------------------------------------------------------------------------------------

def test_the_default_is_the_us_white_pages():
    assert settings.whitepages_url() == DEFAULT


def test_the_address_can_be_changed(monkeypatch):
    monkeypatch.setenv("WHITEPAGES", "http://www.paginebianche.it/execute.cgi?btt=1&tl=2&tr=106&qs=")
    assert settings.whitepages_url().endswith("&qs=")


# --- the window --------------------------------------------------------------------------------------------------------------

def test_a_company_that_is_only_a_number_gets_the_look_up(client, dbsession):
    link = _link(client, _company(dbsession, "5551234567"))
    assert link is not None and link["href"] == DEFAULT + "5551234567"
    assert link["target"] == "_blank" and "noopener" in link["rel"]
    assert link.find("img")["src"] == "/static/images/pb.gif" and link["title"] == "Search the White Pages"


@pytest.mark.parametrize("name", ["Acme Corp", "555-1234", "+15551234", "5551234 Ltd", "５５５"])
def test_a_company_with_anything_but_digits_gets_none(client, dbsession, name):
    assert _link(client, _company(dbsession, name)) is None


def test_the_configured_address_is_used_and_escaped(client, dbsession, monkeypatch):
    monkeypatch.setenv("WHITEPAGES", "http://wp.example/q?a=1&b=2&n=")
    html = client.get(f"/assign?abook_id={_company(dbsession, '5550100')}").text
    assert 'href="http://wp.example/q?a=1&amp;b=2&amp;n=5550100"' in html
