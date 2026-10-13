"""B track, group 1: SystemSettings (SMTP gateway) as an ORM model used through a Session."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import alembic.command
import pytest
import sqlalchemy as sa
from pyramid.httpexceptions import HTTPFound
from pyramid.request import Request
from pyramid.scripting import prepare
from sqlalchemy import Boolean, Integer, String, Text, text
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.dialects.mysql.mariadb import MariaDBDialect
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

ADMIN_SESSION = {"is_superadmin": True, "is_admin": True, "username": "admin"}


# --- model -----------------------------------------------------------------------------

def test_model_maps_the_legacy_table():
    from namifax.models import SystemSettings

    table = SystemSettings.__table__
    assert table.name == "SystemSettings"
    assert [c.name for c in table.primary_key.columns] == ["id"]
    assert set(table.c.keys()) == {
        "id", "smtp_host", "smtp_port", "smtp_security", "smtp_auth", "smtp_username", "smtp_password",
        "from_email", "from_name", "email_sig_text", "email_sig_html", "updated_at"}
    assert isinstance(table.c.smtp_port.type, Integer)
    assert isinstance(table.c.smtp_auth.type, Boolean)
    assert isinstance(table.c.email_sig_html.type, Text)
    for name in ("smtp_host", "smtp_username", "from_email", "from_name"):
        assert isinstance(table.c[name].type, String) and table.c[name].type.length == 255
    assert table.c.smtp_password.type.length == 512      # room for the encrypted value
    assert table.c.updated_at.type.length == 40  # ISO text, kept compatible with legacy rows


@pytest.mark.parametrize("dialect", [sqlite.dialect(), mysql.dialect(), MariaDBDialect(), postgresql.dialect()],
                         ids=["sqlite", "mysql", "mariadb", "postgresql"])
def test_ddl_compiles_for_every_supported_database(dialect):
    from namifax.models import SystemSettings

    ddl = str(CreateTable(SystemSettings.__table__).compile(dialect=dialect))
    assert "PRIMARY KEY (id)" in ddl and "VARCHAR(255)" in ddl


# --- service ---------------------------------------------------------------------------

def test_defaults_when_nothing_is_saved(dbsession):
    from namifax.services.smtp_settings import SmtpConfig, SmtpSettingsService

    dbsession.execute(text("DELETE FROM SystemSettings"))
    cfg = SmtpSettingsService(dbsession).get_settings()
    assert cfg == SmtpConfig()
    assert (cfg.smtp_host, cfg.smtp_port, cfg.smtp_security, cfg.smtp_auth) == ("localhost", 25, "NONE", False)


def test_save_then_read_round_trip(dbsession):
    from namifax.services.smtp_settings import SmtpSettingsService

    svc = SmtpSettingsService(dbsession)
    assert svc.save_settings({
        "smtp_host": "smtp.example.com", "smtp_port": 587, "smtp_security": "starttls", "smtp_auth": "on",
        "smtp_username": "u@example.com", "smtp_password": "pw", "from_email": "noreply@example.com",
        "from_name": "Example", "email_sig_text": "Regards", "email_sig_html": "<p>Regards</p>"}) is True
    cfg = svc.get_settings()
    assert (cfg.smtp_host, cfg.smtp_port, cfg.smtp_security, cfg.smtp_auth) == ("smtp.example.com", 587, "STARTTLS", True)
    assert (cfg.smtp_username, cfg.smtp_password, cfg.from_email, cfg.from_name) == (
        "u@example.com", "pw", "noreply@example.com", "Example")
    assert (cfg.email_sig_text, cfg.email_sig_html) == ("Regards", "<p>Regards</p>")
    assert cfg.updated_at


def test_saving_again_updates_the_single_row(dbsession):
    from namifax.services.smtp_settings import SmtpSettingsService

    svc = SmtpSettingsService(dbsession)
    svc.save_settings({"smtp_host": "one.example.com"})
    svc.save_settings({"smtp_host": "two.example.com"})
    assert svc.get_settings().smtp_host == "two.example.com"
    assert dbsession.execute(text("SELECT COUNT(*) FROM SystemSettings")).scalar() == 1
    assert dbsession.execute(text("SELECT id FROM SystemSettings")).scalar() == 1


@pytest.mark.parametrize("port", [0, -1, 65536, 99999])
def test_invalid_ports_are_rejected_and_nothing_is_written(dbsession, port):
    from namifax.services.smtp_settings import SmtpSettingsService

    dbsession.execute(text("DELETE FROM SystemSettings"))
    with pytest.raises(ValueError):
        SmtpSettingsService(dbsession).save_settings({"smtp_port": port})
    assert dbsession.execute(text("SELECT COUNT(*) FROM SystemSettings")).scalar() == 0


@pytest.mark.parametrize("raw,expected", [("on", True), ("true", True), ("1", True), (1, True), (True, True),
                                          ("off", False), ("0", False), (0, False), (False, False)])
def test_auth_flag_parsing(dbsession, raw, expected):
    from namifax.services.smtp_settings import SmtpSettingsService

    svc = SmtpSettingsService(dbsession)
    svc.save_settings({"smtp_auth": raw})
    assert svc.get_settings().smtp_auth is expected


def test_unknown_security_falls_back_to_none(dbsession):
    from namifax.services.smtp_settings import SmtpSettingsService

    svc = SmtpSettingsService(dbsession)
    svc.save_settings({"smtp_security": "bogus"})
    assert svc.get_settings().smtp_security == "NONE"


def test_values_with_quotes_backslashes_and_unicode_are_stored_verbatim(dbsession):
    from namifax.services.smtp_settings import SmtpSettingsService

    tricky = "pa'ss\\' OR 1=1 -- \"x\" 한글"
    svc = SmtpSettingsService(dbsession)
    svc.save_settings({"smtp_password": tricky, "from_name": tricky, "email_sig_text": tricky})
    cfg = svc.get_settings()
    assert (cfg.smtp_password, cfg.from_name, cfg.email_sig_text) == (tricky, tricky, tricky)


def test_reads_a_row_written_by_the_legacy_raw_sql_path(dbsession):
    from namifax.services.smtp_settings import SmtpSettingsService

    dbsession.execute(text("DELETE FROM SystemSettings"))
    dbsession.execute(text(
        "INSERT INTO SystemSettings (id, smtp_host, smtp_port, smtp_security, smtp_auth, from_email, updated_at) "
        "VALUES (1, 'legacy.example.com', 2525, 'SSL', TRUE, 'f@legacy', '2026-10-01T10:00:00.123456')"))
    cfg = SmtpSettingsService(dbsession).get_settings()
    assert (cfg.smtp_host, cfg.smtp_port, cfg.smtp_security, cfg.smtp_auth) == ("legacy.example.com", 2525, "SSL", True)
    assert cfg.updated_at == "2026-10-01T10:00:00.123456"


def test_service_without_a_session_fails_loudly():
    from namifax.services.smtp_settings import SmtpSettingsService

    with pytest.raises(RuntimeError, match="session"):
        SmtpSettingsService().get_settings()


def test_mailer_is_built_from_the_saved_settings(dbsession):
    from namifax.services.mailer import MailerService
    from namifax.services.smtp_settings import SmtpSettingsService

    SmtpSettingsService(dbsession).save_settings({
        "smtp_host": "smtp.mailer.test", "smtp_port": 465, "smtp_security": "SSL", "smtp_auth": "on",
        "smtp_username": "u", "smtp_password": "p", "from_email": "fax@mailer.test"})
    mailer = MailerService.from_settings(dbsession)
    assert (mailer.smtp_server, mailer.smtp_port, mailer.use_ssl) == ("smtp.mailer.test", 465, True)


# --- view ------------------------------------------------------------------------------

def _call(app, tm, dbsession, method="GET", params=None):
    from namifax.views.admin import admin_smtp_view

    req = Request.blank("/admin/smtp", POST=params) if method == "POST" else Request.blank("/admin/smtp")
    with prepare(registry=app.registry, request=req) as env:
        request = env["request"]
        request.dbsession, request.tm = dbsession, tm
        request.session = dict(ADMIN_SESSION)
        return admin_smtp_view(request)


def test_view_shows_defaults(app, tm, dbsession):
    dbsession.execute(text("DELETE FROM SystemSettings"))
    res = _call(app, tm, dbsession)
    assert res["config"].smtp_host == "localhost" and res["config"].smtp_port == 25


def test_view_saves_and_redirects(app, tm, dbsession):
    from namifax.services.smtp_settings import SmtpSettingsService

    res = _call(app, tm, dbsession, "POST", {
        "action": "save", "smtp_host": "smtp.office365.com", "smtp_port": "587", "smtp_security": "STARTTLS",
        "smtp_auth": "on", "smtp_username": "notify@company.com", "smtp_password": "secret",
        "from_email": "notify@company.com", "from_name": "NamiFAX Alert"})
    assert isinstance(res, HTTPFound)
    cfg = SmtpSettingsService(dbsession).get_settings()
    assert (cfg.smtp_host, cfg.smtp_port, cfg.smtp_auth) == ("smtp.office365.com", 587, True)


def test_view_reports_validation_errors(app, tm, dbsession):
    res = _call(app, tm, dbsession, "POST", {"action": "save", "smtp_port": "70000"})
    assert "Invalid SMTP port" in res["error"]


def test_view_runs_the_connection_test_without_saving(app, tm, dbsession):
    dbsession.execute(text("DELETE FROM SystemSettings"))
    with patch("namifax.services.smtp_settings.SmtpSettingsService.test_connection") as test:
        test.return_value = MagicMock(success=True, message="OK", details=["d"])
        res = _call(app, tm, dbsession, "POST", {"action": "test", "test_email": "a@b.test", "smtp_host": "h"})
    assert res["test_result"]["success"] is True
    assert dbsession.execute(text("SELECT COUNT(*) FROM SystemSettings")).scalar() == 0


# --- real servers (optional) -----------------------------------------------------------

@pytest.mark.serverdb
def test_server_database_round_trip(monkeypatch, server_db_url, alembic_cfg):
    from namifax.models import SystemSettings
    from namifax.services.smtp_settings import SmtpSettingsService

    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(server_db_url)
    try:
        with Session(engine) as session:
            svc = SmtpSettingsService(session)
            assert svc.get_settings().smtp_host == "localhost"
            svc.save_settings({"smtp_host": "smtp.server.test", "smtp_port": 2525, "smtp_auth": "on",
                               "smtp_password": "x\\' OR 1=1 --", "from_name": "한글 ünï", "smtp_security": "ssl"})
            svc.save_settings({"smtp_host": "smtp.server2.test", "smtp_port": 2526, "smtp_auth": "on",
                               "smtp_password": "x\\' OR 1=1 --", "from_name": "한글 ünï", "smtp_security": "ssl"})
            session.commit()
        with Session(engine) as session:
            cfg = SmtpSettingsService(session).get_settings()
            assert (cfg.smtp_host, cfg.smtp_port, cfg.smtp_auth, cfg.smtp_security) == ("smtp.server2.test", 2526, True, "SSL")
            assert (cfg.smtp_password, cfg.from_name) == ("x\\' OR 1=1 --", "한글 ünï")
            count = session.execute(sa.select(sa.func.count()).select_from(SystemSettings)).scalar()
            assert count == 1  # table name is quoted by SQLAlchemy, unlike raw legacy SQL
    finally:
        engine.dispose()
