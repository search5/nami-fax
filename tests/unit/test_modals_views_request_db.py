"""Spec 48 loop V2: views/modals.py hands request.db to every domain object it builds."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest
from pyramid import testing

from namifax.views import modals as modals_mod
from request_identity import set_identity

CASES = [
    ("modal_email_view", "POST", {"fid": "1", "emails": "a@example.test", "_submit_check": "1"}),
    ("modal_assign_view", "POST", {"fid": "1", "regexp": "Acme", "_submit_check": "1"}),
    ("modal_assign_view", "GET", {"fid": "1"}),
    ("modal_note_view", "POST", {"fid": "1", "description": "n", "_submit_check": "1"}),
    ("modal_delete_view", "POST", {"fid": "1", "_submit_check": "1"}),
    ("modal_txreport_view", "GET", {"fid": "1"}),
]


@pytest.mark.parametrize("name,method,params", CASES, ids=[f"{c[0]}-{c[1]}" for c in CASES])
def test_view_builds_domain_objects_with_request_db(name, method, params, as_superuser):
    req = testing.DummyRequest()
    set_identity(req, {"username": "admin", "uid": 1, "is_admin": True, "superuser": True})
    req.db = object()
    req.dbsession = object()
    req.method = method
    req.params = params

    arc_cls, ab_cls = MagicMock(name="ArchiveIn"), MagicMock(name="NFAddressBook")
    arc_cls.return_value.load_fax.return_value = True
    arc_cls.return_value.get_companyid.return_value = 7
    ab_cls.return_value.loadbycid.return_value = True
    ab_cls.return_value.get_companies.return_value = []
    with patch.object(modals_mod, "ArchiveIn", arc_cls), \
            patch.object(modals_mod, "NFAddressBook", ab_cls), \
            patch.object(modals_mod, "send_mail", MagicMock(return_value=True)), \
            contextlib.suppress(Exception):
        getattr(modals_mod, name)(req)

    assert arc_cls.call_args_list + ab_cls.call_args_list, f"{name} built no domain objects"
    for call in arc_cls.call_args_list:
        assert call.kwargs.get("db") is req.dbsession, f"{name}: ArchiveIn built without request.dbsession"
    for call in ab_cls.call_args_list:          # the address book is ORM-backed
        assert call.kwargs.get("db") is req.dbsession, f"{name}: NFAddressBook built without request.dbsession"
