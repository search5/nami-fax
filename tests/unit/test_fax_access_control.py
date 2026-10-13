"""Who may see and change which fax (the original's user_has_rights rules).

A user who is not a superuser only works with the faxes of the modems (or DID routes) and categories on their account
and with the faxes they sent themselves. Deleting also needs the can_del flag. The port listed every fax to everybody and
let any signed-in user view, change, archive and delete any fax.
"""

from __future__ import annotations

import re

import pytest
import webtest
from sqlalchemy import select

from namifax.models import FaxArchive, SysLog
from namifax.services.user_account import NFUserAccount

PWD = "Secret123!"


def _user(session, username, **extra):
    svc = NFUserAccount(db=session)
    details = {"username": username, "password": PWD, "email": f"{username}@corp.test", "name": username.title(),
               "last_login": "2026-01-01 10:00:00", "acc_enabled": 1, **extra}
    assert svc.create(details), svc.error
    session.flush()
    return svc.uid


def _fax(session, tmp_path, name, **kw):
    kw.setdefault("inbox", 1)
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
    ids = {}
    ids["alice"] = _user(dbsession, "alice", modemdevs="ttyS0", faxcats="1")
    ids["bob"] = _user(dbsession, "bob", modemdevs="ttyS1")
    ids["carl"] = _user(dbsession, "carl")                                   # no modems at all
    ids["dan"] = _user(dbsession, "dan", modemdevs="ttyS0", can_del=1)
    ids["root"] = _user(dbsession, "root", superuser=1, can_del=1, is_admin=1)
    fax = {
        "A": _fax(dbsession, tmp_path, "A", modemdev="ttyS0"),
        "B": _fax(dbsession, tmp_path, "B", modemdev="ttyS1"),
        "C": _fax(dbsession, tmp_path, "C", modemdev="ttyS0", faxcatid=2),
        "S": _fax(dbsession, tmp_path, "S", inbox=0, userid=ids["alice"]),
    }
    return type("World", (), {"ids": ids, "fax": fax, "app": testapp.app, "env": testapp.extra_environ, "db": dbsession})


def _login(world, username):
    client = webtest.TestApp(world.app, extra_environ=world.env)
    res = client.post("/login", {"username": username, "password": PWD, "_submit_check": "1"})
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox"), (username, res.headers.get("Location"))
    return client


def _alive(world, fid):
    world.db.expire_all()
    return world.db.get(FaxArchive, fid) is not None


def _inbox_ids(client):
    return set(map(int, re.findall(r"/faxes/download/(\d+)\?format=pdf", client.get("/inbox").text)))


# --- what the inbox lists --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("user,expected", [("alice", {"A"}), ("bob", {"B"}), ("carl", set()), ("dan", {"A"}),
                                             ("root", {"A", "B", "C"})])
def test_the_inbox_lists_only_what_the_user_may_see(world, user, expected):
    assert _inbox_ids(_login(world, user)) == {world.fax[k] for k in expected}


def test_the_unread_counter_counts_the_visible_faxes(world):
    assert _login(world, "alice").get("/ajax/inbox").text.strip() == "1"
    assert _login(world, "root").get("/ajax/inbox").text.strip() == "3"
    assert _login(world, "carl").get("/ajax/inbox").text.strip() == "0"


# --- reading a single fax ----------------------------------------------------------------------------------------------------

def test_a_pdf_can_only_be_downloaded_with_the_right(world):
    a = world.fax["A"]
    assert _login(world, "alice").get(f"/faxes/download/{a}?format=pdf").body.startswith(b"%PDF-1.4 A")
    assert _login(world, "root").get(f"/faxes/download/{a}?format=pdf").status_int == 200
    for user in ("bob", "carl"):
        assert _login(world, user).get(f"/faxes/download/{a}?format=pdf", expect_errors=True).status_int in (403, 404), user


def test_a_user_always_has_the_right_to_the_faxes_they_sent(world):
    s = world.fax["S"]
    assert _login(world, "alice").get(f"/faxes/download/{s}?format=pdf").status_int == 200
    assert _login(world, "bob").get(f"/faxes/download/{s}?format=pdf", expect_errors=True).status_int in (403, 404)


def test_the_preview_page_does_not_reveal_other_users_faxes(world):
    a = world.fax["A"]
    assert "ttyS0" in _login(world, "alice").get(f"/viewfax?fid={a}").text
    page = _login(world, "bob").get(f"/viewfax?fid={a}", expect_errors=True)
    assert page.status_int in (403, 404) or "ttyS0" not in page.text


# --- changing a single fax ----------------------------------------------------------------------------------------------------

def test_notes_can_only_be_set_on_faxes_the_user_may_use(world):
    a = world.fax["A"]
    _login(world, "bob").post("/note", {"fid": str(a), "description": "bob was here", "_submit_check": "1"}, expect_errors=True)
    world.db.expire_all()
    assert world.db.get(FaxArchive, a).description != "bob was here"
    _login(world, "alice").post("/note", {"fid": str(a), "description": "alice note", "_submit_check": "1"})
    world.db.expire_all()
    assert world.db.get(FaxArchive, a).description == "alice note"


def test_archiving_needs_the_right(world):
    a = world.fax["A"]
    _login(world, "bob").post("/ajax/archivefax", {"fid": str(a)}, expect_errors=True)
    world.db.expire_all()
    assert world.db.get(FaxArchive, a).inbox == 1
    _login(world, "alice").post("/ajax/archivefax", {"fid": str(a)})
    world.db.expire_all()
    assert world.db.get(FaxArchive, a).inbox == 0


def test_a_bulk_archive_skips_what_the_user_may_not_touch(world):
    a, b = world.fax["A"], world.fax["B"]
    _login(world, "alice").post("/ajax/archivefax", {"fids": f"{a},{b}"})
    world.db.expire_all()
    assert (world.db.get(FaxArchive, a).inbox, world.db.get(FaxArchive, b).inbox) == (0, 1)


# --- deleting ------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("user,fax,deleted", [
    ("alice", "A", False),      # may use the fax but cannot delete anything
    ("bob", "A", False),        # cannot delete and has no right to it
    ("dan", "A", True),         # can delete and has the right
    ("dan", "B", False),        # can delete but not this fax
    ("root", "B", True),        # superuser
])
def test_deleting_needs_the_flag_and_the_right_ajax(world, user, fax, deleted):
    fid = world.fax[fax]
    _login(world, user).post("/ajax/deletefaxes", {"fids": str(fid), "_submit_check": "1"}, expect_errors=True)
    assert _alive(world, fid) is (not deleted)


@pytest.mark.parametrize("user,fax,deleted", [("alice", "A", False), ("dan", "A", True), ("dan", "B", False), ("root", "B", True)])
def test_deleting_needs_the_flag_and_the_right_modal(world, user, fax, deleted):
    fid = world.fax[fax]
    _login(world, user).post("/delete", {"fid": str(fid), "_submit_check": "1"}, expect_errors=True)
    assert _alive(world, fid) is (not deleted)


def test_a_refused_delete_is_logged(world):
    _login(world, "dan").post("/ajax/deletefaxes", {"fids": str(world.fax["B"]), "_submit_check": "1"})
    texts = [r.logtext for r in world.db.execute(select(SysLog)).scalars()]
    assert any("Access denied" in t and str(world.fax["B"]) in t and "dan" in t for t in texts)


def test_the_delete_confirmation_is_not_offered_to_users_who_cannot_delete(world):
    a = world.fax["A"]
    assert "Delete selected faxes" not in _login(world, "alice").get(f"/ajax/deletefaxes?fids={a}", expect_errors=True).text
    assert "Delete selected faxes" in _login(world, "dan").get(f"/ajax/deletefaxes?fids={a}").text


# --- the archive search follows the same rules ---------------------------------------------------------------------------------

def test_the_archive_search_shows_only_what_the_user_may_see(world):
    for key in ("A", "B", "C"):
        world.db.get(FaxArchive, world.fax[key]).inbox = 0
    world.db.flush()
    names = {fid: key for key, fid in world.fax.items()}

    def found(user):
        text = _login(world, user).get("/archive?kw=&sentrecvd=*&start_day=*&start_month=*&start_year=*&end_day=*&end_month=*&end_year=*").text
        return {names[int(fid)] for fid in re.findall(r'id="faxid_(\d+)"', text)}

    assert found("root") == {"A", "B", "C", "S"}
    assert found("bob") == {"B"}
    assert found("carl") == set()
    assert found("alice") >= {"S"} and "B" not in found("alice")           # her own sent fax is always hers
