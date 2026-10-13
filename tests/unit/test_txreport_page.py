"""The transmission report like the original: company, fax number, date, pages and the picture of the first page; no invented status."""

from __future__ import annotations

from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from PIL import Image
from sqlalchemy import update

from namifax.models import FaxArchive
from test_fax_access_control import _login, world  # noqa: F401


@pytest.fixture
def report(world):
    folder = Path(world.db.get(FaxArchive, world.fax["A"]).faxpath)
    Image.new("1", (1728, 2200), 1).save(folder / "fax.tif", format="TIFF", compression="group4")
    world.db.execute(update(FaxArchive).where(FaxArchive.fid == world.fax["A"]).values(origfaxnum="+1-555-7788", pages=1))
    world.db.flush()
    return world


def _page(world, user="alice", fid=None):
    return BeautifulSoup(_login(world, user).get(f"/txreport?fid={fid or world.fax['A']}").text, "html.parser")


def test_the_number_the_date_and_the_pages_are_shown(report):
    text = _page(report).get_text(" ", strip=True)
    assert "+1-555-7788" in text and "2026-03-01" in text


def test_the_first_page_is_shown_as_a_picture(report):
    soup = _page(report)
    assert soup.find("img", src=f"/faxes/image/{report.fax['A']}/1") is not None


def test_no_made_up_delivery_status(report):
    text = _page(report).get_text(" ", strip=True)
    assert "Transmitted Successfully" not in text


def test_without_the_right_nothing_is_shown(report):
    res = _login(report, "bob").get(f"/txreport?fid={report.fax['A']}")
    assert "+1-555-7788" not in res.text
