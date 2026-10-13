"""Settings page: default cover page and page sizes are saved; name and e-mail are checked on the server (the original settings.php)."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import select

from namifax.models import UserAccount


@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


def _admin(session):
    session.expire_all()
    return session.execute(select(UserAccount).where(UserAccount.username == "admin")).scalar_one()


def _form(client):
    return next(f for f in client.get("/settings").forms.values() if "faxperpageinbox" in f.fields)


def test_the_cover_pages_are_the_real_ones(client):
    soup = BeautifulSoup(client.get("/settings").text, "html.parser")
    options = soup.find("select", {"name": "coverpage_id"}).find_all("option")
    assert len(options) >= 3 and all(o["value"].isdigit() or o["value"] == "" for o in options)


def test_the_page_size_lists_are_the_originals(client):
    soup = BeautifulSoup(client.get("/settings").text, "html.parser")
    for name in ("faxperpageinbox", "faxperpagearchive"):
        values = [o["value"] for o in soup.find("select", {"name": name}).find_all("option")]
        assert values == ["10", "15", "20", "25", "30", "50", "100"], name


def test_cover_and_page_sizes_are_saved_and_shown_again(client, dbsession):
    form = _form(client)
    cover = next(v for v, _, _ in form["coverpage_id"].options if v)
    form["coverpage_id"], form["faxperpageinbox"], form["faxperpagearchive"] = cover, "50", "15"
    form.submit()
    user = _admin(dbsession)
    assert (str(user.coverpage_id), user.faxperpageinbox, user.faxperpagearchive) == (cover, 50, 15)
    again = _form(client)
    assert (again["coverpage_id"].value, again["faxperpageinbox"].value, again["faxperpagearchive"].value) == (cover, "50", "15")


def test_a_wrong_email_is_refused_by_the_server(client, dbsession):
    before = _admin(dbsession).email
    form = _form(client)
    form["email"] = "not-an-address"
    res = form.submit()
    assert "e-mail" in res.text.lower() or "email" in res.text.lower()
    assert _admin(dbsession).email == before


def test_an_email_of_another_user_is_refused(client, dbsession):
    from namifax.services.user_account import NFUserAccount

    other = NFUserAccount(db=dbsession)
    assert other.create({"username": "taken", "password": "Secret123!", "email": "taken@corp.test", "name": "T", "acc_enabled": 1})
    dbsession.flush()
    before = _admin(dbsession).email
    form = _form(client)
    form["email"] = "taken@corp.test"
    res = form.submit()
    assert "already" in res.text.lower() and _admin(dbsession).email == before


def test_a_name_is_required(client, dbsession):
    before = _admin(dbsession).name
    form = _form(client)
    form["name"] = ""
    form.submit()
    assert _admin(dbsession).name == before
