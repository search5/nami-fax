"""The e-mail book edit page: create, save and delete contacts with the checks and messages of the original."""

from __future__ import annotations

import re

import pytest
import webtest
from sqlalchemy import select

from namifax.models import AddressBookEmail


@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


def _contacts(session):
    return {c.abookemail_id: (c.contact_name, c.contact_email)
            for c in session.execute(select(AddressBookEmail).order_by(AddressBookEmail.abookemail_id)).scalars()}


def _make(client, name="Ann Lee", email="ann@corp.test"):
    return client.post("/emailbook/edit", {"_submit_check": "1", "create": "1", "contact_name": name, "contact_email": email},
                       expect_errors=True)


# --- creating ---------------------------------------------------------------------------------------------------------------

def test_the_new_contact_form_does_not_name_an_existing_contact(client):
    """It used to post email_id=1, so 'creating' a contact overwrote contact number 1."""
    page = client.get("/emailbook/edit")
    assert 'name="create"' in page.text and 'name="delete"' not in page.text and 'name="company"' not in page.text
    for field in ("email_id", "abookemail_id"):
        assert not re.search(rf'name="{field}" value="[^"]+"', page.text), field


def test_creating_a_contact_never_touches_the_existing_ones(client, dbsession):
    before = _contacts(dbsession)
    assert before                                                      # the demo address book has contacts
    first = min(before)
    res = _make(client)
    assert res.status_int == 302
    after = _contacts(dbsession)
    assert after[first] == before[first]
    assert sorted(set(after.values()) - set(before.values())) == [("Ann Lee", "ann@corp.test")]


def test_filling_in_the_real_new_contact_form_creates_a_new_contact(client, dbsession):
    """Submit the page's own form (hidden fields included), as a browser does."""
    before = _contacts(dbsession)
    page = client.get("/emailbook/edit")
    form = next(f for f in page.forms.values() if "contact_name" in f.fields)      # the upload form comes first
    form["contact_name"], form["contact_email"] = "Brand New", "brand@new.test"
    res = form.submit("create")
    assert res.status_int == 302
    after = _contacts(dbsession)
    assert all(after[k] == v for k, v in before.items())            # nobody was overwritten
    assert ("Brand New", "brand@new.test") in after.values() and len(after) == len(before) + 1


def test_after_creating_the_contact_is_shown_with_a_message(client, dbsession):
    res = _make(client)
    page = res.follow()
    assert 'value="Ann Lee"' in page.text and "saved" in page.text.lower()


@pytest.mark.parametrize("name,email,expect", [
    ("Bob", "not-an-address", "valid e-mail"),
    ("Bob", "", "valid e-mail"),
    ("", "bob@corp.test", "enter a name"),
])
def test_bad_input_is_explained_and_nothing_is_stored(client, dbsession, name, email, expect):
    before = _contacts(dbsession)
    res = _make(client, name, email)
    assert res.status_int == 200 and expect in res.text.lower()
    assert _contacts(dbsession) == before
    assert f'value="{name}"' in res.text if name else True              # what was typed is kept


def test_an_address_that_is_already_in_the_book_is_refused(client, dbsession):
    _make(client)
    before = _contacts(dbsession)
    res = _make(client, "Other Ann", "ann@corp.test")
    assert res.status_int == 200 and "already exists" in res.text.lower() and _contacts(dbsession) == before


# --- saving ------------------------------------------------------------------------------------------------------------------

def _new_id(session):
    return max(_contacts(session))


def test_the_edit_page_shows_the_contact(client, dbsession):
    _make(client)
    cid = _new_id(dbsession)
    page = client.get(f"/emailbook/edit?abookemail_id={cid}")
    assert 'value="Ann Lee"' in page.text and 'value="ann@corp.test"' in page.text
    assert f'name="abookemail_id" value="{cid}"' in page.text and 'name="save"' in page.text


def test_saving_changes_only_that_contact(client, dbsession):
    _make(client)
    cid = _new_id(dbsession)
    others = {k: v for k, v in _contacts(dbsession).items() if k != cid}
    res = client.post("/emailbook/edit", {"_submit_check": "1", "save": "1", "abookemail_id": str(cid),
                                          "contact_name": "Ann Kim", "contact_email": "ann.kim@corp.test"})
    assert res.status_int == 302
    dbsession.expire_all()
    now = _contacts(dbsession)
    assert now[cid] == ("Ann Kim", "ann.kim@corp.test") and {k: v for k, v in now.items() if k != cid} == others


@pytest.mark.parametrize("name,email,expect", [("Ann", "broken", "valid e-mail"), ("", "ann@corp.test", "enter a name")])
def test_saving_bad_input_keeps_the_contact_and_explains(client, dbsession, name, email, expect):
    _make(client)
    cid = _new_id(dbsession)
    res = client.post("/emailbook/edit", {"_submit_check": "1", "save": "1", "abookemail_id": str(cid),
                                          "contact_name": name, "contact_email": email})
    assert res.status_int == 200 and expect in res.text.lower()
    dbsession.expire_all()
    assert _contacts(dbsession)[cid] == ("Ann Lee", "ann@corp.test")


def test_an_unknown_contact_goes_back_to_the_list(client):
    res = client.post("/emailbook/edit", {"_submit_check": "1", "save": "1", "abookemail_id": "99999",
                                          "contact_name": "X", "contact_email": "x@corp.test"})
    assert res.status_int == 302 and res.headers["Location"].endswith("/emailbook")


def test_names_are_escaped(client, dbsession):
    _make(client, "<b>Bold</b> Ann", "bold@corp.test")
    cid = _new_id(dbsession)
    page = client.get(f"/emailbook/edit?abookemail_id={cid}")
    assert "<b>Bold</b>" not in page.text and "&lt;b&gt;" in page.text


# --- deleting ------------------------------------------------------------------------------------------------------------------

def test_a_superuser_can_delete(client, dbsession):
    _make(client)
    cid = _new_id(dbsession)
    res = client.post("/emailbook/edit", {"_submit_check": "1", "delete": "1", "abookemail_id": str(cid)})
    assert res.status_int == 302 and cid not in _contacts(dbsession)


def test_other_users_cannot_delete(client, dbsession):
    _make(client)
    cid = _new_id(dbsession)
    other = webtest.TestApp(client.app, extra_environ=client.extra_environ)
    other.post("/login", {"username": "operator", "password": "password", "_submit_check": "1"})
    assert 'name="delete"' not in other.get(f"/emailbook/edit?abookemail_id={cid}").text
    res = other.post("/emailbook/edit", {"_submit_check": "1", "delete": "1", "abookemail_id": str(cid)}, expect_errors=True)
    assert cid in _contacts(dbsession) and (res.status_int != 302 or "/emailbook/edit" in res.headers["Location"])


# --- the list ------------------------------------------------------------------------------------------------------------------

def test_the_list_can_be_searched_by_name_or_address(client, dbsession):
    _make(client, "Zebra Zed", "zed@corp.test")
    assert "Zebra Zed" in client.get("/emailbook?q=zebra").text
    assert "Zebra Zed" in client.get("/emailbook?q=ZED@corp").text
    assert "Zebra Zed" not in client.get("/emailbook?q=nomatch").text


def test_only_signed_in_users_can_reach_the_pages(testapp):
    for path in ("/emailbook", "/emailbook/edit"):
        assert testapp.get(path, expect_errors=True).status_int != 200
