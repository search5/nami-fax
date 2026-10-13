"""SENDFAX_USE_COVERPAGE and SENDFAX_REQUEUE_EMAIL of the original's local_config.php (both on by default).

They only decide how the Send Fax form starts: whether the cover page switch is on (its options fold away when off) and whether
"notify on retry" is ticked. What the user submits always wins.
"""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from namifax.common import settings
from test_fax_access_control import _login, world  # noqa: F401  (same users and faxes)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in ("SENDFAX_USE_COVERPAGE", "SENDFAX_REQUEUE_EMAIL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


def _form(client, url="/sendfax"):
    page = BeautifulSoup(client.get(url).text, "html.parser")
    return (page.find("input", {"name": "coverpage"}).has_attr("checked"),
            page.find("input", {"name": "notify_requeue"}).has_attr("checked"),
            "hidden" in (page.find(id="coverpagediv").get("class") or []))


# --- the switches ------------------------------------------------------------------------------------------------------------

def test_both_defaults_are_on_like_the_original():
    assert settings.sendfax_use_coverpage() is True
    assert settings.sendfax_requeue_email() is True


@pytest.mark.parametrize("name,reader", [("SENDFAX_USE_COVERPAGE", settings.sendfax_use_coverpage),
                                         ("SENDFAX_REQUEUE_EMAIL", settings.sendfax_requeue_email)])
def test_a_default_is_set_from_the_environment(monkeypatch, name, reader):
    monkeypatch.setenv(name, "0")
    assert reader() is False
    monkeypatch.setenv(name, "1")
    assert reader() is True


# --- the form ----------------------------------------------------------------------------------------------------------------

def test_the_form_starts_with_the_cover_page_on_and_retry_notice_ticked(client):
    assert _form(client) == (True, True, False)


def test_the_cover_page_can_start_off_and_its_options_start_folded(client, monkeypatch):
    monkeypatch.setenv("SENDFAX_USE_COVERPAGE", "0")
    assert _form(client) == (False, True, True)


def test_the_retry_notice_can_start_unticked(client, monkeypatch):
    monkeypatch.setenv("SENDFAX_REQUEUE_EMAIL", "0")
    assert _form(client) == (True, False, False)


def test_a_reply_form_follows_the_same_defaults(world, monkeypatch):
    monkeypatch.setenv("SENDFAX_USE_COVERPAGE", "0")
    monkeypatch.setenv("SENDFAX_REQUEUE_EMAIL", "0")
    page = BeautifulSoup(_login(world, "alice").get(f"/sendfax?refax={world.fax['A']}").text, "html.parser")
    assert not page.find("input", {"name": "coverpage"}).has_attr("checked")
    assert not page.find("input", {"name": "notify_requeue"}).has_attr("checked")
    assert "hidden" in (page.find(id="coverpagediv").get("class") or [])


def test_what_the_user_submitted_wins_when_the_form_comes_back_with_an_error(client):
    page = BeautifulSoup(client.post("/sendfax", {"_submit_check": "1", "faxnumber": ""}).text, "html.parser")
    assert not page.find("input", {"name": "coverpage"}).has_attr("checked")        # both boxes were left unticked
    assert not page.find("input", {"name": "notify_requeue"}).has_attr("checked")
    assert "hidden" in (page.find(id="coverpagediv").get("class") or [])
