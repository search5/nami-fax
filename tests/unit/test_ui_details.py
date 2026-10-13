"""Small things of the original's screens: the address book's sub-menu, the full name (and superuser mark) in the header, and the line
or DID group a received fax came in on."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import update

from namifax.models import FaxArchive
from test_fax_access_control import _login, world  # noqa: F401


def test_the_address_book_has_the_submenu(world):
    soup = BeautifulSoup(_login(world, "alice").get("/addressbook").text, "html.parser")
    hrefs = [a["href"] for a in soup.select("nav.book-menu a")]
    assert hrefs == ["/emailbook", "/addressbook", "/distrolist"]


def test_the_header_shows_the_full_name_and_marks_a_superuser(world):
    alice = BeautifulSoup(_login(world, "alice").get("/inbox").text, "html.parser")
    assert "Alice" in alice.get_text() and alice.select("[data-superuser]") == []
    root = BeautifulSoup(_login(world, "root").get("/inbox").text, "html.parser")
    assert "Root" in root.get_text() and root.select("[data-superuser]")


def test_an_inbox_row_names_the_line_it_came_in_on(world):
    soup = BeautifulSoup(_login(world, "alice").get("/inbox").text, "html.parser")
    cells = soup.select(f'[data-line-of="{world.fax["A"]}"]')
    assert cells and "ttyS0" in cells[0].get_text()


def test_lists_filter_as_you_type(world):
    client = _login(world, "alice")
    for path, target in (("/addressbook", "#contact-table"), ("/emailbook", "#email-table")):
        html = client.get(path).text
        assert f'data-live-filter="{target}"' in html and f'id="{target[1:]}"' in html, path
        assert "/static/js/livefilter.js" in html
    assert "/static/js/livefilter.js" in client.get("/distrolist").text
    assert client.get("/static/js/livefilter.js").status_int == 200
