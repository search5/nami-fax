"""Send Fax page widgets of the original: the cover page options fold away with the cover page switch, several files are collected in a
list the user can remove from (the original's MultiSelector)."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup


@pytest.fixture
def soup(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return BeautifulSoup(testapp.get("/sendfax").text, "html.parser"), testapp


def test_the_cover_options_sit_in_a_folding_block_tied_to_the_switch(soup):
    page, _ = soup
    block = page.find(id="coverpagediv")
    assert block is not None and block.find("select", {"name": "whichcover"}) and block.find("textarea", {"name": "comments"})
    switch = page.find("input", {"name": "coverpage"})
    assert switch["data-folds"] == "coverpagediv"


def test_the_cover_block_starts_open_because_the_switch_starts_on(soup):
    page, _ = soup
    assert page.find("input", {"name": "coverpage"}).has_attr("checked")
    assert "hidden" not in (page.find(id="coverpagediv").get("class") or [])      # the script folds it when the switch is turned off


def test_the_file_picker_collects_several_files_in_a_list(soup):
    page, _ = soup
    picker = page.find("input", {"type": "file"})
    assert picker.has_attr("multiple") and picker["data-list"] == "files_list"
    assert page.find(id="files_list") is not None
    assert picker.get("data-max-bytes", "").isdigit()


def test_the_widget_script_is_served_and_loaded(soup):
    page, client = soup
    assert any(s.get("src") == "/static/js/sendfax.js" for s in page.find_all("script"))
    body = client.get("/static/js/sendfax.js").body
    assert b"data-folds" in body and b"DataTransfer" in body
