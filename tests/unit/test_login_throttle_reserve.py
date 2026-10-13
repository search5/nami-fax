"""A sign-in attempt is counted before its password is looked at.

The view used to ask "is it locked?", check the password and only then record the failure, so requests that arrived together all
passed the first question before any failure was recorded: a burst of 40 wrong passwords had 40 of them checked with a limit of 10.
Now ``begin_attempt`` takes the row locks of the user name and the address, refuses when either is locked and otherwise counts the
attempt at once; a success gives the address its count back (an address is not locked by the successful sign-ins of an office) and
clears the user name. The overlapping requests need a real server (``serverdb``).
"""

from __future__ import annotations

import json
import threading
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from namifax.models import SystemConfig
from namifax.services import login_throttle as lt
from namifax.services.system_config import SystemConfigService
from namifax.services.user_account import NFUserAccount

LIMIT = 3


@pytest.fixture(autouse=True)
def _limits(monkeypatch):
    monkeypatch.setenv("NAMIFAX_LOGIN_MAX_FAILURES", str(LIMIT))
    monkeypatch.setenv("NAMIFAX_LOGIN_LOCK_MINUTES", "15")


@pytest.fixture
def clock(monkeypatch):
    t = {"now": 1_000_000.0}
    monkeypatch.setattr(lt, "_now", lambda: t["now"])
    return t


def _state(session, kind, value):
    raw = SystemConfigService(session).get(lt._key(kind, value), "")
    return json.loads(raw or "{}")


# --- on any database ----------------------------------------------------------------------------------------------------------

def test_the_attempts_up_to_the_limit_are_allowed_and_the_next_is_refused(dbsession, clock):
    throttle = lt.LoginThrottle(dbsession)
    assert [throttle.begin_attempt("alice", None) for _ in range(LIMIT)] == [True] * LIMIT      # the last one is checked, too
    assert throttle.begin_attempt("alice", None) is False
    assert _state(dbsession, "user", "alice")["n"] == LIMIT                                      # a refused attempt is not counted


def test_the_attempt_that_reaches_the_limit_locks_at_once(dbsession, clock):
    throttle = lt.LoginThrottle(dbsession)
    for _ in range(LIMIT):
        throttle.begin_attempt("bob", None)
    assert throttle.is_locked("bob", None) is True


def test_a_locked_user_name_is_refused_without_counting_the_address(dbsession, clock):
    throttle = lt.LoginThrottle(dbsession)
    for _ in range(LIMIT):
        throttle.begin_attempt("carl", None)
    before = _state(dbsession, "ip", "10.0.0.9")
    assert throttle.begin_attempt("carl", "10.0.0.9") is False
    assert _state(dbsession, "ip", "10.0.0.9") == before == {}


def test_a_success_clears_the_user_name_and_gives_the_address_its_count_back(dbsession, clock):
    throttle = lt.LoginThrottle(dbsession)
    throttle.begin_attempt("dana", "10.0.0.5")
    throttle.begin_attempt("dana", "10.0.0.5")
    assert _state(dbsession, "ip", "10.0.0.5")["n"] == 2
    throttle.record_success("dana", "10.0.0.5")                       # the third attempt had the right password
    assert _state(dbsession, "user", "dana") == {}
    assert _state(dbsession, "ip", "10.0.0.5")["n"] == 1             # only the failure counts for the address


def test_a_success_on_the_attempt_that_reached_the_limit_does_not_leave_a_lock(dbsession, clock, monkeypatch):
    monkeypatch.setenv("NAMIFAX_LOGIN_MAX_FAILURES", "1")             # the address limit is IP_FACTOR times this
    throttle = lt.LoginThrottle(dbsession)
    last = lt.IP_FACTOR
    for i in range(last - 1):
        throttle.begin_attempt(f"user{i}", "10.0.0.6")                # failures on the address, one short of its limit
    reaching = lt.LoginThrottle(dbsession)
    assert reaching.begin_attempt("final", "10.0.0.6") is True       # this one reaches the limit and locks the address
    assert throttle.is_locked("someone-else", "10.0.0.6") is True
    reaching.record_success("final", "10.0.0.6")                      # ... but its password was right
    assert throttle.is_locked("someone-else", "10.0.0.6") is False
    assert _state(dbsession, "ip", "10.0.0.6")["n"] == last - 1


def test_the_lock_of_an_account_does_not_end_with_time(dbsession, clock):
    throttle = lt.LoginThrottle(dbsession)
    for _ in range(LIMIT):
        throttle.begin_attempt("erin", None)
    for later in (15 * 60 + 1, 24 * 3600, 365 * 24 * 3600):
        clock["now"] += later
        assert throttle.begin_attempt("erin", None) is False
    assert _state(dbsession, "user", "erin")["n"] == LIMIT


def test_the_login_view_does_not_look_at_the_password_of_a_locked_user_name(testapp, dbsession, clock):
    assert NFUserAccount(db=dbsession).create({"username": "thr2", "password": "Secret123!", "email": "t2@x.test", "name": "T",
                                               "acc_enabled": 1, "last_login": "2026-01-01 10:00:00"})
    dbsession.flush()
    for _ in range(LIMIT):
        testapp.post("/login", {"username": "thr2", "password": "wrong", "_submit_check": "1"})
    with patch.object(NFUserAccount, "login", side_effect=AssertionError("the password was checked")):
        res = testapp.post("/login", {"username": "thr2", "password": "Secret123!", "_submit_check": "1"})
    assert "Too many failed sign-in attempts" in res.text


# --- overlapping requests (a real server) -----------------------------------------------------------------------------------

@pytest.fixture
def engine(server_db_url):
    from namifax.db.bootstrap import ensure_schema
    from namifax.db.provider import create_sa_engine

    engine = create_sa_engine(server_db_url)
    ensure_schema(engine)
    yield engine
    engine.dispose()


def _together(count, work):
    barrier, outcome = threading.Barrier(count), []

    def request(i):
        try:
            barrier.wait()
            outcome.append(work(i))
        except Exception as exc:
            outcome.append(repr(exc)[:120])

    threads = [threading.Thread(target=request, args=(i,)) for i in range(count)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return outcome


@pytest.mark.serverdb
def test_of_forty_attempts_that_arrive_together_only_the_limit_is_let_through(engine):
    def attempt(i):
        with Session(engine) as session:
            allowed = lt.LoginThrottle(session).begin_attempt("burst", None)
            session.commit()
            return allowed

    outcome = _together(40, attempt)
    assert sorted(map(str, outcome)) == sorted(["True"] * LIMIT + ["False"] * (40 - LIMIT))
    with Session(engine) as session:
        assert json.loads(session.get(SystemConfig, lt._key("user", "burst")).value)["n"] == LIMIT


@pytest.mark.serverdb
def test_a_burst_through_the_login_view_has_only_the_limit_checked_for_its_password(server_db_url):
    import webtest

    from namifax import create_app

    app = create_app(**{"sqlalchemy.url": server_db_url})
    with Session(app.registry["dbengine"]) as session:
        assert NFUserAccount(db=session).create({"username": "victim", "password": "Correct-pw-1", "email": "v@x.test", "name": "V",
                                                 "acc_enabled": 1, "last_login": "2026-01-01 10:00:00"})
        session.commit()
    checked, real_login = [], NFUserAccount.login

    def counting_login(self, *args, **kwargs):
        checked.append(1)
        return real_login(self, *args, **kwargs)

    def attack(i):
        client = webtest.TestApp(app, extra_environ={"HTTP_HOST": "example.com", "REMOTE_ADDR": f"10.8.0.{i}"})
        return client.post("/login", {"username": "victim", "password": f"wrong-{i}", "_submit_check": "1"}, expect_errors=True).text

    with patch.object(NFUserAccount, "login", counting_login):
        pages = _together(30, attack)
    assert len(checked) == LIMIT                                        # not 30
    assert not [p for p in pages if "unavailable" in p.lower()]
    assert sum("Too many failed sign-in attempts" in p for p in pages) == 30 - LIMIT
