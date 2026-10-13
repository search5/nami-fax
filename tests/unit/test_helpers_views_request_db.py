"""Spec 48 loop V5: views/helpers.py (popups, vCard upload) hands request.db to domain objects."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest
from pyramid import testing

from namifax.views import helpers as helpers_mod
from request_identity import set_identity

POST_VCARD = {"upload": MagicMock(file=MagicMock(read=MagicMock(return_value=b"BEGIN:VCARD\nFN:A\nEMAIL:a@x.test\nTEL:555\nEND:VCARD")), filename="c.vcf"),
              "_submit_check": "1", "catid": "1"}

CASES = [
    ("popup_distrolist_helper", "GET", {}),
    ("popup_distro_contacts", "GET", {"dlid": "1"}),
    ("popup_fax_contacts", "GET", {}),
    ("popup_email_contacts", "GET", {}),
    ("upload_email_contacts", "POST", POST_VCARD),
    ("upload_fax_contacts", "POST", POST_VCARD),
    ("upload_fax_contacts", "GET", {}),
]
CLASSES = ["NFAddressBook", "FaxPDFCategory", "DistributionList"]


@pytest.mark.parametrize("name,method,params", CASES, ids=[f"{c[0]}-{c[1]}-{i}" for i, c in enumerate(CASES)])
def test_view_builds_domain_objects_with_request_db(name, method, params):
    req = testing.DummyRequest()
    set_identity(req, {"username": "admin", "uid": 1, "is_admin": True, "superuser": True})
    req.db = object()
    req.dbsession = object()
    req.method = method
    req.params = params
    req.POST = params

    mocks = {c: MagicMock(name=c) for c in CLASSES}
    with patch.multiple(helpers_mod, **mocks), contextlib.suppress(Exception):
        getattr(helpers_mod, name)(req)

    calls = [c for m in mocks.values() for c in m.call_args_list]
    assert calls, f"{name} built no domain objects"
    for cls_name, mock in mocks.items():
        expected = req.dbsession if cls_name in ("FaxPDFCategory", "DistributionList", "NFAddressBook") else req.db
        for call in mock.call_args_list:
            assert call.kwargs.get("db") is expected, f"{name}: {cls_name} built with the wrong database"
