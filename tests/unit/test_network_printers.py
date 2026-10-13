"""B track, group 1: NetworkPrinters as an ORM model used through a Session."""

from __future__ import annotations

from pathlib import Path

import alembic.command
import pytest
import sqlalchemy as sa
from sqlalchemy import Integer, String, Text, text
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.dialects.mysql.mariadb import MariaDBDialect
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

ROOT = Path(__file__).resolve().parents[2]


# --- model -----------------------------------------------------------------------------

def test_model_maps_the_legacy_table():
    from namifax.models import NetworkPrinters

    t = NetworkPrinters.__table__
    assert t.name == "NetworkPrinters"
    assert [c.name for c in t.primary_key.columns] == ["id"]
    assert set(t.c.keys()) == {"id", "name", "protocol", "host", "port", "queue_name", "description"}
    assert isinstance(t.c.id.type, Integer) and t.c.id.autoincrement is True
    assert isinstance(t.c.name.type, String) and t.c.name.type.length == 255 and not t.c.name.nullable
    assert isinstance(t.c.host.type, String) and t.c.host.type.length == 255 and not t.c.host.nullable
    assert isinstance(t.c.protocol.type, String) and t.c.protocol.type.length == 10
    assert isinstance(t.c.port.type, Integer)
    assert isinstance(t.c.queue_name.type, String) and t.c.queue_name.type.length == 255
    assert isinstance(t.c.description.type, Text)


@pytest.mark.parametrize("name,dialect,needle", [
    ("sqlite", sqlite.dialect(), "id INTEGER NOT NULL"),
    ("mysql", mysql.dialect(), "AUTO_INCREMENT"),
    ("mariadb", MariaDBDialect(), "AUTO_INCREMENT"),
    ("postgresql", postgresql.dialect(), "SERIAL"),
])
def test_autoincrement_primary_key_is_expressed_per_database(name, dialect, needle):
    from namifax.models import NetworkPrinters

    assert needle in str(CreateTable(NetworkPrinters.__table__).compile(dialect=dialect))


# --- service ---------------------------------------------------------------------------

def test_create_and_list_in_id_order(dbsession):
    from namifax.services.printer import NetworkPrinter, NetworkPrinterService

    svc = NetworkPrinterService(dbsession)
    first = svc.create_printer("HP", "raw", "10.0.0.1", 9100, "q1", "2nd floor")
    second = svc.create_printer("Canon", host="10.0.0.2")
    assert 0 < first < second
    printers = svc.list_printers()
    assert [p.id for p in printers] == [first, second]
    assert printers[0] == NetworkPrinter(id=first, name="HP", protocol="RAW", host="10.0.0.1", port=9100,
                                         queue_name="q1", description="2nd floor")
    assert (printers[1].protocol, printers[1].port, printers[1].queue_name, printers[1].description) == (
        "RAW", 9100, None, None)


def test_empty_optional_fields_are_stored_as_null(dbsession):
    from namifax.services.printer import NetworkPrinterService

    NetworkPrinterService(dbsession).create_printer("P", host="h", queue_name="", description="")
    assert dbsession.execute(text("SELECT queue_name, description FROM NetworkPrinters")).one() == (None, None)


def test_values_with_quotes_backslashes_and_unicode_are_stored_verbatim(dbsession):
    from namifax.services.printer import NetworkPrinterService

    tricky = "pr'int\\' OR 1=1 -- \"x\" 한글"
    svc = NetworkPrinterService(dbsession)
    svc.create_printer(tricky, host=tricky, queue_name=tricky, description=tricky)
    p = svc.list_printers()[0]
    assert (p.name, p.host, p.queue_name, p.description) == (tricky, tricky, tricky, tricky)


def test_delete_reports_whether_a_printer_was_removed(dbsession):
    from namifax.services.printer import NetworkPrinterService

    svc = NetworkPrinterService(dbsession)
    pid = svc.create_printer("P", host="h")
    assert svc.delete_printer(pid) is True
    assert svc.delete_printer(pid) is False
    assert svc.list_printers() == []


def test_reads_a_row_written_by_the_legacy_raw_sql_path(dbsession):
    from namifax.services.printer import NetworkPrinterService

    dbsession.execute(text("INSERT INTO NetworkPrinters (name, host) VALUES ('legacy', 'h1')"))
    p = NetworkPrinterService(dbsession).list_printers()[0]
    assert (p.name, p.protocol, p.port) == ("legacy", "RAW", 9100)


def test_service_without_a_session_fails_loudly():
    from namifax.services.printer import NetworkPrinterService

    with pytest.raises(RuntimeError, match="session"):
        NetworkPrinterService().list_printers()


def test_printer_module_has_no_string_built_sql():
    src = (ROOT / "src/namifax/services/printer.py").read_text()
    assert ".quote(" not in src and "NetworkPrinters (" not in src


# --- view ------------------------------------------------------------------------------

def test_view_adds_lists_and_deletes(admin_call, dbsession):
    from namifax.views.admin import admin_printers_view

    added = admin_call(admin_printers_view, "POST", {
        "action": "add", "name": "Lobby", "protocol": "lpd", "host": "10.1.1.1", "port": "515"})
    assert "registered successfully" in added["message"]
    assert [(p.name, p.protocol, p.port) for p in added["printers"]] == [("Lobby", "LPD", 515)]

    pid = added["printers"][0].id
    deleted = admin_call(admin_printers_view, "POST", {"action": "delete", "printer_id": str(pid)})
    assert "deleted successfully" in deleted["message"]
    assert deleted["printers"] == []


def test_view_requires_name_and_host(admin_call):
    from namifax.views.admin import admin_printers_view

    res = admin_call(admin_printers_view, "POST", {"action": "add", "name": "", "host": ""})
    assert "required" in res["error"] and res["printers"] == []


# --- real servers (optional) -----------------------------------------------------------

@pytest.mark.serverdb
def test_server_database_round_trip(monkeypatch, server_db_url, alembic_cfg):
    from namifax.models import NetworkPrinters
    from namifax.services.printer import NetworkPrinterService

    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(server_db_url)
    try:
        with Session(engine) as session:
            svc = NetworkPrinterService(session)
            a = svc.create_printer("한글 ünï", "ipp", "h-1", 631, "q", "x\\' OR 1=1 --")
            b = svc.create_printer("second", host="h-2")
            session.commit()
        with Session(engine) as session:
            svc = NetworkPrinterService(session)
            printers = svc.list_printers()
            assert [p.id for p in printers] == [a, b] and a < b
            assert (printers[0].name, printers[0].protocol, printers[0].port) == ("한글 ünï", "IPP", 631)
            assert printers[0].description == "x\\' OR 1=1 --"
            assert svc.delete_printer(a) is True
            session.commit()
            count = session.execute(sa.select(sa.func.count()).select_from(NetworkPrinters)).scalar()
            assert count == 1
    finally:
        engine.dispose()
