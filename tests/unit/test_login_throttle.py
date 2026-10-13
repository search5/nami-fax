"""Repeated failed password sign-ins lock the user name (existing or not) until an administrator unlocks it; a success clears the count.

An address that fails many times is locked for a while only (an address can be a whole office or a proxy)."""

from __future__ import annotations

import pytest

from namifax.services import login_throttle
from namifax.services.user_account import NFUserAccount

LOCKED = "Too many failed sign-in attempts"


@pytest.fixture(autouse=True)
def _limits(monkeypatch):
    monkeypatch.setenv("NAMIFAX_LOGIN_MAX_FAILURES", "3")
    monkeypatch.setenv("NAMIFAX_LOGIN_LOCK_MINUTES", "15")


@pytest.fixture
def clock(monkeypatch):
    t = {"now": 1_000_000.0}
    monkeypatch.setattr(login_throttle, "_now", lambda: t["now"])
    return t


@pytest.fixture
def account(dbsession):
    assert NFUserAccount(db=dbsession).create({"username": "thr", "password": "Secret123!", "email": "t@x.test", "name": "T",
                                               "acc_enabled": 1, "last_login": "2026-01-01 10:00:00"})
    dbsession.flush()


def _login(app, name, password):
    return app.post("/login", {"username": name, "password": password, "_submit_check": "1"})


def test_the_defaults_are_five_failures_and_fifteen_minutes_for_an_address(monkeypatch):
    monkeypatch.delenv("NAMIFAX_LOGIN_MAX_FAILURES")
    monkeypatch.delenv("NAMIFAX_LOGIN_LOCK_MINUTES")
    assert login_throttle.max_failures() == 5 and login_throttle.lock_seconds() == 900


def test_too_many_failures_lock_even_the_right_password(testapp, account, clock):
    for _ in range(3):
        assert "Invalid username or password" in _login(testapp, "thr", "wrong").text
    res = _login(testapp, "thr", "Secret123!")
    assert LOCKED in res.text and res.status_int == 200                       # not signed in
    assert testapp.get("/inbox", expect_errors=True).status_int != 200


def test_the_lock_of_an_account_does_not_end_with_time(testapp, account, clock):
    for _ in range(3):
        _login(testapp, "thr", "wrong")
    for later in (15 * 60 + 1, 24 * 3600, 30 * 24 * 3600):
        clock["now"] += later
        res = _login(testapp, "thr", "Secret123!")
        assert LOCKED in res.text and res.status_int == 200


def test_a_success_clears_the_count(testapp, account, clock):
    for _ in range(2):
        _login(testapp, "thr", "wrong")
    assert _login(testapp, "thr", "Secret123!").status_int == 302
    for _ in range(2):                                                         # two more would have been the fourth
        assert "Invalid username or password" in _login(testapp, "thr", "wrong").text


def test_an_unknown_user_name_is_limited_the_same_way(testapp, clock):
    for _ in range(3):
        assert "Invalid username or password" in _login(testapp, "nobody", "x").text
    assert LOCKED in _login(testapp, "nobody", "x").text


def test_the_lock_is_per_user_name(testapp, account, clock):
    for _ in range(3):
        _login(testapp, "other", "x")
    assert _login(testapp, "thr", "Secret123!").status_int == 302


def test_failures_do_not_expire_only_a_success_clears_them(testapp, account, clock):
    for _ in range(2):
        _login(testapp, "thr", "wrong")
    clock["now"] += 3 * 24 * 3600                                              # days later: they still count
    _login(testapp, "thr", "wrong")
    assert LOCKED in _login(testapp, "thr", "Secret123!").text


def test_an_address_is_locked_for_a_while_only(dbsession, clock):
    throttle = login_throttle.LoginThrottle(dbsession)
    for i in range(3 * login_throttle.IP_FACTOR):
        throttle.record_failure(f"user{i}", "203.0.113.20")
    assert throttle.is_locked("fresh-name", "203.0.113.20")
    clock["now"] += 15 * 60 + 1
    assert not throttle.is_locked("fresh-name", "203.0.113.20")


def test_one_address_trying_many_names_is_locked_at_a_higher_limit(dbsession, clock):
    throttle = login_throttle.LoginThrottle(dbsession)
    for i in range(3 * login_throttle.IP_FACTOR):
        assert not throttle.is_locked(f"user{i}", "203.0.113.9")
        throttle.record_failure(f"user{i}", "203.0.113.9")
    assert throttle.is_locked("brand-new-name", "203.0.113.9")
    assert not throttle.is_locked("brand-new-name", "203.0.113.10")


def test_the_state_is_in_the_database_not_the_process(dbsession, clock):
    for _ in range(3):
        login_throttle.LoginThrottle(dbsession).record_failure("shared", "1.1.1.1")
    assert login_throttle.LoginThrottle(dbsession).is_locked("shared")
