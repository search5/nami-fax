"""Alternate authentication like the original (ALTERNATE_AUTH_ENABLE / _FALLBACK / _CLASS) and the web-server login (REMOTE_USER):
the account must exist in AvantFAX, a disabled one is refused, and the local password is used only when the fallback is on."""

from __future__ import annotations

import pytest
import webtest

from namifax.auth import alternate
from namifax.services.user_account import NFUserAccount
from namifax.services.syslog import SysLogService


class FakeBackend:
    def __init__(self, accept):
        self.accept = accept
        self.calls = []

    def login(self, username, password):
        self.calls.append((username, password))
        return self.accept(username, password)


@pytest.fixture
def local(dbsession):
    svc = NFUserAccount(db=dbsession)
    assert svc.create({"username": "sysuser", "password": "LocalPass123!", "email": "s@x.test", "name": "Sys", "acc_enabled": 1,
                       "last_login": "2026-01-01 10:00:00"})
    dbsession.flush()
    return svc


def _login(app, user, password):
    return webtest.TestApp(app.app, extra_environ=app.extra_environ).post(
        "/login", {"username": user, "password": password, "_submit_check": "1"})


def _enable(monkeypatch, backend, fallback=True):
    monkeypatch.setenv("ALTERNATE_AUTH_ENABLE", "1")
    monkeypatch.setenv("ALTERNATE_AUTH_FALLBACK", "1" if fallback else "0")
    monkeypatch.setattr(alternate, "backend", lambda: backend)


# --- selection --------------------------------------------------------------------------------------------------------------

def test_it_is_off_by_default(monkeypatch):
    monkeypatch.delenv("ALTERNATE_AUTH_ENABLE", raising=False)
    assert alternate.enabled() is False and alternate.fallback() is True


@pytest.mark.parametrize("name,cls", [("PAMAuth", "PAMAuthBackend"), ("PWAuth", "PWAuthBackend")])
def test_the_class_names_of_the_original_are_understood(monkeypatch, name, cls):
    monkeypatch.setenv("ALTERNATE_AUTH_CLASS", name)
    assert type(alternate.backend()).__name__ == cls


def test_an_unknown_class_is_refused(monkeypatch):
    monkeypatch.setenv("ALTERNATE_AUTH_CLASS", "Nonsense")
    assert alternate.backend() is None


def test_pwauth_is_found_by_its_setting(monkeypatch):
    monkeypatch.setenv("ALTERNATE_AUTH_CLASS", "PWAuth")
    monkeypatch.setenv("PWAUTHPATH", "/opt/pwauth")
    assert alternate.backend().binary_path == "/opt/pwauth"


# --- login ------------------------------------------------------------------------------------------------------------------

def test_the_system_password_logs_in(testapp, local, monkeypatch):
    backend = FakeBackend(lambda u, p: (u, p) == ("sysuser", "SystemPass!"))
    _enable(monkeypatch, backend)
    res = _login(testapp, "sysuser", "SystemPass!")
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox")
    assert backend.calls == [("sysuser", "SystemPass!")]


def test_a_wrong_system_password_falls_back_to_the_local_one(testapp, local, monkeypatch):
    _enable(monkeypatch, FakeBackend(lambda u, p: False), fallback=True)
    assert _login(testapp, "sysuser", "LocalPass123!").status_int == 302


def test_without_the_fallback_the_local_password_is_not_enough(testapp, local, monkeypatch):
    _enable(monkeypatch, FakeBackend(lambda u, p: False), fallback=False)
    res = _login(testapp, "sysuser", "LocalPass123!")
    assert res.status_int == 200 and "Invalid username or password" in res.text


def test_a_system_user_without_an_avantfax_account_is_refused_by_name(testapp, local, monkeypatch):
    _enable(monkeypatch, FakeBackend(lambda u, p: True), fallback=False)
    res = _login(testapp, "ghost", "whatever")
    assert res.status_int == 200 and "ghost" in res.text


def test_a_disabled_account_is_refused(testapp, local, dbsession, monkeypatch):
    from sqlalchemy import update

    from namifax.models import UserAccount

    dbsession.execute(update(UserAccount).where(UserAccount.username == "sysuser").values(acc_enabled=0))
    dbsession.flush()
    _enable(monkeypatch, FakeBackend(lambda u, p: True), fallback=False)
    assert "Account is disabled" in _login(testapp, "sysuser", "x").text


def test_the_alternate_login_is_logged(testapp, local, dbsession, monkeypatch):
    _enable(monkeypatch, FakeBackend(lambda u, p: True))
    _login(testapp, "sysuser", "x")
    assert any("login successful for user 'sysuser'" in r["logtext"] for r in SysLogService(dbsession).search(kw="UserAccount>"))


# --- web server authentication ---------------------------------------------------------------------------------------------

def test_the_web_server_login_is_off_unless_asked_for(testapp, local, monkeypatch):
    monkeypatch.delenv("WEBSERVER_AUTH", raising=False)
    client = webtest.TestApp(testapp.app, extra_environ={**testapp.extra_environ, "REMOTE_USER": "sysuser"})
    res = client.get("/login")
    assert res.status_int == 200


def test_remote_user_logs_in_when_the_web_server_authenticates(testapp, local, monkeypatch):
    monkeypatch.setenv("WEBSERVER_AUTH", "1")
    client = webtest.TestApp(testapp.app, extra_environ={**testapp.extra_environ, "REMOTE_USER": "sysuser"})
    res = client.get("/login")
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox")
    assert client.get("/inbox").status_int == 200


def test_an_unknown_remote_user_sees_the_login_page_with_a_message(testapp, local, monkeypatch):
    monkeypatch.setenv("WEBSERVER_AUTH", "1")
    client = webtest.TestApp(testapp.app, extra_environ={**testapp.extra_environ, "REMOTE_USER": "stranger"})
    res = client.get("/login")
    assert res.status_int == 200 and "stranger" in res.text
