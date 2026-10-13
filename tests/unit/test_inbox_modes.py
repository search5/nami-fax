"""RESTRICTED_USER_MODE and INBOX_LIST_MODEM of the original's local_config.php, switched on from the environment.

Restricted mode makes a user's archive search need the modem (or DID route) AND the category of the account instead of either one.
Listing the inbox by modem orders it by line and shows a heading above each line's faxes.
"""

from __future__ import annotations

import re

import pytest
import webtest

from namifax.common import settings
from namifax.models import FaxArchive
from namifax.services.user_account import NFUserAccount

PWD = "Secret123!"


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in ("RESTRICTED_USER_MODE", "INBOX_LIST_MODEM"):
        monkeypatch.delenv(name, raising=False)


def _user(session, username, **extra):
    svc = NFUserAccount(db=session)
    details = {"username": username, "password": PWD, "email": f"{username}@corp.test", "name": username.title(),
               "last_login": "2026-01-01 10:00:00", "acc_enabled": 1, **extra}
    assert svc.create(details), svc.error
    session.flush()
    return svc.uid


def _fax(session, tmp_path, name, **kw):
    folder = tmp_path / name
    folder.mkdir()
    (folder / "fax.pdf").write_bytes(f"%PDF-1.4 {name}".encode())
    row = FaxArchive(faxpath=str(folder), pages=1, archstamp="2026-03-01 10:00:00", **kw)
    session.add(row)
    session.flush()
    return row.fid


@pytest.fixture
def world(testapp, dbsession, tmp_path):
    dbsession.execute(FaxArchive.__table__.delete())
    _user(dbsession, "alice", modemdevs="ttyS0", faxcats="1")
    _user(dbsession, "root", superuser=1, is_admin=1)
    fax = {
        "on_line_and_category": _fax(dbsession, tmp_path, "a", inbox=0, modemdev="ttyS0", faxcatid=1),
        "on_line_only": _fax(dbsession, tmp_path, "b", inbox=0, modemdev="ttyS0", faxcatid=2),
        "category_only": _fax(dbsession, tmp_path, "c", inbox=0, modemdev="ttyS1", faxcatid=1),
        "uncategorised_on_line": _fax(dbsession, tmp_path, "d", inbox=0, modemdev="ttyS0"),
        "other": _fax(dbsession, tmp_path, "e", inbox=0, modemdev="ttyS1", faxcatid=2),
    }
    return type("World", (), {"fax": fax, "app": testapp.app, "env": testapp.extra_environ, "db": dbsession})


def _login(world, username):
    client = webtest.TestApp(world.app, extra_environ=world.env)
    res = client.post("/login", {"username": username, "password": PWD, "_submit_check": "1"})
    assert res.status_int == 302, username
    return client


def _found(world, client):
    page = client.get("/archive?kw=&opensearch=1&sentrecvd=r").text
    ids = set(map(int, re.findall(r'id="faxid_(\d+)"', page)))
    return {name for name, fid in world.fax.items() if fid in ids}


# --- the switches ------------------------------------------------------------------------------------------------------------

def test_both_modes_are_off_by_default():
    assert settings.restricted_user_mode() is False
    assert settings.inbox_list_modem() is False


@pytest.mark.parametrize("name,reader", [("RESTRICTED_USER_MODE", settings.restricted_user_mode),
                                         ("INBOX_LIST_MODEM", settings.inbox_list_modem)])
def test_a_mode_is_switched_on_from_the_environment(monkeypatch, name, reader):
    monkeypatch.setenv(name, "1")
    assert reader() is True
    monkeypatch.setenv(name, "0")
    assert reader() is False


# --- RESTRICTED_USER_MODE ----------------------------------------------------------------------------------------------------

def test_by_default_the_line_or_the_category_is_enough_to_find_a_fax(world):
    assert _found(world, _login(world, "alice")) == {"on_line_and_category", "on_line_only", "category_only",
                                                       "uncategorised_on_line"}


def test_in_restricted_mode_a_fax_needs_the_line_and_the_category(world, monkeypatch):
    monkeypatch.setenv("RESTRICTED_USER_MODE", "1")
    assert _found(world, _login(world, "alice")) == {"on_line_and_category", "uncategorised_on_line"}


def test_restricted_mode_does_not_limit_a_superuser(world, monkeypatch):
    monkeypatch.setenv("RESTRICTED_USER_MODE", "1")
    assert _found(world, _login(world, "root")) == set(world.fax)


# --- INBOX_LIST_MODEM --------------------------------------------------------------------------------------------------------

@pytest.fixture
def inbox(world, tmp_path):
    world.db.execute(FaxArchive.__table__.delete())
    return [_fax(world.db, tmp_path, n, inbox=1, modemdev=dev) for n, dev in
            (("i1", "ttyS1"), ("i2", "ttyS0"), ("i3", "ttyS1"), ("i4", "ttyS0"))]


def _order(client):
    return [int(i) for i in re.findall(r'id="faxid_(\d+)"', client.get("/inbox").text)]


def test_the_inbox_is_listed_newest_first_by_default(world, inbox):
    assert _order(_login(world, "root")) == sorted(inbox, reverse=True)


def test_the_inbox_can_be_listed_line_by_line(world, inbox, monkeypatch):
    monkeypatch.setenv("INBOX_LIST_MODEM", "1")
    page = _login(world, "root").get("/inbox").text
    assert [int(i) for i in re.findall(r'id="faxid_(\d+)"', page)] == [inbox[3], inbox[1], inbox[2], inbox[0]]
    assert page.count('data-line-heading') == 2


def test_there_are_no_line_headings_by_default(world, inbox):
    assert 'data-line-heading' not in _login(world, "root").get("/inbox").text
