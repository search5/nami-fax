"""B track, group 2: Modems, DIDRoute, BarcodeRoute. The services behave the same on a Session and the legacy engine."""

from __future__ import annotations

import alembic.command
import pytest
import sqlalchemy as sa
from sqlalchemy import Integer, String
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.dialects.mysql.mariadb import MariaDBDialect
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

DIALECTS = [sqlite.dialect(), mysql.dialect(), MariaDBDialect(), postgresql.dialect()]
DIALECT_IDS = ["sqlite", "mysql", "mariadb", "postgresql"]


# --- models ----------------------------------------------------------------------------

@pytest.mark.parametrize("model,table,pk,unique,columns", [
    ("Modems", "Modems", "devid", "device", {"devid", "device", "alias", "contact", "printer", "faxcatid"}),
    ("DIDRoute", "DIDRoute", "didr_id", "routecode", {"didr_id", "routecode", "alias", "contact", "printer", "faxcatid"}),
    ("BarcodeRoute", "BarcodeRoute", "barcode_id", "barcode", {"barcode_id", "barcode", "alias", "contact", "printer", "faxcatid"}),
])
def test_models_map_the_legacy_tables(model, table, pk, unique, columns):
    import namifax.models as models

    t = getattr(models, model).__table__
    assert t.name == table and [c.name for c in t.primary_key.columns] == [pk]
    assert set(t.c.keys()) == columns  # BarcodeRoute.bcr_id (a duplicate of barcode_id the port added) is not modelled
    assert isinstance(t.c[pk].type, Integer) and t.c[pk].autoincrement is True
    assert t.c[unique].unique is True and t.c[unique].nullable is False
    assert isinstance(getattr(t.c[unique].type, "impl", t.c[unique].type), String) and t.c[unique].type.length in (64, 255)
    for name in ("alias", "contact", "printer"):
        assert isinstance(getattr(t.c[name].type, "impl", t.c[name].type), String) and t.c[name].type.length == 255 and t.c[name].nullable
    assert isinstance(t.c.faxcatid.type, Integer) and t.c.faxcatid.nullable


@pytest.mark.parametrize("dialect", DIALECTS, ids=DIALECT_IDS)
@pytest.mark.parametrize("model", ["Modems", "DIDRoute", "BarcodeRoute"])
def test_ddl_compiles_for_every_supported_database(model, dialect):
    import namifax.models as models

    ddl = str(CreateTable(getattr(models, model).__table__).compile(dialect=dialect))
    assert "UNIQUE" in ddl and "VARCHAR" in ddl


# --- select(): the same NULL ordering on every database ----------------------------------

def test_select_puts_null_values_first_when_ascending_on_every_backend(dbsession, seeded_db):
    from namifax.db.repository import Repository

    for backend in (dbsession, seeded_db):
        if backend is dbsession:
            backend.execute(sa.text("DELETE FROM Modems"))
        else:
            backend.query("DELETE FROM Modems")
        repo = Repository("Modems", db=backend)
        for device, alias in (("d1", "b"), ("d2", None), ("d3", "a")):
            repo.new_entry({"device": device, "alias": alias})
        assert [r["device"] for r in repo.select(order_by="alias")] == ["d2", "d3", "d1"]
        assert [r["device"] for r in repo.select(order_by="alias", descending=True)] == ["d1", "d3", "d2"]


# --- modems --------------------------------------------------------------------------------

@pytest.fixture(params=["session", "engine"])
def backend(request, dbsession, seeded_db):
    if request.param == "session":
        for t in ("Modems", "DIDRoute", "BarcodeRoute"):
            dbsession.execute(sa.text(f"DELETE FROM {t}"))
        return dbsession
    for t in ("Modems", "DIDRoute", "BarcodeRoute"):
        seeded_db.query(f"DELETE FROM {t}")
    return seeded_db


def test_modem_create_list_and_order(backend):
    from namifax.services.modem import FaxModem

    m = FaxModem(db=backend)
    assert m.create("ttyS1", "Zeta", "z@x.test", "lp1", 2) is True and m.devid > 0
    assert m.create("ttyS0", "Alpha") is True
    assert m.get_modems() == ["ttyS0", "ttyS1"]                         # ordered by alias
    assert [r["device"] for r in m.list_all()] == ["ttyS0", "ttyS1"]    # ordered by device
    assert [m.list_modems_step()[2], m.list_modems_step()[2]] == ["ttyS0", "ttyS1"]
    assert m.list_modems_step() is None and m.error == "No modems configured"


def test_modem_validation_and_duplicates(backend):
    from namifax.services.modem import FaxModem

    m = FaxModem(db=backend)
    assert m.get_modems() is None and m.error == "No modems configured"
    assert m.create("", "x") is False and m.error == "Modem could not be created"
    m.create("ttyS0", "A")
    assert m.create("ttyS0", "B") is False and m.error == "Modem already exists"


def test_modem_load_update_and_delete(backend):
    from namifax.services.modem import FaxModem

    m = FaxModem(db=backend)
    m.create("ttyS0", "Sales", "s@x.test", "lp1", 3)
    devid = m.devid
    assert m.load_device("ttyS0") and (m.alias, m.contact, m.printer, m.faxcatid) == ("Sales", "s@x.test", "lp1", 3)
    assert m.loadbyid(str(devid)) is True                                # web forms pass strings
    assert m.set_alias("Renamed") and m.set_contact("c@x.test") and m.set_printer("lp9") and m.set_faxcatid(5)
    fresh = FaxModem(db=backend)
    assert fresh.load_device("ttyS0") and (fresh.alias, fresh.contact, fresh.printer, fresh.faxcatid) == (
        "Renamed", "c@x.test", "lp9", 5)
    assert fresh.load_device("nope") is False and fresh.error == "Modem 'nope' doesn't exist"
    assert fresh.loadbyid(99999) is False
    assert fresh.delete_device("ttyS0") is True and fresh.get_modems() is None   # by device name
    fresh.create("ttyS5", "x")
    assert fresh.delete_device(fresh.devid) is True                              # by id


# --- DID routes ----------------------------------------------------------------------------

def test_did_create_validate_and_list(backend):
    from namifax.services.did import DIDRouting

    d = DIDRouting(db=backend)
    assert d.get_routes() is None and d.error == "No DID routes configured"
    assert d.create("1000", "Zeta", "sales@x.test", "lp1", 1) is True and d.didr_id > 0
    assert d.create("1001", "Alpha") is True
    assert d.create("1000", "Dup") is False and d.error == "DID route already exists"
    assert d.create("<NONE>", "x") is False and d.error == "Route could not be created"
    assert d.create("1002", "x", contact="not-an-email") is False and d.error == "Please enter a valid e-mail address."
    assert [r["routecode"] for r in d.list_all()] == ["1001", "1000"]              # ordered by alias
    ids = d.get_routes()
    assert ids[0] == 0 and len(ids) == 3
    assert [d.list_routes_step()[2], d.list_routes_step()[2]] == ["1001", "1000"]
    assert d.list_routes_step() is None


def test_did_load_update_and_delete(backend):
    from namifax.services.did import DIDRouting

    d = DIDRouting(db=backend)
    d.create("1000", "Main", "a@x.test", "lp1", 4)
    didr_id = d.didr_id
    assert d.load_route("1000") and (d.get_alias(), d.get_contact(), d.get_printer(), d.get_faxcatid()) == (
        "Main", "a@x.test", "lp1", 4)
    assert d.loadbyid(str(didr_id)) is True
    assert d.set_alias("New") and d.set_routecode("2000") and d.set_contact("b@x.test") and d.set_printer("lp2")
    assert d.set_faxcatid(7)
    fresh = DIDRouting(db=backend)
    assert fresh.load_route("2000") and (fresh.get_alias(), fresh.get_contact(), fresh.get_faxcatid()) == ("New", "b@x.test", 7)
    assert fresh.load_route("1000") is False and fresh.error == "DID route '1000' doesn't exist"
    assert fresh.delete_route(didr_id) is True and fresh.list_all() == []


# --- barcode routes ----------------------------------------------------------------------------

def test_barcode_create_validate_and_list(backend):
    from namifax.services.barcode import BarcodeRouting

    b = BarcodeRouting(db=backend)
    assert b.get_routes() is None and b.error == "No barcode routes configured"
    assert b.create("BC-2", "Zeta", "s@x.test", "lp1", 1) is True and b.barcode_id > 0
    assert b.create("BC-1", "Alpha") is True
    assert b.create("BC-1", "Dup") is False and b.error == "Barcode route already exists"
    assert b.create("<NONE>", "x") is False and b.error == "Route could not be created"
    rows = b.list_all()
    assert [r["barcode"] for r in rows] == ["BC-1", "BC-2"] and all(r["barcode_id"] for r in rows)
    assert b.get_routes()[0] == 0
    assert [b.list_routes_step()[2], b.list_routes_step()[2]] == ["BC-1", "BC-2"]


def test_barcode_load_update_and_delete(backend):
    from namifax.services.barcode import BarcodeRouting

    b = BarcodeRouting(db=backend)
    b.create("BC-9", "Nine", "n@x.test", "lp9", 2)
    barcode_id = b.barcode_id
    assert b.load_route("BC-9") and b.barcode_id == barcode_id and b.get_alias() == "Nine"
    assert b.loadbyid(str(barcode_id)) is True and b.loadbyid(99999) is False
    assert b.set_alias("Renamed") and b.set_barcode("BC-10") and b.set_contact("m@x.test") and b.set_printer("lp1")
    assert b.set_faxcatid(3)
    fresh = BarcodeRouting(db=backend)
    assert fresh.load_route("BC-10") and (fresh.get_alias(), fresh.get_contact(), fresh.get_faxcatid()) == (
        "Renamed", "m@x.test", 3)
    assert fresh.load_route("BC-9") is False
    assert fresh.delete_route(barcode_id) is True and fresh.list_all() == []


def test_values_with_quotes_backslashes_and_unicode_round_trip(backend):
    from namifax.services.barcode import BarcodeRouting
    from namifax.services.did import DIDRouting
    from namifax.services.modem import FaxModem

    tricky = "o'brien\\' OR 1=1 -- 한글"
    assert FaxModem(db=backend).create("ttyS0", tricky) and DIDRouting(db=backend).create("1000", tricky)
    assert BarcodeRouting(db=backend).create(tricky, tricky)
    assert FaxModem(db=backend).list_all()[0]["alias"] == tricky
    b = BarcodeRouting(db=backend)
    assert b.load_route(tricky) and b.get_alias() == tricky


# --- views ---------------------------------------------------------------------------------

def test_admin_modems_did_and_barcode_views_run_on_the_request_session(admin_call, dbsession):
    from namifax.views.admin import admin_barcodes_view, admin_modems_view, admin_routing_did_view

    for t in ("Modems", "DIDRoute", "BarcodeRoute"):
        dbsession.execute(sa.text(f"DELETE FROM {t}"))
    for view, params in (
        (admin_modems_view, {"device": "ttyS7", "alias": "Seven"}),
        (admin_routing_did_view, {"route": "7000", "alias": "Seven DID"}),
        (admin_barcodes_view, {"barcode": "BC-7", "alias": "Seven BC"}),
    ):
        admin_call(view, "POST", params)    # some pages redirect to the list, others render it again
    assert [m["device"] for m in admin_call(admin_modems_view)["modems"]] == ["ttyS7"]
    assert [r["routecode"] for r in admin_call(admin_routing_did_view)["did_routes"]] == ["7000"]
    assert [b["barcode"] for b in admin_call(admin_barcodes_view)["barcodes"]] == ["BC-7"]


def test_the_modem_helper_used_by_every_page_reads_through_the_session(dbsession):
    from namifax.services.modem import FaxModem
    from namifax.views.admin import get_all_admin_modems

    dbsession.execute(sa.text("DELETE FROM Modems"))
    FaxModem(db=dbsession).create("ttyS3", "Three")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(FaxModem, "get_status", lambda self, raw_output=None: {"status": "Idle"})
        rows = get_all_admin_modems(dbsession)
    assert [r["device"] for r in rows] == ["ttyS3"]


# --- real servers (optional) -----------------------------------------------------------------

@pytest.mark.serverdb
def test_server_database_services(monkeypatch, server_db_url, alembic_cfg):
    from namifax.db.repository import Repository
    from namifax.services.barcode import BarcodeRouting
    from namifax.services.did import DIDRouting
    from namifax.services.modem import FaxModem

    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(server_db_url)
    try:
        with Session(engine) as session:
            m, d, b = FaxModem(db=session), DIDRouting(db=session), BarcodeRouting(db=session)
            assert m.create("ttyS0", "Beta") and m.create("ttyS1", "Alpha") and m.create("ttyS2", "한글 'q' \\x")
            assert m.create("ttyS0", "Dup") is False
            assert d.create("1000", "A", "a@x.test") and d.create("1000", "B") is False
            assert b.create("BC-1", "A") and b.create("BC-1", "B") is False
            assert m.load_device("ttyS1") and m.set_alias("Zeta") and m.loadbyid(str(m.devid))
            assert d.load_route("1000") and d.set_faxcatid(2) and b.load_route("BC-1") and b.set_printer("lp")
            repo = Repository("Modems", db=session)
            session.execute(sa.text("UPDATE " + ("`Modems`" if engine.dialect.name in ("mysql", "mariadb") else '"Modems"') +
                                    " SET alias = NULL WHERE device = 'ttyS2'"))
            assert [r["device"] for r in repo.select(order_by="alias")][0] == "ttyS2"      # NULLs first everywhere
            assert m.delete_device("ttyS0") is True
            session.commit()
        with Session(engine) as session:
            assert len(FaxModem(db=session).list_all()) == 2
            assert DIDRouting(db=session).list_all()[0]["faxcatid"] == 2
            assert BarcodeRouting(db=session).list_all()[0]["printer"] == "lp"
    finally:
        engine.dispose()
