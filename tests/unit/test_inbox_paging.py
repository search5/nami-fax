"""Inbox paging like the original inbox.php: page size from the user (faxperpageinbox, default 10, never below 10), page links,
"first - last (total faxes)", and a page number past the end shows the last page."""

from __future__ import annotations

import re

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import update

from namifax.models import FaxArchive, UserAccount
from test_fax_access_control import _fax, _login, world  # noqa: F401


@pytest.fixture
def many(world):
    """dan sees ttyS0: 27 faxes (the world's 'A' plus 26 more)."""
    for i in range(26):
        _fax(world.db, __import__("pathlib").Path(world.db.info.setdefault("tmp", __import__("tempfile").mkdtemp())), f"M{i}", modemdev="ttyS0")
    return world


def _page(world, query="", user="dan"):
    soup = BeautifulSoup(_login(world, user).get("/inbox" + query).text, "html.parser")
    fids = [int(c["value"]) for c in soup.find_all("input", {"name": "fids", "type": "checkbox"})]
    return soup, fids


def _set_page_size(world, user, size):
    world.db.execute(update(UserAccount).where(UserAccount.username == user).values(faxperpageinbox=size))
    world.db.flush()


def test_the_default_page_holds_the_users_page_size(many):
    _set_page_size(many, "dan", 10)
    _, fids = _page(many)
    assert len(fids) == 10 and fids == sorted(fids, reverse=True)


def test_a_larger_page_size_is_used(many):
    _set_page_size(many, "dan", 25)
    assert len(_page(many)[1]) == 25


def test_pages_follow_each_other_without_overlap(many):
    _set_page_size(many, "dan", 10)
    first, second, third = (_page(many, f"?pageindex={i}")[1] for i in range(3))
    assert len(first) == len(second) == 10 and len(third) == 7
    assert not set(first) & set(second) and not set(second) & set(third)
    assert max(second) < min(first)


def test_a_page_past_the_end_shows_the_last_page(many):
    _set_page_size(many, "dan", 10)
    assert _page(many, "?pageindex=99")[1] == _page(many, "?pageindex=2")[1]


def test_a_bad_page_number_shows_the_first_page(many):
    _set_page_size(many, "dan", 10)
    assert _page(many, "?pageindex=-4")[1] == _page(many)[1]
    assert _page(many, "?pageindex=abc")[1] == _page(many)[1]


def test_the_page_says_which_faxes_of_how_many(many):
    _set_page_size(many, "dan", 10)
    soup, _ = _page(many, "?pageindex=1")
    text = soup.get_text(" ", strip=True)
    assert re.search(r"11\s*-\s*20\s*\(\s*27\s*faxes?", text, re.I), text[:400]


def test_page_links_are_offered_only_when_there_is_more_than_one_page(many):
    _set_page_size(many, "dan", 10)
    soup, _ = _page(many, "?pageindex=1")
    hrefs = [a["href"] for a in soup.select("nav.paging a")]
    assert "/inbox?pageindex=0" in hrefs and "/inbox?pageindex=2" in hrefs
    _set_page_size(many, "dan", 100)
    assert _page(many)[0].select("nav.paging") == []


def test_the_page_limit_can_be_given_in_the_address_but_not_below_ten(many):
    _set_page_size(many, "dan", 10)
    assert len(_page(many, "?pageindex=0&pagelimit=15")[1]) == 15
    assert len(_page(many, "?pageindex=0&pagelimit=3")[1]) == 10


def test_the_unread_counter_counts_every_fax_not_just_the_page(many):
    _set_page_size(many, "dan", 10)
    assert _login(many, "dan").get("/ajax/inbox").text.strip() == "27"
