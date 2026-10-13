"""Spec 48 loop 2: admin views (smtp/printers/storage/saml) use request.db only."""

from __future__ import annotations

import sqlite3

import pytest
from pyramid import testing
from pyramid.scripting import prepare

from namifax.views.admin import (
    admin_printers_view,
    admin_saml_view,
    admin_smtp_view,
    admin_storage_view,
)

ADMIN_SESSION = {"is_superadmin": True, "is_admin": True, "username": "admin"}
VIEWS = [admin_smtp_view, admin_printers_view, admin_storage_view, admin_saml_view]


@pytest.fixture
def app_env(tmp_path):
    from namifax import create_app

    db_file = tmp_path / "app.db"
    app = create_app(**{"sqlalchemy.url": f"sqlite:///{db_file}"})
    env = prepare(registry=app.registry)
    yield env, db_file
    env["closer"]()


@pytest.mark.parametrize("view", VIEWS, ids=lambda v: v.__name__)
def test_view_runs_on_real_app_request_db(view, app_env):
    env, _ = app_env
    request = env["request"]
    request.session = dict(ADMIN_SESSION)
    request.tm.begin()  # the pyramid_tm tween does this before the view runs
    try:
        res = view(request)
    finally:
        request.tm.abort()
    assert isinstance(res, dict)
    assert res["active_tab"] == "admin"


def test_smtp_save_persists_into_app_database_file(app_env):
    env, db_file = app_env
    from pyramid.request import Request

    post_req = Request.blank("/admin/smtp", POST={
        "action": "save", "smtp_host": "smtp.example.test", "smtp_port": "2525",
        "smtp_security": "NONE", "from_email": "fax@example.test"})
    env["closer"]()
    env = prepare(registry=env["registry"], request=post_req)
    request = env["request"]
    request.session = dict(ADMIN_SESSION)
    request.tm.begin()  # the pyramid_tm tween begins and commits the request transaction
    admin_smtp_view(request)
    request.tm.commit()

    con = sqlite3.connect(db_file)
    try:
        rows = con.execute("SELECT smtp_host FROM SystemSettings WHERE id = 1").fetchall()
    finally:
        con.close()
    assert rows == [("smtp.example.test",)]
