"""Spec 48 loop V9: webauthn, archive, sendfax and outbox views hand request.db to domain objects."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest
from pyramid import testing

from namifax.views import archive as archive_mod
from namifax.views import outbox as outbox_mod
from namifax.views import sendfax as sendfax_mod
from namifax.views import webauthn as webauthn_mod


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


def _calls(*mocks):
    return [c for m in mocks for c in m.call_args_list]


def _assert_all_db(calls, req, label, attr="db"):
    assert calls, f"{label}: nothing was built"
    for call in calls:
        passed = call.kwargs.get("db", call.args[0] if call.args else None)
        assert passed is getattr(req, attr), f"{label}: built without request.{attr}"


# --- webauthn -----------------------------------------------------------------

def test_webauthn_current_user_uses_request_db():
    req = _request(session={"username": "admin"})
    with patch.object(webauthn_mod, "NFUserAccount") as cls:
        webauthn_mod._get_current_user(req)
    _assert_all_db(_calls(cls), req, "_get_current_user", attr="dbsession")  # the account is ORM-backed


def test_webauthn_auth_options_uses_request_db():
    req = _request(params={"username": "admin"})
    with patch.object(webauthn_mod, "NFUserAccount") as cls, \
            patch.object(webauthn_mod, "_get_webauthn_service", MagicMock()), \
            contextlib.suppress(Exception):
        webauthn_mod.webauthn_auth_options_view(req)
    _assert_all_db(_calls(cls), req, "webauthn_auth_options_view", attr="dbsession")  # the account is ORM-backed


def test_webauthn_auth_verify_uses_request_db():
    req = _request("POST", session={"webauthn_auth_challenge": "c"})
    req.json_body = {"credential": {"id": "cid"}}
    svc = MagicMock()
    svc.get_credential_by_id.return_value = {"public_key": "00", "uid": 1, "sign_count": 0}
    with patch.object(webauthn_mod, "NFUserAccount") as cls, \
            patch.object(webauthn_mod, "_get_webauthn_service", MagicMock(return_value=svc)), \
            contextlib.suppress(Exception):
        webauthn_mod.webauthn_auth_verify_view(req)
    _assert_all_db(_calls(cls), req, "webauthn_auth_verify_view", attr="dbsession")  # the account is ORM-backed


# --- archive / sendfax / outbox -----------------------------------------------

def test_archive_view_uses_request_db(as_superuser):
    req = _request(params={"kw": "acme"})
    arc, cat = MagicMock(name="FaxPDFArchive"), MagicMock(name="FaxPDFCategory")
    modems = MagicMock(return_value=[])
    arc.return_value.search_archive.return_value = 0
    arc.return_value.next_archive_entry.return_value = None
    cat.return_value.get_categories.return_value = []
    with patch.object(archive_mod, "NFUserAccount", MagicMock()), patch.object(archive_mod, "NFAddressBook", MagicMock()), \
            patch.object(archive_mod, "FaxPDFArchive", arc), patch.object(archive_mod, "FaxPDFCategory", cat), \
            patch.object(archive_mod, "get_all_admin_modems", modems), patch.object(archive_mod, "page_size", MagicMock(return_value=30)), \
            contextlib.suppress(Exception):
        archive_mod.archive_view(req)
    _assert_all_db(_calls(arc), req, "archive_view", attr="dbsession")
    assert modems.call_args.args[0] is req.dbsession  # modems are ORM-backed
    assert cat.call_args.kwargs.get("db") is req.dbsession  # ORM-backed: the request session
    assert arc.call_args_list and modems.call_args_list


def test_sendfax_view_uses_request_db(as_superuser):
    req = _request()
    covers, modems = MagicMock(name="Covers"), MagicMock(name="FaxModem")
    covers.return_value.get_covers.return_value = []
    modems.return_value.get_modems.return_value = []
    with patch.object(sendfax_mod, "Covers", covers), patch.object(sendfax_mod, "FaxModem", modems), \
            patch.object(sendfax_mod, "NFUserAccount", MagicMock()), contextlib.suppress(Exception):
        sendfax_mod.sendfax_view(req)
    assert modems.call_args.kwargs.get("db") is req.dbsession  # ORM-backed
    assert covers.call_args.kwargs.get("db") is req.dbsession  # ORM-backed: the request session
    assert covers.call_args_list and modems.call_args_list


def test_outbox_view_passes_request_db_to_modem_helper(as_superuser):
    req = _request()
    req.session = MagicMock()                                 # the page carries the session's CSRF token
    modems = MagicMock(return_value=[])
    with patch.object(outbox_mod, "FaxQueue", MagicMock()), patch.object(outbox_mod, "get_all_admin_modems", modems), \
            patch.object(outbox_mod, "NFAddressBook", MagicMock()), contextlib.suppress(Exception):
        outbox_mod.outbox_view(req)
    assert modems.call_args.args[0] is req.dbsession  # modems are ORM-backed
