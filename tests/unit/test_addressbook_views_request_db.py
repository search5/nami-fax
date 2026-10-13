"""Spec 48 loop V7: views/addressbook.py hands request.db to every domain object it builds."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest
from pyramid import testing

from namifax.views import addressbook as mod
from request_identity import set_identity

CASES = [
    ("addressbook_list_view", "GET", {}),
    ("addressbook_edit_view", "GET", {}),
    ("addressbook_edit_view", "POST", {"delete": "1", "company_id": "1"}),
    ("addressbook_edit_view", "POST", {"company": "C", "company_id": "1", "faxnumber": "555"}),
    ("addressbook_edit_view", "POST", {"company": "C"}),
    ("emailbook_list_view", "GET", {}),
    ("emailbook_edit_view", "GET", {}),
    ("emailbook_edit_view", "POST", {"delete": "1", "email_id": "1"}),
    ("emailbook_edit_view", "POST", {"contact_name": "n", "contact_email": "a@x.test", "company": "C"}),
]


@pytest.mark.parametrize("name,method,params", CASES, ids=[f"{c[0]}-{c[1]}-{i}" for i, c in enumerate(CASES)])
def test_view_builds_domain_objects_with_request_db(name, method, params):
    req = testing.DummyRequest()
    set_identity(req, {"username": "admin", "uid": 1, "is_admin": True, "superuser": True})
    req.db = object()
    req.dbsession = object()
    req.method = method
    req.params = params
    req.route_url = MagicMock(return_value="/x")

    cls = MagicMock(name="NFAddressBook")
    cls.return_value.get_companies.return_value = []
    # the account and category lookups have no database behind a stand-in session; this test is about the address book
    with patch.object(mod, "NFAddressBook", cls), patch.object(mod, "NFUserAccount", MagicMock()), \
            patch.object(mod, "FaxPDFCategory", MagicMock()), contextlib.suppress(Exception):
        getattr(mod, name)(req)

    assert cls.call_args_list, f"{name} built no NFAddressBook"
    for call in cls.call_args_list:
        assert call.kwargs.get("db") is req.dbsession, f"{name}: built without request.dbsession"


def test_get_all_companies_uses_given_db():
    db = object()
    with patch.object(mod, "NFAddressBook") as cls:
        cls.return_value.get_companies.return_value = []
        mod.get_all_companies(db)
    assert cls.call_args.kwargs.get("db") is db
