"""DEFAULT_FAXES_PER_PAGE_INBOX (25) and DEFAULT_FAXES_PER_PAGE_ARCHIVE (30) of the original's local_config.php.

They are the page size of a user who has not chosen one (the user's own value is NULL, as in the original's database), and the
start value of the settings and new-user forms. The shortest page a ``pagelimit`` can ask for stays 10.
"""

from __future__ import annotations

import re

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import update

from namifax.common import settings
from namifax.models import FaxArchive, UserAccount
from namifax.services.user_account import NFUserAccount
from test_fax_access_control import _fax, _login, _user, world  # noqa: F401  (same users and helpers)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in ("DEFAULT_FAXES_PER_PAGE_INBOX", "DEFAULT_FAXES_PER_PAGE_ARCHIVE"):
        monkeypatch.delenv(name, raising=False)


# --- the settings ------------------------------------------------------------------------------------------------------------

def test_the_defaults_are_the_originals():
    assert (settings.default_faxes_per_page_inbox(), settings.default_faxes_per_page_archive()) == (25, 30)


@pytest.mark.parametrize("name,reader", [("DEFAULT_FAXES_PER_PAGE_INBOX", settings.default_faxes_per_page_inbox),
                                         ("DEFAULT_FAXES_PER_PAGE_ARCHIVE", settings.default_faxes_per_page_archive)])
def test_a_default_is_set_from_the_environment(monkeypatch, name, reader):
    monkeypatch.setenv(name, "40")
    assert reader() == 40


# --- a user without a page size of their own ----------------------------------------------------------------------------------

def test_a_new_account_has_no_page_size_of_its_own(world):
    user = world.db.get(UserAccount, world.ids["alice"])
    assert (user.faxperpageinbox, user.faxperpagearchive) == (None, None)


def _rows(page):
    return len(re.findall(r'id="faxid_\d+"', page))


@pytest.fixture
def crowd(world, tmp_path):
    world.db.execute(FaxArchive.__table__.delete())
    for n in range(40):
        _fax(world.db, tmp_path, f"in{n}", inbox=1, modemdev="ttyS0")
    for n in range(40):
        _fax(world.db, tmp_path, f"ar{n}", inbox=0, modemdev="ttyS0")
    return world


def test_the_inbox_shows_25_faxes_by_default(crowd):
    assert _rows(_login(crowd, "root").get("/inbox").text) == 25


def test_the_inbox_default_can_be_changed(crowd, monkeypatch):
    monkeypatch.setenv("DEFAULT_FAXES_PER_PAGE_INBOX", "12")
    assert _rows(_login(crowd, "root").get("/inbox").text) == 12


def test_the_users_own_page_size_wins_over_the_default(crowd, monkeypatch):
    crowd.db.execute(update(UserAccount).where(UserAccount.username == "root").values(faxperpageinbox=15))
    monkeypatch.setenv("DEFAULT_FAXES_PER_PAGE_INBOX", "12")
    assert _rows(_login(crowd, "root").get("/inbox").text) == 15


def test_a_page_limit_below_10_is_raised_to_10(crowd):
    assert _rows(_login(crowd, "root").get("/inbox?pagelimit=3").text) == 10


def test_the_archive_shows_30_faxes_by_default(crowd):
    assert _rows(_login(crowd, "root").get("/archive?kw=&opensearch=1&sentrecvd=r").text) == 30


def test_the_archive_default_can_be_changed(crowd, monkeypatch):
    monkeypatch.setenv("DEFAULT_FAXES_PER_PAGE_ARCHIVE", "12")
    assert _rows(_login(crowd, "root").get("/archive?kw=&opensearch=1&sentrecvd=r").text) == 12


# --- the forms ---------------------------------------------------------------------------------------------------------------

def _form_values(client, url):
    form = next(f for f in client.get(url).forms.values() if "faxperpageinbox" in f.fields)
    return form["faxperpageinbox"].value, form["faxperpagearchive"].value


def test_the_settings_form_starts_with_the_defaults_for_a_user_without_a_choice(world):
    assert _form_values(_login(world, "alice"), "/settings") == ("25", "30")


def test_the_new_user_form_follows_the_defaults(world, monkeypatch):
    monkeypatch.setenv("DEFAULT_FAXES_PER_PAGE_INBOX", "50")
    monkeypatch.setenv("DEFAULT_FAXES_PER_PAGE_ARCHIVE", "100")
    assert _form_values(_login(world, "root"), "/admin/users") == ("50", "100")
