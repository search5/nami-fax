"""Rotating a fax and assigning its company change data, so they are POSTs with the session's CSRF token.

(The original rotated through a link, rotate.php?fid=N, which any other page could make a signed-in user follow; the login
cookie is SameSite=Lax and still travels with such a link.)
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup

from namifax.models import AddressBook, AddressBookFAX, FaxArchive
from test_fax_access_control import _login, world  # noqa: F401  (users alice/bob/carl/dan/root and nine faxes)


@pytest.fixture
def rotated():
    """Counts rotations instead of touching fax image files."""
    calls = []
    with patch("namifax.services.archive_in.ArchiveIn.rotate_fax", lambda self: calls.append(self.get_fid()) or True):
        yield calls


def _token(client, path="/inbox"):
    return BeautifulSoup(client.get(path).text, "html.parser").find("input", {"name": "csrf_token"})["value"]


def _number(world, fax_key="A"):
    ab = AddressBook(company="Acme")
    world.db.add(ab)
    world.db.flush()
    num = AddressBookFAX(abook_id=ab.abook_id, faxnumber="5550100")
    world.db.add(num)
    world.db.flush()
    return num.abookfax_id


# --- the buttons are forms ----------------------------------------------------------------------------------------------------

def test_the_inbox_rotate_button_is_a_post_form_with_the_token(world):
    page = _login(world, "alice").get("/inbox")
    form = BeautifulSoup(page.text, "html.parser").find("form", {"action": f"/faxes/rotate/{world.fax['A']}"})
    assert form is not None and form["method"].lower() == "post"
    assert form.find("input", {"name": "csrf_token"})["value"] and form.find("input", {"name": "redirect"})["value"] == "inbox"
    assert f'href="/faxes/rotate/' not in page.text


def test_the_preview_rotate_button_is_a_post_form_with_the_token(world):
    page = _login(world, "alice").get(f"/viewfax?fid={world.fax['A']}")
    form = BeautifulSoup(page.text, "html.parser").find("form", {"action": f"/faxes/rotate/{world.fax['A']}"})
    assert form is not None and form["method"].lower() == "post" and form.find("input", {"name": "csrf_token"})["value"]


# --- rotating -----------------------------------------------------------------------------------------------------------------

def test_a_post_with_the_token_rotates_the_fax_and_returns_to_the_inbox(world, rotated):
    client = _login(world, "alice")
    res = client.post(f"/faxes/rotate/{world.fax['A']}", {"csrf_token": _token(client), "redirect": "inbox"})
    assert rotated == [world.fax["A"]] and res.status_int == 302 and res.headers["Location"].endswith("/inbox")


def test_the_preview_goes_back_to_the_preview(world, rotated):
    client = _login(world, "alice")
    res = client.post(f"/faxes/rotate/{world.fax['A']}", {"csrf_token": _token(client), "redirect": "viewfax"})
    assert res.status_int == 302 and res.headers["Location"].endswith(f"/viewfax?fid={world.fax['A']}")


def test_without_a_redirect_the_answer_is_json(world, rotated):
    client = _login(world, "alice")
    res = client.post(f"/faxes/rotate/{world.fax['A']}", {"csrf_token": _token(client)})
    assert res.json["status"] == "ok" and rotated == [world.fax["A"]]


def test_the_old_rotate_link_and_address_do_nothing(world, rotated):
    client = _login(world, "alice")
    assert client.get(f"/faxes/rotate/{world.fax['A']}", expect_errors=True).status_int == 405
    assert client.get(f"/rotate?fid={world.fax['A']}", expect_errors=True).status_int == 405
    assert rotated == []


@pytest.mark.parametrize("token", [None, "", "not-the-token"])
def test_a_rotate_post_without_a_good_token_does_nothing(world, rotated, token):
    client = _login(world, "alice")
    data = {} if token is None else {"csrf_token": token}
    assert client.post(f"/faxes/rotate/{world.fax['A']}", data, expect_errors=True).status_int == 400
    assert rotated == []


def test_the_token_of_another_session_is_refused(world, rotated):
    other = _token(_login(world, "bob"))
    res = _login(world, "alice").post(f"/faxes/rotate/{world.fax['A']}", {"csrf_token": other}, expect_errors=True)
    assert res.status_int == 400 and rotated == []


def test_a_user_still_cannot_rotate_a_fax_they_have_no_right_to(world, rotated):
    client = _login(world, "bob")
    client.post(f"/faxes/rotate/{world.fax['A']}", {"csrf_token": _token(client)}, expect_errors=True)
    assert rotated == []


def test_rotate_by_the_form_field_address(world, rotated):
    client = _login(world, "alice")
    client.post("/rotate", {"fid": str(world.fax["A"]), "csrf_token": _token(client)})
    assert rotated == [world.fax["A"]]


# --- assigning a company ---------------------------------------------------------------------------------------------------------

def _faxnumid(world, key="A"):
    world.db.expire_all()
    return world.db.get(FaxArchive, world.fax[key]).faxnumid


def test_a_post_with_the_token_assigns_the_company(world):
    number = _number(world)
    client = _login(world, "alice")
    res = client.post("/setcompany", {"fid": str(world.fax["A"]), "faxnumid": str(number), "csrf_token": _token(client)})
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox") and _faxnumid(world) == number


def test_the_old_setcompany_address_does_nothing(world):
    number = _number(world)
    client = _login(world, "alice")
    res = client.get(f"/setcompany?fid={world.fax['A']}&faxnumid={number}", expect_errors=True)
    assert res.status_int == 405 and _faxnumid(world) is None


@pytest.mark.parametrize("token", [None, "wrong"])
def test_a_setcompany_post_without_a_good_token_does_nothing(world, token):
    number = _number(world)
    data = {"fid": str(world.fax["A"]), "faxnumid": str(number)}
    if token:
        data["csrf_token"] = token
    res = _login(world, "alice").post("/setcompany", data, expect_errors=True)
    assert res.status_int == 400 and _faxnumid(world) is None


def test_a_user_cannot_assign_a_company_to_a_fax_they_have_no_right_to(world):
    number = _number(world)
    client = _login(world, "bob")
    client.post("/setcompany", {"fid": str(world.fax["A"]), "faxnumid": str(number), "csrf_token": _token(client)})
    assert _faxnumid(world) is None
