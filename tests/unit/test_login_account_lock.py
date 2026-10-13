"""After more than five wrong passwords an account stays locked, even for the right password, and only an administrator unlocks it.

The lock does not end with time. It is lifted from the user list of the administration (a button, with the form's token) or on the
server with ``namifax unlock-user``; the lost-password page does not lift it, and neither does a successful sign-in with another
method. The failures of an account are counted one after the other since its last successful sign-in (they do not expire).
An address is still locked for a while only: it can be a whole office or a proxy.
"""

from __future__ import annotations

import json
import re
from unittest.mock import patch

import pytest
import webtest
from bs4 import BeautifulSoup
from sqlalchemy import select

from namifax.models import SystemConfig
from namifax.services import login_throttle as lt
from namifax.services.user_account import NFUserAccount

LOCKED = "Too many failed sign-in attempts"
PW = "Correct-pw-1"


@pytest.fixture(autouse=True)
def _defaults(monkeypatch):
    monkeypatch.delenv("NAMIFAX_LOGIN_MAX_FAILURES", raising=False)
    monkeypatch.delenv("NAMIFAX_LOGIN_LOCK_MINUTES", raising=False)


@pytest.fixture
def clock(monkeypatch):
    t = {"now": 2_000_000.0}
    monkeypatch.setattr(lt, "_now", lambda: t["now"])
    return t


def _user(session, name, **extra):
    svc = NFUserAccount(db=session)
    details = {"username": name, "password": PW, "email": f"{name}@corp.test", "name": name.title(), "acc_enabled": 1,
               "last_login": "2026-01-01 10:00:00", **extra}
    assert svc.create(details), svc.error
    session.flush()
    return svc.get_uid()


def _client(testapp):
    return webtest.TestApp(testapp.app, extra_environ=testapp.extra_environ)


def _login(client, name, password):
    return client.post("/login", {"username": name, "password": password, "_submit_check": "1"}, expect_errors=True)


def _fail(client, name, times):
    for _ in range(times):
        assert "Invalid username or password" in _login(client, name, "wrong").text


@pytest.fixture
def victim(dbsession):
    return _user(dbsession, "victim")


@pytest.fixture
def locked(testapp, victim):
    _fail(_client(testapp), "victim", 5)
    return victim


@pytest.fixture
def admin(testapp, locked):
    client = _client(testapp)
    assert _login(client, "admin", "password").status_int == 302
    return client


def _unlock_form(client, name):
    soup = BeautifulSoup(client.get("/admin/users").text, "html.parser")
    row = next(tr for tr in soup.find_all("tr") if tr.find("a", string=name))
    return soup, row, row.find("form", attrs={"data-unlock": True})


def _is_locked(session, name):
    session.expire_all()
    row = session.get(SystemConfig, lt._key("user", name))
    return bool(row and row.value and '"locked": true' in row.value)


# --- the lock ---------------------------------------------------------------------------------------------------------------

def test_five_wrong_passwords_are_tried_and_the_sixth_attempt_is_refused_even_with_the_right_password(testapp, victim):
    client = _client(testapp)
    _fail(client, "victim", 5)
    res = _login(client, "victim", PW)
    assert LOCKED in res.text and res.status_int == 200
    assert client.get("/inbox", expect_errors=True).status_int != 200            # not signed in


def test_the_message_says_that_an_administrator_has_to_unlock(testapp, locked):
    assert "administrator" in _login(_client(testapp), "victim", PW).text.lower()


def test_the_lock_stays_for_a_year(testapp, locked, clock):
    client = _client(testapp)
    for later in (15 * 60 + 1, 24 * 3600, 365 * 24 * 3600):
        clock["now"] += later
        assert LOCKED in _login(client, "victim", PW).text


def test_a_name_that_does_not_exist_is_answered_in_the_same_way(testapp):
    client = _client(testapp)
    _fail(client, "nobody-here", 5)
    assert LOCKED in _login(client, "nobody-here", "x").text


def test_one_account_being_locked_does_not_lock_another(testapp, locked, dbsession):
    _user(dbsession, "bystander")
    assert _login(_client(testapp), "bystander", PW).status_int == 302


def test_the_lost_password_page_does_not_lift_the_lock(testapp, locked, dbsession):
    sent = []
    with patch("namifax.views.auth.send_mail", lambda to, frm, subject, text, **kw: sent.append(text) or True):
        testapp.post("/forgot", {"email": "victim@corp.test", "_submit_check": "1"}, expect_errors=True)
    assert LOCKED in _login(_client(testapp), "victim", PW).text
    assert _is_locked(dbsession, "victim")


def test_creating_an_account_clears_a_lock_that_someone_left_on_its_name(testapp, dbsession):
    _fail(_client(testapp), "future_user", 5)                                     # a stranger tried the name before it existed
    _user(dbsession, "future_user")
    assert _login(_client(testapp), "future_user", PW).status_int == 302


def test_a_success_stays_possible_before_the_limit(testapp, victim):
    client = _client(testapp)
    _fail(client, "victim", 4)
    assert _login(client, "victim", PW).status_int == 302


def test_the_right_password_on_the_fifth_attempt_clears_the_count(testapp, victim, dbsession):
    client = _client(testapp)
    _fail(client, "victim", 4)
    assert _login(client, "victim", PW).status_int == 302                         # the fifth attempt is the right one
    assert not _is_locked(dbsession, "victim")
    row = dbsession.get(SystemConfig, lt._key("user", "victim"))
    assert json.loads(row.value or "{}") == {}                                    # nothing is left of the four failures
    other = _client(testapp)
    _fail(other, "victim", 4)                                                     # four more are allowed again
    assert _login(other, "victim", PW).status_int == 302
    _fail(_client(testapp), "victim", 5)                                          # and only five in a row lock it
    assert LOCKED in _login(_client(testapp), "victim", PW).text


# --- an administrator unlocks it --------------------------------------------------------------------------------------------

def test_the_user_list_marks_a_locked_account_and_offers_the_unlock_only_for_it(admin, dbsession):
    _user(dbsession, "free_user")
    soup, row, form = _unlock_form(admin, "victim")
    assert form is not None and "Locked" in row.get_text()
    assert form.find("input", attrs={"name": "csrf_token"})["value"]
    _, free_row, free_form = _unlock_form(admin, "free_user")
    assert free_form is None and "Locked" not in free_row.get_text()


def test_an_administrator_unlocks_the_account(admin, testapp, locked, dbsession):
    _, _, form = _unlock_form(admin, "victim")
    res = admin.post("/admin/users", {"unlock_uid": str(locked), "csrf_token": form.find("input", attrs={"name": "csrf_token"})["value"]})
    assert res.status_int in (200, 302)
    assert not _is_locked(dbsession, "victim")
    assert _login(_client(testapp), "victim", PW).status_int == 302
    soup = BeautifulSoup(admin.get("/admin/users").text, "html.parser")
    assert soup.find("form", attrs={"data-unlock": True}) is None


def test_an_unlock_without_the_form_token_is_refused(admin, testapp, locked, dbsession):
    admin.post("/admin/users", {"unlock_uid": str(locked)}, expect_errors=True)
    assert _is_locked(dbsession, "victim")
    assert LOCKED in _login(_client(testapp), "victim", PW).text


def test_a_user_who_is_not_an_administrator_cannot_unlock(testapp, locked, dbsession):
    _user(dbsession, "plain")
    client = _client(testapp)
    assert _login(client, "plain", PW).status_int == 302
    res = client.post("/admin/users", {"unlock_uid": str(locked), "csrf_token": "x"}, expect_errors=True)
    assert res.status_int != 200 or "unlock" not in res.text.lower()
    assert _is_locked(dbsession, "victim")


def test_the_unlock_does_not_touch_the_address_counter(admin, locked, dbsession):
    before = dbsession.get(SystemConfig, lt._key("ip", "127.0.0.1"))
    _, _, form = _unlock_form(admin, "victim")
    admin.post("/admin/users", {"unlock_uid": str(locked), "csrf_token": form.find("input", attrs={"name": "csrf_token"})["value"]})
    after = dbsession.get(SystemConfig, lt._key("ip", "127.0.0.1"))
    assert (before.value if before else None) == (after.value if after else None)


# --- on the server -----------------------------------------------------------------------------------------------------------

def test_the_server_command_unlocks_an_account(testapp, locked, dbsession, capsys):
    from namifax.cli.user import run_unlock_user

    assert run_unlock_user(["victim"], session=dbsession) == 0
    assert "unlocked" in capsys.readouterr().out.lower()
    assert _login(_client(testapp), "victim", PW).status_int == 302


def test_the_server_command_says_when_there_is_nothing_to_unlock(victim, dbsession, capsys):
    from namifax.cli.user import run_unlock_user

    assert run_unlock_user(["victim"], session=dbsession) == 1
    assert "not locked" in capsys.readouterr().out.lower()


def test_the_server_command_is_listed(capsys):
    import importlib

    app_main = importlib.import_module("namifax.main")
    assert app_main.main([]) == 0
    assert "unlock-user" in capsys.readouterr().out
