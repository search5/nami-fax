"""Logins are written to the system log like the original: success, and failure with the password masked to its last three
characters; a disabled account is told apart from a wrong password."""

from __future__ import annotations

import pytest

from namifax.services.syslog import SysLogService
from namifax.services.user_account import NFUserAccount


def _logs(session):
    return [r["logtext"] for r in SysLogService(session).search(kw="UserAccount>")]


@pytest.fixture
def account(dbsession):
    svc = NFUserAccount(db=dbsession)
    assert svc.create({"username": "audit", "password": "Secret123!", "email": "a@x.test", "name": "A", "acc_enabled": 1,
                       "last_login": "2026-01-01 10:00:00"})
    dbsession.flush()
    return svc


def test_a_good_login_is_logged_with_the_address(dbsession, account):
    assert NFUserAccount(db=dbsession).login("audit", "Secret123!", remote_ip="10.1.2.3")
    assert any("Login successful for 'audit' from IP: '10.1.2.3'" in t for t in _logs(dbsession))


def test_a_bad_login_is_logged_with_the_password_masked(dbsession, account):
    user = NFUserAccount(db=dbsession)
    assert not user.login("audit", "WrongPass999", remote_ip="10.1.2.4")
    entry = next(t for t in _logs(dbsession) if "failed login attempt" in t)
    assert "'audit'" in entry and "XXXXXX999" in entry and "10.1.2.4" in entry and "WrongPass" not in entry
    assert user.get_error() == "Incorrect username or password"


def test_a_disabled_account_gets_its_own_message_and_a_log_line(dbsession, account):
    from sqlalchemy import update

    from namifax.models import UserAccount

    dbsession.execute(update(UserAccount).where(UserAccount.username == "audit").values(acc_enabled=0))
    dbsession.flush()
    user = NFUserAccount(db=dbsession)
    assert not user.login("audit", "Secret123!", remote_ip="10.1.2.5")
    assert user.get_error() == "Account is disabled"
    assert any("failed login attempt for 'audit'" in t for t in _logs(dbsession))


def test_the_login_page_names_a_disabled_account(testapp, dbsession, account):
    from sqlalchemy import update

    from namifax.models import UserAccount

    dbsession.execute(update(UserAccount).where(UserAccount.username == "audit").values(acc_enabled=0))
    dbsession.flush()
    res = testapp.post("/login", {"username": "audit", "password": "Secret123!", "_submit_check": "1"})
    assert "Account is disabled" in res.text
    res = testapp.post("/login", {"username": "audit", "password": "wrong", "_submit_check": "1"})
    assert "Invalid username or password" in res.text and "Account is disabled" not in res.text
