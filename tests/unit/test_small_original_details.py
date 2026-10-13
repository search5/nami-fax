"""Remaining small things of the original: the TIFF download only with ENABLE_DL_TIFF, the server name (SHOWSERVER_DETAILS), access keys,
a print style, month names in the system log, TSI for superusers only in the settings, and a real thumbnail for sent faxes."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from PIL import Image
from sqlalchemy import select, update

from namifax.models import FaxArchive, UserAccount
from test_fax_access_control import _login, world  # noqa: F401


# --- TIFF download ----------------------------------------------------------------------------------------------------------

def _tiffed(world):
    folder = Path(world.db.get(FaxArchive, world.fax["A"]).faxpath)
    Image.new("1", (200, 300), 1).save(folder / "fax.tif", format="TIFF", compression="group4")
    return world.fax["A"]


def test_no_tiff_link_unless_enabled(world, monkeypatch):
    monkeypatch.delenv("ENABLE_DL_TIFF", raising=False)
    fid = _tiffed(world)
    client = _login(world, "alice")
    assert "format=tiff" not in client.get(f"/viewfax?fid={fid}").text and "format=tiff" not in client.get("/inbox").text
    assert client.get(f"/faxes/download/{fid}?format=tiff", expect_errors=True).status_int == 404


def test_the_tiff_link_and_download_with_the_setting(world, monkeypatch):
    monkeypatch.setenv("ENABLE_DL_TIFF", "1")
    fid = _tiffed(world)
    client = _login(world, "alice")
    assert "format=tiff" in client.get(f"/viewfax?fid={fid}").text and "format=tiff" in client.get("/inbox").text
    assert client.get(f"/faxes/download/{fid}?format=tiff").status_int == 200


@pytest.mark.parametrize("fmt", ["tiff\r\nX-Evil: 1", 'x"; filename="evil', "exe", "PDF ", "tif/../x", ""])
def test_the_download_format_is_checked_against_a_list(world, monkeypatch, fmt):
    """R4Z-02: with ENABLE_DL_TIFF on, only pdf, tif and tiff are served; anything else is refused, never put in a header."""
    monkeypatch.setenv("ENABLE_DL_TIFF", "1")
    fid = _tiffed(world)
    res = _login(world, "alice").get(f"/faxes/download/{fid}", params={"format": fmt}, expect_errors=True)
    assert res.status_int in (400, 404)
    assert "X-Evil" not in res.headers and "evil" not in res.headers.get("Content-Disposition", "")


@pytest.mark.parametrize("fid", ["abc", "1;2", "-1", "1%0d%0aX-Evil:%201", "1.5"])
def test_the_download_fid_must_be_a_whole_number(world, fid):
    res = _login(world, "alice").get(f"/faxes/download/{fid}", expect_errors=True)
    assert res.status_int in (400, 404) and "X-Evil" not in res.headers


def test_the_download_header_is_built_from_the_checked_values(world, monkeypatch):
    monkeypatch.setenv("ENABLE_DL_TIFF", "1")
    fid = _tiffed(world)
    res = _login(world, "alice").get(f"/faxes/download/{fid}?format=tif")
    assert res.headers["Content-Disposition"] == f'inline; filename="fax_{fid}.tif"'
    assert res.headers["Content-Type"].startswith("image/tiff")


# --- header ------------------------------------------------------------------------------------------------------------------

def test_the_server_name_is_shown_when_asked(world, monkeypatch):
    monkeypatch.setenv("SHOWSERVER_DETAILS", "1")
    monkeypatch.setenv("AVANTFAX_SERVERNAME", "fax-hq-01")
    assert "fax-hq-01" in _login(world, "alice").get("/inbox").text
    monkeypatch.setenv("SHOWSERVER_DETAILS", "0")
    assert "fax-hq-01" not in _login(world, "alice").get("/inbox").text


def test_the_menu_has_the_original_access_keys(world):
    soup = BeautifulSoup(_login(world, "alice").get("/inbox").text, "html.parser")
    keys = {a["href"]: "".join(a["accesskey"]) for a in soup.find_all("a", accesskey=True)}
    assert keys.get("/inbox") == "i" and keys.get("/sendfax") == "s" and keys.get("/outbox") == "o" and keys.get("/addressbook") == "c"
    assert keys.get("/settings") == "p"


def test_there_is_a_print_style_that_hides_the_chrome(world):
    html = _login(world, "alice").get("/inbox").text
    assert '<style media="print">' in html and ".print-hide" in html


# --- system log months -----------------------------------------------------------------------------------------------------

def test_the_log_month_list_has_names(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    soup = BeautifulSoup(testapp.get("/admin/system_logs").text, "html.parser")
    options = [(o["value"], o.get_text(strip=True)) for o in soup.find("select", {"name": "month"}).find_all("option") if o["value"]]
    assert options[0] == ("01", "January") and options[11] == ("12", "December")


# --- settings: TSI -----------------------------------------------------------------------------------------------------------

def test_tsi_is_only_for_superusers_in_the_settings(world):
    assert BeautifulSoup(_login(world, "alice").get("/settings").text, "html.parser").find("input", {"name": "user_tsi"}) is None
    assert BeautifulSoup(_login(world, "root").get("/settings").text, "html.parser").find("input", {"name": "user_tsi"}) is not None


def test_a_user_cannot_set_tsi_by_posting_it(world):
    client = _login(world, "alice")
    form = next(f for f in client.get("/settings").forms.values() if "faxperpageinbox" in f.fields)
    res = client.post("/settings", dict(form.submit_fields(), user_tsi="EVIL"))
    world.db.expire_all()
    assert world.db.execute(select(UserAccount.user_tsi).where(UserAccount.username == "alice")).scalar() != "EVIL"


# --- thumbnail of a sent fax -----------------------------------------------------------------------------------------------

def test_a_sent_fax_gets_a_real_thumbnail_from_its_pdf(tmp_path, monkeypatch):
    from namifax.common.helpers import pdf_preview

    gs = tmp_path / "fakegs"
    gs.write_text("#!/bin/sh\nfor a in \"$@\"; do case \"$a\" in -sOutputFile=*) out=\"${a#-sOutputFile=}\";; esac; done\n"
                  "python3 - \"$out\" <<'PY'\nimport sys\nfrom PIL import Image\n"
                  "for n in (1, 2):\n    Image.new('L', (600, 800), 128).save(sys.argv[1].replace('%d', str(n)))\nPY\n")
    gs.chmod(gs.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("GS", str(gs))
    folder = tmp_path / "sent"
    folder.mkdir()
    (folder / "fax.pdf").write_bytes(b"%PDF-1.4")
    assert pdf_preview(str(folder)) is True
    assert Image.open(folder / "thumb.png").width == 80
    assert Image.open(folder / "page0.png").width == 600 and (folder / "page1.png").exists()
