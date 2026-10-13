"""Spec 48 loop V10: NamiFaxSecurityPolicy.remember() resolves the account through request.dbsession."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pyramid import testing

from namifax.security import NamiFaxSecurityPolicy


def test_remember_builds_account_with_request_db():
    req = testing.DummyRequest()
    req.db = object()
    req.dbsession = object()
    user_cls = MagicMock(name="NFUserAccount")
    user_cls.return_value.load_username.return_value = False
    with patch("namifax.security.NFUserAccount", user_cls):
        NamiFaxSecurityPolicy().remember(req, "admin")

    assert user_cls.call_args_list, "NFUserAccount was never built"
    for call in user_cls.call_args_list:
        assert call.kwargs.get("db") is req.dbsession
