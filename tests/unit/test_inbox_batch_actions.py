"""Inbox: archive and delete one fax or several, as the original's inbox did (links, bulk buttons, confirmation)."""

from __future__ import annotations

import re

import pytest
from bs4 import BeautifulSoup

from namifax.models import FaxArchive
from test_fax_access_control import _login, world  # noqa: F401  (alice: ttyS0 + category 1, no delete; dan: ttyS0, can_del)


def _soup(client, path="/inbox"):
    return BeautifulSoup(client.get(path).text, "html.parser")


def _inbox_fids(world, user):
    return sorted(int(c["value"]) for c in _soup(_login(world, user)).find_all("input", {"name": "fids", "type": "checkbox"}))


# --- the page ---------------------------------------------------------------------------------------------------------------

def test_the_row_archive_button_posts_to_the_archive_endpoint(world):
    soup = _soup(_login(world, "alice"))
    form = soup.find("form", {"action": "/ajax/archivefax", "data-fax": str(world.fax["A"])})
    assert form is not None and form["method"].lower() == "post"
    assert form.find("input", {"name": "fids"})["value"] == str(world.fax["A"])
    assert "/archive/move/" not in str(soup)


def test_the_bulk_buttons_work_on_the_checked_faxes_through_a_form_of_their_own(world):
    soup = _soup(_login(world, "dan"))
    batch = soup.find("form", id="batchform")
    assert batch is not None and batch["method"].lower() == "post"
    boxes = soup.find_all("input", {"name": "fids", "type": "checkbox"})
    assert boxes and all(b.get("form") == "batchform" for b in boxes)
    archive = soup.find("button", attrs={"formaction": "/ajax/archivefax"})
    delete = soup.find("button", attrs={"formaction": "/ajax/deletefaxes"})
    assert archive.get("form") == "batchform" and delete.get("form") == "batchform" and delete.get("formmethod", "").lower() == "get"


def test_a_user_who_cannot_delete_is_not_offered_delete(world):
    soup = _soup(_login(world, "alice"))
    assert soup.find("button", attrs={"formaction": "/ajax/deletefaxes"}) is None
    assert not [a for a in soup.find_all("a") if (a.get("href") or "").startswith("/delete")]


def test_a_user_who_can_delete_gets_a_working_delete_link(world):
    soup = _soup(_login(world, "dan"))
    assert soup.find("a", href=f"/delete?fid={world.fax['A']}") is not None
    assert "/delete/" not in str(soup)


# --- archiving --------------------------------------------------------------------------------------------------------------

def test_archiving_several_checked_faxes_archives_the_ones_the_user_may_use(world):
    client = _login(world, "alice")
    res = client.post("/ajax/archivefax", {"fids": [str(world.fax["A"]), str(world.fax["B"])]})
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox")
    world.db.expire_all()
    assert (world.db.get(FaxArchive, world.fax["A"]).inbox, world.db.get(FaxArchive, world.fax["B"]).inbox) == (0, 1)


def test_the_old_comma_separated_value_still_works(world):
    _login(world, "alice").post("/ajax/archivefax", {"fids": f"{world.fax['A']},{world.fax['B']}"})
    world.db.expire_all()
    assert world.db.get(FaxArchive, world.fax["A"]).inbox == 0


def test_an_ajax_caller_gets_an_empty_answer(world):
    res = _login(world, "alice").post("/ajax/archivefax", {"fids": str(world.fax["A"])}, headers={"X-Requested-With": "XMLHttpRequest"})
    assert res.status_int == 200 and res.text == ""


# --- deleting ---------------------------------------------------------------------------------------------------------------

def test_the_bulk_delete_asks_first_and_lists_what_it_will_delete(world):
    page = _login(world, "dan").get("/ajax/deletefaxes", params=[("fids", str(world.fax["A"])), ("fids", str(world.fax["C"]))])
    values = sorted(int(i["value"]) for i in BeautifulSoup(page.text, "html.parser").find_all("input", {"name": "fids"}))
    assert values == sorted([world.fax["A"], world.fax["C"]]) and 'href="/inbox"' in page.text


def test_confirming_deletes_what_the_user_may_delete_and_returns_to_the_inbox(world):
    client = _login(world, "dan")
    res = client.post("/ajax/deletefaxes", {"fids": [str(world.fax["A"]), str(world.fax["B"])]})
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox")
    world.db.expire_all()
    assert world.db.get(FaxArchive, world.fax["A"]) is None and world.db.get(FaxArchive, world.fax["B"]) is not None


def test_the_confirmation_does_not_echo_markup(world):
    page = _login(world, "dan").get("/ajax/deletefaxes", params={"fids": '"><script>alert(1)</script>'})
    assert "<script>alert(1)" not in page.text
    assert not re.search(r'name="fids" value="[^"]*[<>]', page.text)


def test_a_user_who_cannot_delete_is_refused(world):
    assert _login(world, "alice").get("/ajax/deletefaxes", params={"fids": str(world.fax["A"])}, expect_errors=True).status_int == 403
