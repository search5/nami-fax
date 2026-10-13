"""Spec 48 loop V8: auth and settings views hand request.db to the account/TOTP services."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest
from pyramid import testing

from namifax.views import auth as auth_mod
from namifax.views import settings as settings_mod


class _Request(testing.DummyRequest):
    identity = {"username": "admin", "uid": 1, "is_admin": True, "superuser": True}


def _request(method="GET", params=None, session=None):
    req = _Request()
    req.db = object()
    req.dbsession = object()
    req.method = method
    req.params = params or {}
    req.POST = req.params
    req.session = session if session is not None else {}
    req.route_url = MagicMock(return_value="/x")
    return req


def _run(view, req):
    user_cls, totp_cls = MagicMock(name="NFUserAccount"), MagicMock(name="TotpService")
    user_cls.return_value.login.return_value = True
    user_cls.return_value.load.return_value = True
    user_cls.return_value.is_expired.return_value = False
    user_cls.return_value.dbdata = {}
    totp_cls.return_value.is_totp_enabled.return_value = False
    with patch.object(auth_mod, "NFUserAccount", user_cls), \
            patch.object(settings_mod, "NFUserAccount", user_cls), \
            patch("namifax.services.totp.TotpService", totp_cls), \
            patch("namifax.services.login_throttle.LoginThrottle",
                  MagicMock(return_value=MagicMock(is_locked=MagicMock(return_value=False)))), \
            contextlib.suppress(Exception):
        view(req)
    return user_cls, totp_cls


def _assert_db(mock_cls, req, positional=False, attr="db"):
    assert mock_cls.call_args_list, f"{mock_cls._mock_name} was never built"
    for call in mock_cls.call_args_list:
        passed = call.args[0] if positional and call.args else call.kwargs.get("db")
        assert passed is getattr(req, attr)


def test_login_post_builds_account_and_totp_with_request_db():
    req = _request("POST", {"username": "admin", "password": "pw"})
    user_cls, totp_cls = _run(auth_mod.login_post_view, req)
    _assert_db(user_cls, req, attr="dbsession")  # the account is ORM-backed
    _assert_db(totp_cls, req, positional=True, attr="dbsession")


def test_login_totp_post_builds_totp_with_request_db():
    req = _request("POST", {"code": "123456"}, session={"2fa_pending_uid": 1, "2fa_pending_username": "admin"})
    _, totp_cls = _run(auth_mod.login_totp_view, req)
    _assert_db(totp_cls, req, positional=True, attr="dbsession")


def test_settings_view_builds_account_and_totp_with_request_db():
    req = _request()
    user_cls, totp_cls = _run(settings_mod.settings_view, req)
    _assert_db(user_cls, req, attr="dbsession")  # the account is ORM-backed
    _assert_db(totp_cls, req, positional=True, attr="dbsession")
