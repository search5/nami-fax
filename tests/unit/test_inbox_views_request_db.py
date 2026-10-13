"""Spec 48 loop V1: views/inbox.py hands request.db to every domain object it builds."""

from __future__ import annotations

import contextlib
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
from pyramid import testing
from pyramid.scripting import prepare

from namifax.views import inbox as inbox_mod


def _request(**kw):
    req = testing.DummyRequest(**kw)
    req.db = object()
    req.dbsession = object()
    return req


VIEW_CASES = [
    ("inbox_view", {}, {}),
    ("viewfax_view", {"params": {"fid": "1"}}, {}),
    ("fax_download_view", {"params": {"format": "pdf"}}, {"matchdict": {"fid": "1"}}),
    ("fax_rotate_view", {"params": {}}, {"matchdict": {"fid": "1"}}),
    ("setcompany_view", {"params": {"fid": "1", "faxnumid": "1"}}, {}),
]


@pytest.mark.parametrize("name,kwargs,attrs", VIEW_CASES, ids=[c[0] for c in VIEW_CASES])
def test_view_builds_domain_objects_with_request_db(name, kwargs, attrs):
    req = _request(**kwargs)
    for k, v in attrs.items():
        setattr(req, k, v)
    if name in ("fax_rotate_view", "setcompany_view"):          # these change data, so they are POSTs (with a CSRF token)
        req.method, req.POST = "POST", {**req.params}
    arc_cls, ab_cls = MagicMock(name="ArchiveIn"), MagicMock(name="NFAddressBook")
    with patch.object(inbox_mod, "ArchiveIn", arc_cls), \
            patch.object(inbox_mod, "NFAddressBook", ab_cls), \
            patch.object(inbox_mod, "get_all_admin_modems", MagicMock(return_value=[])), \
            patch.object(inbox_mod, "check_csrf_token", MagicMock()), contextlib.suppress(Exception):
        getattr(inbox_mod, name)(req)

    assert arc_cls.called, f"{name} did not build ArchiveIn"
    for cls, expected in ((arc_cls, req.dbsession), (ab_cls, req.dbsession)):   # both are ORM-backed
        for call in cls.call_args_list:
            assert call.kwargs.get("db") is expected, f"{name}: {cls._mock_name} built with the wrong database"


def test_inbox_view_lists_rows_from_the_app_database_not_the_global_one(tmp_path, as_superuser):
    from namifax import create_app

    db_file = tmp_path / "isolated.db"
    app = create_app(**{"sqlalchemy.url": f"sqlite:///{db_file}"})
    con = sqlite3.connect(db_file)
    try:
        con.execute("UPDATE AddressBook SET company='Isolated Co'")
        con.commit()
    finally:
        con.close()

    env = prepare(registry=app.registry)
    env["request"].tm.begin()               # outside the pyramid_tm tween the transaction is started by hand
    try:
        res = inbox_mod.inbox_view(env["request"])
    finally:
        env["request"].tm.abort()
        env["closer"]()

    assert res["total_faxes"] >= 1
    assert {f["company"] for f in res["faxes"]} == {"Isolated Co"}
