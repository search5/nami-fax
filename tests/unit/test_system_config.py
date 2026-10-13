"""B0-6 pilot: SystemConfig as an ORM model used through request.dbsession (portable across databases)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pyramid.request import Request
from pyramid.scripting import prepare
from sqlalchemy import String, Text, text
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.dialects.mysql.mariadb import MariaDBDialect
from sqlalchemy.schema import CreateTable

ROOT = Path(__file__).resolve().parents[2]
ADMIN_ADMIN = {"is_superadmin": True, "is_admin": True, "username": "admin"}


# --- model -----------------------------------------------------------------------------

def test_model_maps_the_legacy_table_name_and_columns():
    from namifax.models import SystemConfig

    table = SystemConfig.__table__
    assert table.name == "SystemConfig"  # unchanged so existing raw SQL keeps working
    assert [c.name for c in table.primary_key.columns] == ["key"]
    assert isinstance(table.c.key.type, String) and table.c.key.type.length == 255
    assert isinstance(table.c.value.type, Text)
    assert table.c.value.nullable is True


@pytest.mark.parametrize("name,dialect", [
    ("sqlite", sqlite.dialect()), ("mysql", mysql.dialect()),
    ("mariadb", MariaDBDialect()), ("postgresql", postgresql.dialect()),
])
def test_ddl_compiles_for_every_supported_database(name, dialect):
    from namifax.models import SystemConfig

    ddl = str(CreateTable(SystemConfig.__table__).compile(dialect=dialect))
    assert "VARCHAR(255)" in ddl and "PRIMARY KEY" in ddl
    if name in ("mysql", "mariadb"):
        assert "`key`" in ddl  # reserved word is quoted for MySQL-family databases


def test_every_string_column_has_a_length():
    """MySQL and MariaDB cannot create VARCHAR without a length."""
    from namifax.models.meta import Base
    import namifax.models  # noqa: F401  (registers all models)

    missing = [f"{t.name}.{c.name}" for t in Base.metadata.tables.values() for c in t.columns
               if isinstance(c.type, String) and not isinstance(c.type, Text) and c.type.length is None]
    assert missing == []


# --- service ---------------------------------------------------------------------------

def test_service_returns_default_for_unknown_keys(dbsession):
    from namifax.services.system_config import SystemConfigService

    assert SystemConfigService(dbsession).get("nope") == ""
    assert SystemConfigService(dbsession).get("nope", "fallback") == "fallback"


def test_service_set_inserts_then_replaces(dbsession):
    from namifax.services.system_config import SystemConfigService

    svc = SystemConfigService(dbsession)
    svc.set("k", "one")
    assert svc.get("k") == "one"
    svc.set("k", "two")
    assert svc.get("k") == "two"
    assert dbsession.execute(text("SELECT COUNT(*) FROM SystemConfig WHERE key = 'k'")).scalar() == 1


def test_service_stores_quotes_and_backslashes_verbatim(dbsession):
    from namifax.services.system_config import SystemConfigService

    svc = SystemConfigService(dbsession)
    value = "x\\' OR 1=1 -- \"q\" ünï"
    svc.set("tricky", value)
    assert svc.get("tricky") == value


def test_service_treats_a_null_value_as_the_default(dbsession):
    from namifax.services.system_config import SystemConfigService

    dbsession.execute(text("INSERT INTO SystemConfig (key, value) VALUES ('nullval', NULL)"))
    assert SystemConfigService(dbsession).get("nullval", "dflt") == "dflt"


# --- views -----------------------------------------------------------------------------

def _call(view, app, tm, dbsession, method="GET", params=None):
    req = Request.blank("/admin/x", POST=params) if method == "POST" else Request.blank("/admin/x")
    with prepare(registry=app.registry, request=req) as env:
        request = env["request"]
        request.dbsession, request.tm = dbsession, tm
        request.session = dict(ADMIN_ADMIN)
        return view(request)


def test_storage_view_saves_and_replaces_lifecycle_settings(app, tm, dbsession):
    from namifax.views.admin import admin_storage_view

    first = _call(admin_storage_view, app, tm, dbsession, "POST", {
        "action": "save_lifecycle", "purge_tiff_after_days": "9", "full_retention_days": "400",
        "remote_sync_delete": "on"})
    assert first["lifecycle"] == {"purge_tiff_after_days": 9, "full_retention_days": 400, "remote_sync_delete": True}

    second = _call(admin_storage_view, app, tm, dbsession, "POST", {
        "action": "save_lifecycle", "purge_tiff_after_days": "3", "full_retention_days": "100"})
    assert second["lifecycle"] == {"purge_tiff_after_days": 3, "full_retention_days": 100, "remote_sync_delete": False}
    assert dbsession.execute(
        text("SELECT COUNT(*) FROM SystemConfig WHERE key = 'storage_purge_tiff_days'")).scalar() == 1


def test_storage_view_keeps_the_secret_key_when_the_form_leaves_it_blank(app, tm, dbsession):
    from namifax.views.admin import admin_storage_view

    base = {"action": "save_cloud", "storage_type": "S3", "bucket_name": "b", "access_key": "AK"}
    _call(admin_storage_view, app, tm, dbsession, "POST", {**base, "secret_key": "s3cret"})
    res = _call(admin_storage_view, app, tm, dbsession, "POST", {**base, "bucket_name": "b2"})
    assert res["cloud"]["has_secret_key"] is True
    assert res["cloud"]["bucket_name"] == "b2"


def test_saml_view_saves_and_reads_back_settings(app, tm, dbsession):
    from namifax.views.admin import admin_saml_view

    res = _call(admin_saml_view, app, tm, dbsession, "POST", {
        "enabled": "on", "idp_entity_id": "https://idp.example.test", "idp_sso_url": "https://idp/sso",
        "idp_x509_cert": "CERT", "jit_provisioning": "on", "default_role": "admin"})
    assert res["saml"]["enabled"] is True
    assert res["saml"]["idp_entity_id"] == "https://idp.example.test"
    assert res["saml"]["default_role"] == "admin"


def test_admin_views_no_longer_use_sqlite_only_sql():
    src = (ROOT / "src/namifax/views/admin.py").read_text()
    assert not re.search(r"INSERT\s+OR\s+(REPLACE|IGNORE)", src, re.I)
    assert "CREATE TABLE IF NOT EXISTS SystemConfig" not in src


def test_real_application_commits_settings_saved_through_the_orm(tmp_path):
    """Login, then save storage and SAML settings through the real pyramid_tm tween."""
    import sqlite3

    import webtest

    from namifax import create_app

    db_file = tmp_path / "e2e-config.db"
    client = webtest.TestApp(create_app(**{"sqlalchemy.url": f"sqlite:///{db_file}"}))
    client.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"}, status=302)
    client.post("/admin/storage", {"action": "save_lifecycle", "purge_tiff_after_days": "11",
                                   "full_retention_days": "500"}, status=200)
    client.post("/admin/saml", {"idp_entity_id": "https://idp.e2e.test", "default_role": "user"}, status=200)

    con = sqlite3.connect(db_file)
    try:
        rows = dict(con.execute("SELECT key, value FROM SystemConfig").fetchall())
    finally:
        con.close()
    assert rows["storage_purge_tiff_days"] == "11"
    assert rows["storage_retention_days"] == "500"
    assert rows["saml_idp_entity_id"] == "https://idp.e2e.test"

    page = client.get("/admin/storage", status=200)
    assert "11" in page.text
