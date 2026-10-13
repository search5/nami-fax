"""Lost password (the original forgot.php): a new temporary password is e-mailed and must be changed at the next login.

The original wrote the new password in clear text to the system log; this one does not.
"""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest
import webtest
from sqlalchemy import select

from namifax.models import SysLog, UserAccount
from namifax.services.user_account import NFUserAccount

OLD = "Old-pass-123"


@pytest.fixture
def account(dbsession):
    svc = NFUserAccount(db=dbsession)
    assert svc.create({"username": "forgetful", "password": OLD, "email": "forgetful@corp.test", "name": "Forgetful",
                       "last_login": "2026-01-01 10:00:00", "acc_enabled": 1}), svc.error
    dbsession.flush()
    return svc.get_uid()


@pytest.fixture
def mail():
    sent = []

    def fake(to, from_addr, subject, text, **kw):
        sent.append({"to": to, "from": from_addr, "subject": subject, "text": text})
        return True

    with patch("namifax.views.auth.send_mail", fake):
        yield sent


def _ask(testapp, email, ip="203.0.113.7"):
    return testapp.post("/forgot", {"email": email, "_submit_check": "1"}, extra_environ={"REMOTE_ADDR": ip}, expect_errors=True)


def _login_status(testapp, username, password):
    other = webtest.TestApp(testapp.app, extra_environ=testapp.extra_environ)
    res = other.post("/login", {"username": username, "password": password, "_submit_check": "1"})
    return res.status_int, res.headers.get("Location", "")


def _logs(session):
    session.expire_all()
    return [r.logtext for r in session.execute(select(SysLog)).scalars()]


def test_the_page_asks_for_an_email_address(testapp):
    page = testapp.get("/forgot")
    assert 'name="email"' in page.text and 'name="username"' not in page.text


def test_a_known_email_gets_a_new_password_by_mail(testapp, account, mail):
    res = _ask(testapp, "forgetful@corp.test")
    assert res.status_int == 200 and "sent to the given e-mail address" in res.text
    (message,) = mail
    assert message["to"] == "forgetful@corp.test" and message["subject"] == "password reset"
    assert "forgetful" in message["text"] and "203.0.113.7" in message["text"]
    assert re.search(r"Your New Password is: \S{8,}", message["text"])


def test_the_mailed_password_works_and_the_old_one_does_not(testapp, account, mail):
    _ask(testapp, "forgetful@corp.test")
    new = re.search(r"Your New Password is: (\S+)", mail[0]["text"]).group(1)
    assert _login_status(testapp, "forgetful", OLD)[0] == 200                     # refused: the login page again
    status, location = _login_status(testapp, "forgetful", new)
    assert status == 302 and location.endswith("/pwdexpired")                     # it has to be changed first


def test_after_asking_the_form_gives_way_to_a_login_link(testapp, account, mail):
    page = _ask(testapp, "forgetful@corp.test")
    assert 'name="email"' not in page.text and 'href="/login"' in page.text


def test_an_unknown_email_is_refused_and_logged(testapp, account, mail, dbsession):
    res = _ask(testapp, "nobody@corp.test")
    assert "Sorry, no corresponding user was found." in res.text and mail == []
    assert _login_status(testapp, "forgetful", OLD)[1].endswith("/inbox")         # nothing changed
    assert any("nobody@corp.test" in t and "203.0.113.7" in t for t in _logs(dbsession))


@pytest.mark.parametrize("value", ["", "not-an-address", "a b@corp.test"])
def test_something_that_is_not_an_email_address_is_refused(testapp, account, mail, value):
    res = _ask(testapp, value)
    assert "Please enter a valid e-mail address." in res.text and mail == []


def test_a_failed_mail_leaves_the_old_password_in_place(testapp, account):
    with patch("namifax.views.auth.send_mail", return_value=False):
        res = _ask(testapp, "forgetful@corp.test")
    assert "Email failed to send" in res.text
    assert _login_status(testapp, "forgetful", OLD)[1].endswith("/inbox")         # not locked out by a mail that never came


def test_the_new_password_is_not_written_to_the_log(testapp, account, mail, dbsession):
    _ask(testapp, "forgetful@corp.test")
    new = re.search(r"Your New Password is: (\S+)", mail[0]["text"]).group(1)
    logs = _logs(dbsession)
    assert any("forgetful" in t and "203.0.113.7" in t for t in logs) and not any(new in t for t in logs)


def test_a_deleted_account_is_not_reset(testapp, account, mail, dbsession):
    row = dbsession.execute(select(UserAccount).where(UserAccount.username == "forgetful")).scalar_one()
    row.deleted = 1
    dbsession.flush()
    assert "no corresponding user" in _ask(testapp, "forgetful@corp.test").text and mail == []


def test_the_email_is_matched_whatever_its_case(testapp, account, mail):
    assert "sent to the given e-mail address" in _ask(testapp, "Forgetful@Corp.Test").text
