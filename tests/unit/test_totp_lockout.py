"""Brute-force protection for the second factor: a 6-digit code must not be guessable by trying them all."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import alembic.command
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from namifax.services.totp import LOCK_MINUTES, MAX_FAILED_ATTEMPTS, TotpService


@pytest.fixture(params=["session", "engine"])
def svc(request, dbsession, seeded_db):
    return TotpService(dbsession if request.param == "session" else seeded_db)


def _enable(svc, uid=1):
    with patch.object(svc, "verify_code", return_value=True):
        return svc.enable_totp(uid, svc.generate_secret(), "123456")["backup_codes"]


def _fail(svc, n, uid=1):
    for _ in range(n):
        assert svc.verify_user_login(uid, "000000") is False


def _row(svc, uid=1):
    row = svc._rows(uid).find({"uid": uid})
    return row[0] if isinstance(row, list) else row


def test_the_limits_are_sane():
    assert 3 <= MAX_FAILED_ATTEMPTS <= 10 and 5 <= LOCK_MINUTES <= 60


def test_wrong_codes_are_counted_and_the_account_locks(svc):
    codes = _enable(svc)
    _fail(svc, MAX_FAILED_ATTEMPTS - 1)
    assert svc.is_locked(1) is False
    assert svc.verify_user_login(1, "000000") is False                       # the last allowed failure ...
    assert svc.is_locked(1) is True and 0 < svc.lock_remaining_seconds(1) <= LOCK_MINUTES * 60
    # ... and now even a correct recovery code is refused until the lock ends
    assert svc.verify_user_login(1, codes[0]) is False


def test_a_correct_code_inside_the_limit_resets_the_counter(svc):
    codes = _enable(svc)
    _fail(svc, MAX_FAILED_ATTEMPTS - 1)
    assert svc.verify_user_login(1, codes[0]) is True
    assert int(_row(svc)["failed_attempts"] or 0) == 0
    _fail(svc, MAX_FAILED_ATTEMPTS - 1)                                      # a fresh allowance
    assert svc.is_locked(1) is False


def test_the_lock_expires(svc):
    codes = _enable(svc)
    _fail(svc, MAX_FAILED_ATTEMPTS)
    assert svc.is_locked(1)
    past = (datetime.now() - timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
    svc._rows(1).update_where({"uid": 1}, {"locked_until": past})
    assert svc.is_locked(1) is False
    assert svc.verify_user_login(1, codes[1]) is True
    row = _row(svc)
    assert int(row["failed_attempts"] or 0) == 0 and not row["locked_until"]


def test_a_failure_after_the_lock_expired_starts_counting_again(svc):
    _enable(svc)
    _fail(svc, MAX_FAILED_ATTEMPTS)
    past = (datetime.now() - timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S")
    svc._rows(1).update_where({"uid": 1}, {"locked_until": past})
    _fail(svc, 1)
    assert svc.is_locked(1) is False and int(_row(svc)["failed_attempts"]) == 1   # not instantly locked again


def test_locks_are_per_user(svc):
    _enable(svc, 1)
    codes2 = _enable(svc, 2)
    _fail(svc, MAX_FAILED_ATTEMPTS, uid=1)
    assert svc.is_locked(1) and not svc.is_locked(2)
    assert svc.verify_user_login(2, codes2[0]) is True


def test_users_without_2fa_are_never_locked_out(svc):
    assert svc.is_locked(5) is False and svc.verify_user_login(5, "x") is True
    assert svc.lock_remaining_seconds(5) == 0


def test_enabling_again_clears_an_old_lock(svc):
    _enable(svc)
    _fail(svc, MAX_FAILED_ATTEMPTS)
    assert svc.is_locked(1)
    _enable(svc)                                                              # re-enrolled by the user
    assert svc.is_locked(1) is False and int(_row(svc)["failed_attempts"] or 0) == 0


# --- the login page ------------------------------------------------------------------------------------------

def test_the_login_page_stops_guessing_and_says_why(testapp, dbsession):
    codes = TotpService(dbsession)
    with patch.object(codes, "verify_code", return_value=True):
        recovery = codes.enable_totp(1, codes.generate_secret(), "123456")["backup_codes"]
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})

    for _ in range(MAX_FAILED_ATTEMPTS):
        assert testapp.post("/login/totp", {"code": "000000"}).status_int == 200
    locked = testapp.post("/login/totp", {"code": recovery[0]})            # the right code, but too late
    assert locked.status_int == 200 and "Too many" in locked.text
    assert testapp.get("/inbox", expect_errors=True).status_int != 200


# --- schema ---------------------------------------------------------------------------------------------------

def test_existing_sqlite_databases_get_the_new_columns(tmp_path):
    """A database made before the lockout existed is upgraded in place, keeping the enrolled secret."""
    import sqlite3

    from namifax.db.bootstrap import ensure_schema
    from namifax.db.provider import create_sa_engine

    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE UserTOTP (uid INTEGER PRIMARY KEY, secret_key TEXT NOT NULL, is_enabled INTEGER DEFAULT 0, "
                "backup_codes TEXT, created_at TEXT)")
    con.execute("INSERT INTO UserTOTP (uid, secret_key, is_enabled) VALUES (9, 'SECRET', 1)")
    con.commit()
    con.close()
    engine = create_sa_engine(f"sqlite:///{path}")
    ensure_schema(engine)
    ensure_schema(engine)
    with engine.connect() as c:
        row = c.execute(sa.text("SELECT secret_key, failed_attempts, locked_until FROM UserTOTP WHERE uid = 9")).one()
    assert tuple(row) == ("SECRET", 0, None)
    engine.dispose()


@pytest.mark.serverdb
def test_server_database(monkeypatch, server_db_url, alembic_cfg):
    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(server_db_url)
    try:
        with Session(engine) as s:
            t = TotpService(s)
            codes = _enable(t, 7)
            _fail(t, MAX_FAILED_ATTEMPTS, uid=7)
            assert t.is_locked(7) and t.verify_user_login(7, codes[0]) is False
            s.commit()
        with Session(engine) as s:
            assert TotpService(s).is_locked(7) is True               # the lock is stored, not kept in memory
    finally:
        engine.dispose()
