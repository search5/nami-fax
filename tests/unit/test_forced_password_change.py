"""An account that must change its password (reset by an administrator, expired, or never used) cannot get in until it does.

This is how the original AvantFAX behaves; the port computed the flag but ignored it, and its "change password" page
changed nothing.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
import webtest

from namifax.common.passwords import verify_password
from namifax.services.user_account import NFUserAccount

OLD = "OldPassword1!"
NEW = "BrandNewPass2!"


def _account(session, username="carol", **extra):
    values = {"username": username, "password": OLD, "email": f"{username}@corp.test", "name": username.title(),
              "last_login": "2026-01-01 10:00:00", **extra}
    svc = NFUserAccount(db=session)
    assert svc.create(values), svc.error
    session.flush()
    return svc.uid


def _set(session, uid, **values):
    svc = NFUserAccount(db=session)
    assert svc.load(uid)
    svc.dbdata.update(values)
    assert svc.update()
    session.flush()


def _login(client, username="carol", password=OLD):
    return client.post("/login", {"username": username, "password": password, "_submit_check": "1"}, expect_errors=True)


def _in(client):
    return client.get("/inbox", expect_errors=True).status_int == 200


def _change(client, old=OLD, new=NEW, confirm=None):
    return client.post("/pwdexpired", {"oldpwd": old, "newpwd": new, "conpwd": new if confirm is None else confirm,
                                       "_submit_check": "1"}, expect_errors=True)


# --- who is sent to the change page -------------------------------------------------------------------------------------

def test_a_normal_account_goes_straight_in(testapp, dbsession):
    _account(dbsession)
    res = _login(testapp)
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox") and _in(testapp)


@pytest.mark.parametrize("why,values", [
    ("reset by an administrator", {"wasreset": 1}),
    ("expired", {"pwdcycle": 3, "pwdexpire": "2000-01-01"}),
    ("never logged in", {"last_login": None}),
])
def test_accounts_that_must_change_their_password_are_not_let_in(testapp, dbsession, why, values):
    uid = _account(dbsession)
    _set(dbsession, uid, **values)
    res = _login(testapp)
    assert res.status_int == 302 and res.headers["Location"].endswith("/pwdexpired"), why
    assert not _in(testapp)                                    # no login cookie yet


def test_an_expiry_date_in_the_future_is_fine(testapp, dbsession):
    uid = _account(dbsession)
    _set(dbsession, uid, pwdcycle=3, pwdexpire=(datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"))
    assert _login(testapp).headers["Location"].endswith("/inbox")


def test_a_wrong_password_never_reaches_the_change_page(testapp, dbsession):
    uid = _account(dbsession)
    _set(dbsession, uid, wasreset=1)
    res = _login(testapp, password="nope")
    assert res.status_int == 200 and "Invalid username or password" in res.text
    assert testapp.get("/pwdexpired").status_int == 302         # nothing is pending


# --- the change page -----------------------------------------------------------------------------------------------------

def _pending(testapp, dbsession, **values):
    uid = _account(dbsession)
    _set(dbsession, uid, wasreset=1, **values)
    _login(testapp)
    return uid


def test_changing_the_password_logs_the_user_in_and_clears_the_flag(testapp, dbsession):
    uid = _pending(testapp, dbsession, pwdcycle=3)
    res = _change(testapp)
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox") and _in(testapp)
    row = NFUserAccount(db=dbsession)
    assert row.load(uid)
    assert not row.dbdata["wasreset"] and verify_password(row.dbdata["password"], NEW)
    assert row.dbdata["pwdexpire"] > datetime.now().strftime("%Y-%m-%d")          # a new 90 days
    fresh = webtest.TestApp(testapp.app, extra_environ=testapp.extra_environ)
    assert _login(fresh, password=NEW).headers["Location"].endswith("/inbox")      # and the old one is gone
    assert _login(webtest.TestApp(testapp.app, extra_environ=testapp.extra_environ)).status_int == 200


@pytest.mark.parametrize("old,new,confirm,expect", [
    ("wrong", NEW, None, "old password"),
    (OLD, NEW, "Different3!", "do not match"),
    (OLD, "short", None, "too short"),
    (OLD, OLD, None, "already been used"),
    ("", NEW, None, "required"),
])
def test_bad_input_keeps_the_user_on_the_page(testapp, dbsession, old, new, confirm, expect):
    _pending(testapp, dbsession)
    res = _change(testapp, old=old, new=new, confirm=confirm)
    assert res.status_int == 200 and expect in res.text.lower()
    assert not _in(testapp)


def test_the_page_cannot_be_used_to_change_somebody_elses_password(testapp, dbsession):
    victim = _account(dbsession, "victim")
    res = testapp.post("/pwdexpired", {"username": "victim", "oldpwd": OLD, "newpwd": NEW, "conpwd": NEW}, expect_errors=True)
    assert res.status_int == 302 and res.headers["Location"].endswith("/login")
    row = NFUserAccount(db=dbsession)
    assert row.load(victim) and verify_password(row.dbdata["password"], OLD)


def test_two_factor_still_applies_after_the_change(testapp, dbsession):
    from unittest.mock import patch

    from namifax.services.totp import TotpService

    uid = _pending(testapp, dbsession)
    svc = TotpService(dbsession)
    with patch.object(svc, "verify_code", return_value=True):
        codes = svc.enable_totp(uid, svc.generate_secret(), "123456")["backup_codes"]
    res = _change(testapp)
    assert res.headers["Location"].endswith("/login/totp") and not _in(testapp)
    assert testapp.post("/login/totp", {"code": codes[0]}).status_int == 302 and _in(testapp)


def test_the_installers_administrator_must_change_the_default_password(testapp, dbsession):
    """AvantFAX's installer creates admin/password with wasreset set."""
    admin = NFUserAccount(db=dbsession)
    assert admin.load_username("admin")
    admin.dbdata.update({"wasreset": 1})
    admin.update()
    dbsession.flush()
    res = _login(testapp, "admin", "password")
    assert res.headers["Location"].endswith("/pwdexpired")
    assert _change(testapp, old="password", new="Much-better-1!").headers["Location"].endswith("/inbox")


def test_the_demo_accounts_are_not_forced_to_change_their_passwords(testapp):
    assert _login(testapp, "admin", "password").headers["Location"].endswith("/inbox")
