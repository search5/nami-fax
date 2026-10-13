"""Send Fax rules of the original sendfax.php: the lines a user may use, 'any line' only with any_modem, the allowed file
types and size, priority and TSI for superusers only, and the job number shown after sending."""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import update

from namifax.models import UserAccount
from test_fax_access_control import _login, world  # noqa: F401
from test_sendfax_refax import sent  # noqa: F401


def _page(world, user):
    return BeautifulSoup(_login(world, user).get("/sendfax").text, "html.parser")


def _options(world, user):
    select = _page(world, user).find("select", {"name": "modem"})
    return [o["value"] for o in select.find_all("option")] if select else None


def _post(client, upload=None, **fields):
    data = {"faxnumber": "5551234", "_submit_check": "1", **fields}
    files = [("file", upload[0], upload[1])] if upload else []
    return client.post("/sendfax", data, upload_files=files)


# --- lines ------------------------------------------------------------------------------------------------------------------

def test_a_user_is_offered_only_their_own_lines(world):
    assert _options(world, "alice") in (["ttyS0"], None)               # a single line needs no choice
    assert "ttyS1" not in str(_page(world, "alice"))


def test_any_line_is_offered_only_with_the_any_modem_right(world):
    world.db.execute(update(UserAccount).where(UserAccount.username == "alice").values(any_modem=1))
    world.db.flush()
    values = _options(world, "alice")
    assert values is not None and "" in values and "ttyS0" in values


def test_a_superuser_is_offered_every_line(world):
    values = _options(world, "root")
    assert values is not None and {"ttyS0", "ttyS1"} <= set(values)


def test_a_line_that_is_not_theirs_is_refused(world, sent):
    res = _post(_login(world, "alice"), upload=("a.txt", b"hello"), modem="ttyS1")
    assert "may not use this line" in res.text and sent == []


def test_a_user_without_lines_cannot_send(world, sent):
    page = _login(world, "carl").get("/sendfax")
    assert "No modems configured" in page.text
    res = _post(_login(world, "carl"), upload=("a.txt", b"hello"))
    assert "No modems configured" in res.text and sent == []


def test_a_single_line_is_used_when_none_is_named(world, sent):
    _post(_login(world, "alice"), upload=("a.txt", b"hello"))
    assert sent and sent[0].modem == "ttyS0"


def test_any_line_means_no_line_is_forced(world, sent):
    world.db.execute(update(UserAccount).where(UserAccount.username == "alice").values(any_modem=1))
    world.db.flush()
    _post(_login(world, "alice"), upload=("a.txt", b"hello"), modem="")
    assert sent and not sent[0].modem


# --- files ------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name,content", [("a.pdf", b"%PDF-1.4 x"), ("a.ps", b"%!PS-Adobe-3.0"), ("a.tif", b"II*\x00rest"),
                                           ("a.tif", b"MM\x00*rest"), ("a.txt", "plain text ünï\n".encode())])
def test_the_allowed_file_types_are_sent(world, sent, name, content):
    _post(_login(world, "alice"), upload=(name, content))
    assert len(sent) == 1


@pytest.mark.parametrize("name,content", [("a.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 20), ("a.exe", b"MZ\x90\x00\x03"),
                                           ("a.pdf", b"not really a pdf \x00\x01\x02")])
def test_other_file_types_are_refused_whatever_their_name(world, sent, name, content):
    res = _post(_login(world, "alice"), upload=(name, content))
    assert "File type is unauthorized" in res.text and sent == []


def test_a_file_over_the_limit_is_refused(world, sent, monkeypatch):
    monkeypatch.setenv("NAMIFAX_MAX_UPLOAD_BYTES", "100")
    res = _post(_login(world, "alice"), upload=("a.txt", b"x" * 500))
    assert "File size is over the limit" in res.text and sent == []


def test_the_page_names_the_size_limit(world, monkeypatch):
    monkeypatch.setenv("NAMIFAX_MAX_UPLOAD_BYTES", str(3 * 1024 * 1024))
    assert "3 MB" in _login(world, "alice").get("/sendfax").text or "3MB" in _login(world, "alice").get("/sendfax").text


# --- superuser fields -------------------------------------------------------------------------------------------------------

def test_priority_and_tsi_are_for_superusers_only(world):
    assert _page(world, "alice").find("select", {"name": "priority"}) is None
    assert _page(world, "alice").find("input", {"name": "user_tsi"}) is None
    assert _page(world, "root").find("select", {"name": "priority"}) is not None
    assert _page(world, "root").find("input", {"name": "user_tsi"}) is not None


def test_a_user_cannot_set_priority_or_tsi_by_posting_them(world, sent):
    _post(_login(world, "alice"), upload=("a.txt", b"hello"), priority="0", user_tsi="EVIL")
    assert sent and sent[0].priority == "*" and sent[0].tsi != "EVIL"


def test_a_superuser_can_set_them(world, sent):
    _post(_login(world, "root"), upload=("a.txt", b"hello"), priority="10", user_tsi="HQ", modem="ttyS0")
    assert sent and sent[0].priority == "10" and sent[0].tsi == "HQ"


# --- after sending ---------------------------------------------------------------------------------------------------------

def test_the_job_number_is_shown_after_sending(world):
    with patch("namifax.views.sendfax.dispatch_sendfax", lambda send, sender: {"success": True, "jobid": "4711"}):
        res = _post(_login(world, "alice"), upload=("a.txt", b"hello"))
        page = res.follow()
    assert "4711" in page.text
