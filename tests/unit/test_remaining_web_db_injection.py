"""Spec 48 loop V12: emailbook MDBOData lookups and SAML JIT provisioning use the injected db."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest
from pyramid import testing

from namifax.services.saml import SAMLService, SAMLSettings
from namifax.views import addressbook as ab_mod


class _Request(testing.DummyRequest):
    identity = {"username": "admin", "uid": 1, "is_admin": True, "superuser": True}


@pytest.mark.parametrize(
    "method,params",
    [("GET", {"abookemail_id": "1"}), ("POST", {"abookemail_id": "1", "contact_name": "n", "contact_email": "a@x.test"})],
    ids=["emailbook_edit-GET", "emailbook_edit-POST-update"],
)
def test_emailbook_edit_builds_the_address_book_with_the_request_session(method, params):
    req = _Request()
    req.db = object()
    req.dbsession = object()
    req.method = method
    req.params = params
    req.POST = params
    req.route_url = MagicMock(return_value="/x")
    cls = MagicMock(name="NFAddressBook")
    with patch.object(ab_mod, "NFAddressBook", cls), contextlib.suppress(Exception):
        ab_mod.emailbook_edit_view(req)

    assert cls.call_args_list, "NFAddressBook was never built"
    assert all(call.kwargs.get("db") is req.dbsession for call in cls.call_args_list)


def test_saml_provisioning_builds_account_with_service_db():
    db = object()
    svc = SAMLService(SAMLSettings(enabled=True), db=db)
    with patch("namifax.services.saml.NFUserAccount") as cls:
        cls.return_value.load_by_username.return_value = True
        svc.provision_or_get_user("alice@corp.example")
    assert cls.call_args.kwargs.get("db") is db
