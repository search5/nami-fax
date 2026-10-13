"""Spec 48 loop V6: views/distrolist.py hands the request session to the (ORM-backed) distribution list service."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest
from pyramid import testing

from namifax.views import distrolist as mod
from request_identity import set_identity

CASES = [
    ("distrolist_view", "GET", {}),
    ("distrolist_view", "GET", {"delete": "1", "dl_id": "1"}),
    ("distrolist_edit_view", "GET", {}),
    ("distrolist_edit_view", "POST", {"delete": "1", "dl_id": "1"}),
    ("distrolist_edit_view", "POST", {"dl_id": "1", "listname": "L"}),
    ("distrolist_edit_view", "POST", {"listname": "New"}),
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

    cls = MagicMock(name="DistributionList")
    with patch.object(mod, "DistributionList", cls), contextlib.suppress(Exception):
        getattr(mod, name)(req)

    assert cls.call_args_list, f"{name} built no DistributionList"
    for call in cls.call_args_list:
        assert call.kwargs.get("db") is req.dbsession, f"{name}: built without request.dbsession"


def test_get_all_distrolists_uses_given_db():
    db = object()
    with patch.object(mod, "DistributionList") as cls:
        cls.return_value.get_distrolists.return_value = []
        mod.get_all_distrolists(db)
    assert cls.call_args.kwargs.get("db") is db
