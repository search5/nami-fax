"""Users can turn two-factor authentication on and off themselves (the settings page used to link nowhere)."""

from __future__ import annotations

import re

import pyotp
import pytest

from namifax.models import UserTOTP
from namifax.services.totp import TotpService
from request_identity import set_identity


def _login(client, username="admin", password="password"):
    return client.post("/login", {"username": username, "password": password, "_submit_check": "1"})


def _token(page):
    return re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)


def _secret(page):
    return re.search(r'data-secret="([A-Z2-7]+)"', page.text).group(1)


def _codes(page):
    return list(dict.fromkeys(re.findall(r"\b[A-Z2-9]{5}-[A-Z2-9]{5}\b", page.text)))        # (shown, copied, saved: once each)


@pytest.fixture
def client(testapp):
    _login(testapp)
    return testapp


def _setup(client):
    page = client.get("/settings/2fa/setup")
    return page, _secret(page), _token(page)


def _enable(client):
    page, secret, token = _setup(client)
    done = client.post("/settings/2fa/enable", {"csrf_token": token, "code": pyotp.TOTP(secret).now()})
    return secret, done


# --- the settings page ------------------------------------------------------------------------------------------

def test_the_settings_page_links_to_the_real_setup_page(client):
    page = client.get("/settings")
    assert 'href="/settings/2fa/setup"' in page.text and "/login/totp?setup=1" not in page.text


def test_the_settings_page_offers_disable_and_recovery_once_enabled(client):
    _enable(client)
    page = client.get("/settings")
    assert "/settings/2fa/disable" in page.text and "/settings/2fa/recovery" in page.text
    assert "8" in re.search(r"(\d+) recovery codes? left", page.text).group(1)


# --- setup -----------------------------------------------------------------------------------------------------------

def test_the_setup_page_shows_the_secret_the_uri_and_a_qr_code(client):
    page, secret, _ = _setup(client)
    assert page.status_int == 200
    assert f"secret={secret}" in page.text and "otpauth://totp/" in page.text and "NamiFAX" in page.text
    assert "<svg" in page.text and "admin" in page.text


def test_the_pending_secret_is_not_kept_in_the_clear():
    from pyramid import testing

    from namifax.views import settings_2fa

    req = testing.DummyRequest()
    set_identity(req, {"username": "admin", "uid": 1})
    req.session = {}
    req.dbsession = object()
    settings_2fa.begin_enrolment(req)
    assert req.session["totp_pending"].startswith("enc:v1:")
    assert settings_2fa.pending_secret(req) == settings_2fa.pending_secret(req) and len(settings_2fa.pending_secret(req)) >= 16


def test_enabling_needs_the_right_code(client, dbsession):
    page, secret, token = _setup(client)
    wrong = client.post("/settings/2fa/enable", {"csrf_token": token, "code": "000000"})
    assert wrong.status_int == 200 and "did not match" in wrong.text
    assert TotpService(dbsession).is_totp_enabled(1) is False
    assert _secret(wrong) == secret                                       # the same QR code stays valid for the retry


def test_enabling_shows_recovery_codes_once_and_stores_only_hashes(client, dbsession):
    secret, done = _enable(client)
    codes = _codes(done)
    assert done.status_int == 200 and len(set(codes)) == 8
    row = dbsession.get(UserTOTP, 1)
    assert row.is_enabled and secret not in row.secret_key and not any(c in row.backup_codes for c in codes)
    assert TotpService(dbsession).verify_user_login(1, codes[0]) is True
    assert _codes(client.get("/settings")) == []                           # never shown again


def test_enabling_without_a_started_setup_goes_back_to_setup(client):
    token = _token(client.get("/settings/2fa/setup"))
    fresh = client.app                                                      # a request with no pending secret
    other = type(client)(fresh, extra_environ=client.extra_environ)
    _login(other)
    res = other.post("/settings/2fa/enable", {"csrf_token": token, "code": "123456"}, expect_errors=True)
    assert res.status_int in (302, 400, 403)


def test_a_request_without_the_csrf_token_is_refused(client, dbsession):
    _, secret, _ = _setup(client)
    res = client.post("/settings/2fa/enable", {"code": pyotp.TOTP(secret).now()}, expect_errors=True)
    assert res.status_int in (400, 403) and TotpService(dbsession).is_totp_enabled(1) is False


def test_only_signed_in_users_can_reach_the_pages(testapp):
    for path in ("/settings/2fa/setup",):
        assert testapp.get(path, expect_errors=True).status_int != 200


def test_without_an_encryption_key_setup_explains_instead_of_failing(client, monkeypatch):
    monkeypatch.delenv("NAMIFAX_SECRET_KEY")
    page = client.get("/settings/2fa/setup", expect_errors=True)
    assert page.status_int == 200 and "NAMIFAX_SECRET_KEY" in page.text and "data-secret" not in page.text


# --- using it ----------------------------------------------------------------------------------------------------------

def test_after_enabling_the_next_login_needs_a_code(testapp, dbsession):
    _login(testapp)
    _, done = _enable(testapp)
    codes = _codes(done)
    second = type(testapp)(testapp.app, extra_environ=testapp.extra_environ)
    step = second.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    assert step.headers["Location"].endswith("/login/totp")
    assert second.post("/login/totp", {"code": codes[0]}).status_int == 302
    assert second.get("/inbox", expect_errors=True).status_int == 200


# --- disabling ----------------------------------------------------------------------------------------------------------

def _disable(client, token, password="password", code=""):
    return client.post("/settings/2fa/disable", {"csrf_token": token, "password": password, "code": code}, expect_errors=True)


def test_disabling_needs_the_password_and_a_valid_code(client, dbsession):
    secret, done = _enable(client)
    token = _token(client.get("/settings"))
    assert "password" in _disable(client, token, password="wrong", code=pyotp.TOTP(secret).now()).text.lower()
    assert TotpService(dbsession).is_totp_enabled(1) is True
    assert _disable(client, token, code="000000").status_int == 200
    assert TotpService(dbsession).is_totp_enabled(1) is True
    res = _disable(client, token, code=pyotp.TOTP(secret).now())
    assert res.status_int == 302 and TotpService(dbsession).is_totp_enabled(1) is False


def test_wrong_codes_while_disabling_count_towards_the_lockout(client, dbsession):
    from namifax.services.totp import MAX_FAILED_ATTEMPTS

    _enable(client)
    token = _token(client.get("/settings"))
    for _ in range(MAX_FAILED_ATTEMPTS):
        _disable(client, token, code="000000")
    assert TotpService(dbsession).is_locked(1) is True


def test_a_recovery_code_can_disable_2fa_too(client, dbsession):
    _, done = _enable(client)
    code = _codes(done)[0]
    token = _token(client.get("/settings"))
    assert _disable(client, token, code=code).status_int == 302
    assert TotpService(dbsession).is_totp_enabled(1) is False


# --- new recovery codes -----------------------------------------------------------------------------------------------------

def test_new_recovery_codes_replace_the_old_ones(client, dbsession):
    secret, done = _enable(client)
    old = _codes(done)
    token = _token(client.get("/settings"))
    bad = client.post("/settings/2fa/recovery", {"csrf_token": token, "code": "000000"}, expect_errors=True)
    assert not _codes(bad)
    res = client.post("/settings/2fa/recovery", {"csrf_token": token, "code": pyotp.TOTP(secret).now()})
    new = _codes(res)
    assert len(new) == 8 and not set(new) & set(old)
    svc = TotpService(dbsession)
    assert svc.verify_user_login(1, old[0]) is False and svc.verify_user_login(1, new[0]) is True


# --- operations ----------------------------------------------------------------------------------------------------------------

def test_an_administrator_can_reset_a_users_2fa_from_the_command_line(tmp_path, monkeypatch):
    from sqlalchemy.orm import Session

    from namifax.cli.user import run_reset_2fa
    from namifax.db.bootstrap import ensure_schema
    from namifax.db.provider import create_sa_engine

    url = f"sqlite:///{tmp_path / 'r.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_sa_engine(url)
    ensure_schema(engine)
    with Session(engine) as s:
        s.add(UserTOTP(uid=2, secret_key="X", is_enabled=True, backup_codes=""))
        s.commit()
    assert run_reset_2fa(["operator"]) == 0
    with Session(engine) as s:
        assert s.get(UserTOTP, 2) is None
    assert run_reset_2fa(["nobody"]) == 1
    engine.dispose()
