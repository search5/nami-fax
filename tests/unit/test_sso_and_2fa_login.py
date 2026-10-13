"""Two-factor, SAML and passkey logins end to end (the first versions could not log anybody in).

The old tests replaced NFUserAccount, the services and the session with mocks, so they never noticed that
* the app had no HTTP session factory (a user with 2FA got a 500, passkey challenges were never stored),
* NFUserAccount had none of the methods SAML and the passkey views call, and
* both flows only wrote ``request.session['username']`` while the security policy authenticates by token.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from webauthn.helpers import bytes_to_base64url

from namifax.services.totp import TotpService
from namifax.services.user_account import NFUserAccount
from request_identity import set_identity

PWD = "Secret123!"


def _user(session, username, email=None, **extra):
    svc = NFUserAccount(db=session)
    assert svc.create({"username": username, "password": PWD, "email": email or f"{username}@corp.test",
                       "name": f"{username.title()} Person", **extra}), svc.error
    return svc


def _status(client, path):
    return client.get(path, expect_errors=True).status_int


def _logged_in(client):
    return _status(client, "/inbox") == 200


# --- session factory + 2FA ---------------------------------------------------------------------------------

def _enable_2fa(session, uid):
    t = TotpService(session)
    with patch.object(t, "verify_code", return_value=True):
        return t.enable_totp(uid, t.generate_secret(), "123456")["backup_codes"]


def test_a_user_with_2fa_logs_in_through_the_code_step(testapp, dbsession):
    codes = _enable_2fa(dbsession, 1)
    res = testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    assert res.status_int == 302 and res.headers["Location"].endswith("/login/totp")
    assert not _logged_in(testapp)                                        # not yet: the code is still missing

    bad = testapp.post("/login/totp", {"code": "000000"})
    assert bad.status_int == 200 and not _logged_in(testapp)

    good = testapp.post("/login/totp", {"code": codes[0]})
    assert good.status_int == 302 and _logged_in(testapp)


def test_the_flow_cookie_is_http_only_and_same_site(testapp, dbsession):
    _enable_2fa(dbsession, 1)
    res = testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    cookie = "; ".join(res.headers.getall("Set-Cookie"))
    assert "namifax_flow=" in cookie and "HttpOnly" in cookie and "SameSite=Lax" in cookie


def test_the_totp_page_without_a_pending_login_goes_back_to_login(testapp):
    res = testapp.get("/login/totp")
    assert res.status_int == 302 and res.headers["Location"].endswith("/login")


# --- NFUserAccount: the methods the SSO code uses ---------------------------------------------------------

def test_user_account_lookup_helpers(dbsession):
    made = _user(dbsession, "carol", email="carol@corp.test")
    other = NFUserAccount(db=dbsession)
    assert other.load_by_username("carol") is True
    assert (other.get_uid(), other.get_username(), other.get_name()) == (made.uid, "carol", "Carol Person")
    assert NFUserAccount(db=dbsession).load_by_username("nobody") is False
    by_id = NFUserAccount(db=dbsession)
    assert by_id.load_by_id(made.uid) is True and by_id.get_username() == "carol"
    assert by_id.load_by_id(999999) is False


def test_create_user_wrapper(dbsession):
    svc = NFUserAccount(db=dbsession)
    assert svc.create_user(username="dave", password=PWD, name="Dave D", email="dave@corp.test", is_admin=False)
    check = NFUserAccount(db=dbsession)
    assert check.load_by_username("dave") and check.get_name() == "Dave D" and not check.dbdata["is_admin"]
    assert NFUserAccount(db=dbsession).login("dave", PWD)
    assert NFUserAccount(db=dbsession).create_user(username="dave", password=PWD, name="x", email="o@x.test") is False


# --- SAML ----------------------------------------------------------------------------------------------------

def _acs(client, name_id, **attrs):
    result = {"success": True, "name_id": name_id, "attributes": attrs}
    with patch("namifax.services.saml.SAMLService.process_saml_response", return_value=result):
        return client.post("/auth/saml/acs", {"SAMLResponse": "x", "RelayState": "/inbox"}, expect_errors=True)


def test_saml_logs_in_the_account_with_the_asserted_email(testapp, dbsession):
    _user(dbsession, "erin", email="erin@corp.test")
    res = _acs(testapp, "erin@corp.test", email="erin@corp.test")
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox")
    assert _logged_in(testapp) and _status(testapp, "/admin") == 403         # signed in as erin, a plain user


def test_saml_never_attaches_to_an_account_by_the_local_part_of_the_name_id(testapp, dbsession):
    """admin@other-company must not become the local administrator just because both start with 'admin'."""
    res = _acs(testapp, "admin@other.example", email="admin@other.example", displayName="Not The Admin")
    assert res.status_int == 302 and _logged_in(testapp)
    assert _status(testapp, "/admin") == 403                                  # a new, ordinary account
    created = NFUserAccount(db=dbsession)
    assert created.loadbyemail("admin@other.example")
    assert created.get_username() != "admin" and not created.dbdata["is_admin"] and created.get_name() == "Not The Admin"
    original = NFUserAccount(db=dbsession)
    assert original.load_username("admin") and original.dbdata["is_admin"] and original.dbdata["email"] != "admin@other.example"


def test_saml_provisioning_picks_a_free_username_and_a_random_password(testapp, dbsession):
    _user(dbsession, "frank", email="frank@a.test")
    _acs(testapp, "frank@b.test", email="frank@b.test")
    second = NFUserAccount(db=dbsession)
    assert second.loadbyemail("frank@b.test") and second.get_username() == "frank1"
    assert NFUserAccount(db=dbsession).login("frank1", "password") is False


def test_saml_refuses_disabled_accounts(testapp, dbsession):
    made = _user(dbsession, "gina", email="gina@corp.test")
    edit = NFUserAccount(db=dbsession)
    edit.load(made.uid)
    edit.dbdata["acc_enabled"] = 0
    edit.update()
    res = _acs(testapp, "gina@corp.test", email="gina@corp.test")
    assert res.status_int == 302 and res.headers["Location"].endswith("/login") and not _logged_in(testapp)


def test_saml_without_jit_does_not_create_accounts(dbsession):
    from namifax.services.saml import SAMLService, SAMLSettings

    svc = SAMLService(SAMLSettings(enabled=True, jit_provisioning=False), db=dbsession)
    assert svc.provision_or_get_user("nobody@corp.test", {"email": "nobody@corp.test"}) is None
    assert NFUserAccount(db=dbsession).loadbyemail("nobody@corp.test") is False


def test_saml_view_uses_the_request_session():
    from pyramid import testing

    from namifax.services.saml import SAMLSettings
    from namifax.views.saml import _get_saml_service

    req = testing.DummyRequest()
    req.db, req.dbsession = object(), object()
    with patch("namifax.views.saml.saml_settings", return_value=SAMLSettings()):
        assert _get_saml_service(req).db is req.dbsession


# --- passkeys ------------------------------------------------------------------------------------------------

def _passkey(dbsession, uid, cid_bytes=b"credential-1"):
    from namifax.services.webauthn import WebAuthnService

    cid = bytes_to_base64url(cid_bytes)
    WebAuthnService(db=dbsession).save_credential(uid=uid, credential_id=cid, public_key="ab" * 32, sign_count=1,
                                                  device_name="YubiKey")
    return cid


def _passkey_login(client, cid, username="operator", verified=7):
    opts = client.get(f"/api/webauthn/auth/options?username={username}")
    with patch("namifax.services.webauthn.WebAuthnService.verify_authentication_response", return_value=verified):
        return opts, client.post_json("/api/webauthn/auth/verify", {"credential": {"id": cid}}, expect_errors=True)


def test_a_passkey_logs_the_user_in_and_counts_the_use(testapp, dbsession):
    from namifax.services.webauthn import WebAuthnService

    cid = _passkey(dbsession, uid=2)
    opts, res = _passkey_login(testapp, cid)
    assert opts.json["challenge"] and [c["id"] for c in opts.json["allowCredentials"]] == [cid]
    assert res.status_int == 200 and res.json == {"success": True, "username": "operator"}
    assert _logged_in(testapp) and _status(testapp, "/admin") == 403          # operator is not an administrator
    row = WebAuthnService(db=dbsession).get_credential_by_id(cid)
    assert row["sign_count"] == 7 and row["last_used_at"]


def test_a_passkey_needs_a_fresh_challenge(testapp, dbsession):
    cid = _passkey(dbsession, uid=2)
    with patch("namifax.services.webauthn.WebAuthnService.verify_authentication_response", return_value=2):
        res = testapp.post_json("/api/webauthn/auth/verify", {"credential": {"id": cid}}, expect_errors=True)
    assert res.status_int == 400 and not _logged_in(testapp)


def test_an_unknown_passkey_is_rejected(testapp, dbsession):
    _passkey(dbsession, uid=2)
    _, res = _passkey_login(testapp, bytes_to_base64url(b"other"))
    assert res.status_int == 400 and not _logged_in(testapp)


def test_a_passkey_cannot_log_in_a_disabled_account(testapp, dbsession):
    cid = _passkey(dbsession, uid=2)
    edit = NFUserAccount(db=dbsession)
    edit.load(2)
    edit.dbdata["acc_enabled"] = 0
    edit.update()
    _, res = _passkey_login(testapp, cid)
    assert res.status_int == 400 and not _logged_in(testapp)


def test_registering_a_passkey_needs_a_session_and_a_login(testapp, dbsession):
    assert testapp.get("/api/webauthn/register/options", expect_errors=True).status_int == 401
    testapp.post("/login", {"username": "operator", "password": "password", "_submit_check": "1"})
    res = testapp.get("/api/webauthn/register/options")
    assert res.json["user"]["name"] == "operator" and res.json["user"]["displayName"] == "Operator User"


# --- the send queue names its users through the session ------------------------------------------------------

def test_faxqueue_shows_the_users_display_name(dbsession):
    from namifax.services.faxqueue import FaxQueue

    _user(dbsession, "henry", email="henry@corp.test")
    fq = FaxQueue(auto_process=False, db=dbsession)
    fq.queue = [{"owner": "henry", "mailaddr": ""}, {"owner": "faxmail", "mailaddr": "henry@corp.test"},
                {"owner": "stranger", "mailaddr": ""}, {"owner": "faxmail", "mailaddr": "x@y.test"}]
    assert [e["user"] for e in fq.get_queue()] == ["Henry Person", "Henry Person", "stranger", "x@y.test"]
    # his own job and the one mailed in his name (owner faxmail, his address), like the original's list_owner
    assert [e["user"] for e in fq.list_owner("henry")] == ["Henry Person", "Henry Person"]


def test_faxqueue_callers_pass_the_request_session(as_superuser):
    import contextlib
    from unittest.mock import MagicMock

    from pyramid import testing

    from namifax.views import outbox as outbox_mod

    req = testing.DummyRequest()
    set_identity(req, {"username": "admin", "uid": 1, "is_admin": True, "superuser": True})
    req.db, req.dbsession = object(), object()
    req.route_url = MagicMock(return_value="/x")
    with patch.object(outbox_mod, "FaxQueue") as cls, patch.object(outbox_mod, "NFAddressBook"), contextlib.suppress(Exception):
        outbox_mod.outbox_view(req)
    assert cls.call_args.kwargs.get("db") is req.dbsession
