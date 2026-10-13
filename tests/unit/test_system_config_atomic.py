"""SystemConfig keys and the login counters are written correctly when requests overlap.

``SystemConfigService.set`` used to be ``merge`` (read, then INSERT or UPDATE): two connections creating the same key at once made one
fail with a duplicate key, and on MySQL/MariaDB a transaction that had read earlier did not see a key committed meanwhile and tried to
INSERT it again. The login counters read, added one and wrote, so parallel failures were counted once. Now ``set`` updates first and
only creates a missing row (a lost race is not an error), and the counters are changed under a row lock.

The plain behaviour is tried on every database; the overlapping requests need a real server (``serverdb``).
"""

from __future__ import annotations

import json
import threading

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from namifax.models import SystemConfig
from namifax.services import login_throttle as lt
from namifax.services.system_config import SystemConfigService


# --- behaviour on any database ------------------------------------------------------------------------------------------------

def test_set_creates_a_missing_key_and_replaces_an_existing_one(dbsession):
    svc = SystemConfigService(dbsession)
    svc.set("atomic-a", "1")
    assert svc.get("atomic-a") == "1"
    svc.set("atomic-a", "2")
    assert svc.get("atomic-a") == "2"


def test_a_value_read_before_a_set_is_the_new_value_afterwards(dbsession):
    svc = SystemConfigService(dbsession)
    svc.set("atomic-b", "old")
    assert dbsession.get(SystemConfig, "atomic-b").value == "old"        # the row is in the session
    svc.set("atomic-b", "new")
    assert dbsession.get(SystemConfig, "atomic-b").value == "new"
    assert svc.get("atomic-b") == "new"


def test_set_keeps_the_other_keys_and_accepts_an_empty_value(dbsession):
    svc = SystemConfigService(dbsession)
    svc.set("atomic-c", "x")
    svc.set("atomic-d", "")
    assert (svc.get("atomic-c"), svc.get("atomic-d", "default")) == ("x", "")


def test_locked_update_gives_the_function_the_old_value_and_stores_its_answer(dbsession):
    svc = SystemConfigService(dbsession)
    assert svc.locked_update("atomic-e", lambda old: old + "a") == "a"       # a missing key starts empty
    assert svc.locked_update("atomic-e", lambda old: old + "b") == "ab"
    assert svc.get("atomic-e") == "ab"


def test_a_failure_is_counted_once_for_every_call(dbsession):
    throttle = lt.LoginThrottle(dbsession)
    for _ in range(4):
        throttle.record_failure("counted-user", None)
    assert json.loads(SystemConfigService(dbsession).get(lt._key("user", "counted-user")))["n"] == 4


# --- overlapping requests (a real server) -----------------------------------------------------------------------------------

@pytest.fixture
def engine(server_db_url):
    from namifax.db.bootstrap import ensure_schema
    from namifax.db.provider import create_sa_engine

    engine = create_sa_engine(server_db_url)
    ensure_schema(engine)
    yield engine
    engine.dispose()


def _together(engine, count, work):
    """``count`` requests that start at the same moment, each with its own session and transaction (committed at the end)."""
    barrier, outcome = threading.Barrier(count), []

    def request(i):
        session = Session(engine)
        try:
            barrier.wait()
            work(session, i)
            session.commit()
            outcome.append("ok")
        except Exception as exc:                                            # the request would end as an error page
            session.rollback()
            outcome.append(repr(exc)[:120])
        finally:
            session.close()

    threads = [threading.Thread(target=request, args=(i,)) for i in range(count)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return outcome


def _raw(engine, key):
    with Session(engine) as session:
        row = session.get(SystemConfig, key)
        return row.value if row else None


@pytest.mark.serverdb
def test_connections_creating_the_same_key_together_all_succeed(engine):
    outcome = _together(engine, 12, lambda s, i: SystemConfigService(s).set("race-key", str(i)))
    assert outcome == ["ok"] * 12
    assert _raw(engine, "race-key") in {str(i) for i in range(12)}


@pytest.mark.serverdb
def test_a_transaction_that_read_early_can_still_set_a_key_committed_meanwhile(engine):
    """MySQL/MariaDB: its snapshot does not show the key that another connection committed after the first read."""
    early = Session(engine)
    assert early.get(SystemConfig, "stale-key") is None                      # the first read: the snapshot is taken here
    with Session(engine) as other:
        SystemConfigService(other).set("stale-key", "from-other")
        other.commit()
    SystemConfigService(early).set("stale-key", "from-early")                # used to fail: duplicate key
    early.commit()
    early.close()
    assert _raw(engine, "stale-key") == "from-early"


@pytest.mark.serverdb
def test_failures_that_arrive_together_are_all_counted(engine, monkeypatch):
    monkeypatch.setenv("NAMIFAX_LOGIN_MAX_FAILURES", "100")                # far from the limit: this test is about the counting
    outcome = _together(engine, 8, lambda s, i: lt.LoginThrottle(s).record_failure("burst-user", None))
    assert outcome == ["ok"] * 8
    assert json.loads(_raw(engine, lt._key("user", "burst-user")))["n"] == 8


@pytest.mark.serverdb
def test_failures_on_an_existing_counter_are_all_counted(engine, monkeypatch):
    monkeypatch.setenv("NAMIFAX_LOGIN_MAX_FAILURES", "100")
    with Session(engine) as session:
        SystemConfigService(session).set(lt._key("user", "known-user"), json.dumps({"n": 3, "start": lt._now()}))
        session.commit()
    outcome = _together(engine, 5, lambda s, i: lt.LoginThrottle(s).record_failure("known-user", None))
    assert outcome == ["ok"] * 5
    assert json.loads(_raw(engine, lt._key("user", "known-user")))["n"] == 8


@pytest.mark.serverdb
def test_a_burst_over_the_limit_locks_the_account_and_stops_counting(engine):
    outcome = _together(engine, 25, lambda s, i: lt.LoginThrottle(s).record_failure("attacked-user", None))
    assert outcome == ["ok"] * 25
    state = json.loads(_raw(engine, lt._key("user", "attacked-user")))
    assert state["n"] == lt.max_failures() and state["locked"] is True


@pytest.mark.serverdb
def test_a_failure_after_an_early_read_is_counted_and_does_not_fail(engine):
    """The login view asks ``is_locked`` first (a read) and records the failure later, after other requests have committed."""
    early = Session(engine)
    assert lt.LoginThrottle(early).is_locked("late-user", None) is False
    with Session(engine) as other:
        lt.LoginThrottle(other).record_failure("late-user", None)
        other.commit()
    lt.LoginThrottle(early).record_failure("late-user", None)
    early.commit()
    early.close()
    assert json.loads(_raw(engine, lt._key("user", "late-user")))["n"] == 2


@pytest.mark.serverdb
def test_a_wrong_password_burst_through_the_login_view_locks_without_error_pages(server_db_url):
    import webtest

    from namifax import create_app
    from namifax.services.user_account import NFUserAccount

    app = create_app(**{"sqlalchemy.url": server_db_url})
    engine = app.registry["dbengine"]
    with Session(engine) as session:
        user = NFUserAccount(db=session)
        assert user.create({"username": "victim", "password": "Correct-pw-1", "email": "v@x.test", "name": "V", "acc_enabled": 1,
                            "last_login": "2026-01-01 10:00:00"}), user.error
        session.commit()
    barrier, codes = threading.Barrier(30), []

    def attack(i):
        client = webtest.TestApp(app, extra_environ={"HTTP_HOST": "example.com", "REMOTE_ADDR": f"10.7.0.{i}"})
        barrier.wait()
        codes.append(client.post("/login", {"username": "victim", "password": f"wrong-{i}", "_submit_check": "1"},
                                 expect_errors=True).text)

    threads = [threading.Thread(target=attack, args=(i,)) for i in range(30)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not [page for page in codes if "database" in page.lower() and "unavailable" in page.lower()]
    state = json.loads(_raw(engine, lt._key("user", "victim")))
    assert state["n"] == lt.max_failures() and state["locked"] is True
