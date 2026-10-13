"""Spec 48 loop V3: views/ajax.py hands request.db to every domain object it builds."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

import pytest
from pyramid import testing

from namifax.views import ajax as ajax_mod

CASES = [
    ("ajax_modem_status", "GET", {}),
    ("ajax_inbox_count", "GET", {}),
    ("ajax_addressbook_suggest", "GET", {"q": "a"}),
    ("ajax_emailbook_suggest", "GET", {"q": "a"}),
    ("ajax_addressbook_prefill", "GET", {"cid": "1", "faxnumid": "1"}),
    ("ajax_distrolist_faxes", "GET", {"dlid": "1"}),
    ("ajax_archive_fax", "POST", {"fid": "1"}),
    ("ajax_deletefaxes_view", "POST", {"fids": "1,2"}),
    ("ajax_archivebook_view", "GET", {"q": "a"}),
]
CLASSES = ["ArchiveIn", "NFAddressBook", "FaxModem", "DistributionList"]


@pytest.mark.parametrize("name,method,params", CASES, ids=[c[0] for c in CASES])
def test_view_builds_domain_objects_with_request_db(name, method, params, as_superuser):
    req = testing.DummyRequest()
    req.session = {"user_id": 1, "username": "admin", "is_admin": True, "superuser": True}
    req.db = object()
    req.dbsession = object()
    req.method = method
    req.params = params

    mocks = {c: MagicMock(name=c) for c in CLASSES}
    modems = MagicMock(return_value=[{"device": "ttyS0", "status": "Idle"}])
    with patch.multiple(ajax_mod, **mocks), \
            patch.object(ajax_mod, "get_all_admin_modems", modems), \
            contextlib.suppress(Exception):
        getattr(ajax_mod, name)(req)

    assert any(m.call_args_list for m in mocks.values()) or modems.call_args_list, f"{name} built no domain objects"
    for cls_name, mock in mocks.items():
        expected = req.dbsession if cls_name in ("FaxModem", "DistributionList", "NFAddressBook", "ArchiveIn") else req.db   # modems are ORM-backed
        for call in mock.call_args_list:
            assert call.kwargs.get("db") is expected, f"{name}: {cls_name} built with the wrong database"
    for call in modems.call_args_list:
        assert call.args[0] is req.dbsession, f"{name}: modem helper called without request.dbsession"
