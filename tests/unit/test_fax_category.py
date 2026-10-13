"""B track, group 2: FaxCategory. The service behaves the same on a Session and on the legacy engine."""

from __future__ import annotations

import alembic.command
import pytest
import sqlalchemy as sa
from sqlalchemy import Integer, String
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.dialects.mysql.mariadb import MariaDBDialect
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable


# --- model -----------------------------------------------------------------------------

def test_model_maps_the_legacy_table():
    from namifax.models import FaxCategory

    t = FaxCategory.__table__
    assert t.name == "FaxCategory"
    assert [c.name for c in t.primary_key.columns] == ["catid"]
    assert isinstance(t.c.catid.type, Integer) and t.c.catid.autoincrement is True
    assert isinstance(getattr(t.c.name.type, "impl", t.c.name.type), String) and t.c.name.type.length == 255
    assert t.c.name.unique is True and t.c.name.nullable is False


@pytest.mark.parametrize("dialect", [sqlite.dialect(), mysql.dialect(), MariaDBDialect(), postgresql.dialect()],
                         ids=["sqlite", "mysql", "mariadb", "postgresql"])
def test_ddl_compiles_for_every_supported_database(dialect):
    from namifax.models import FaxCategory

    ddl = str(CreateTable(FaxCategory.__table__).compile(dialect=dialect))
    assert "UNIQUE (name)" in ddl and "VARCHAR(255)" in ddl


# --- the legacy repository gets the same ordered listing as the ORM one ---------------------

# --- service on both backends ----------------------------------------------------------------

@pytest.fixture(params=["session", "engine"])
def svc(request, dbsession, seeded_db):
    from namifax.services.categories import FaxPDFCategory

    backend = dbsession if request.param == "session" else seeded_db
    if request.param == "session":
        backend.execute(sa.text("DELETE FROM FaxCategory"))
    else:
        backend.query("DELETE FROM FaxCategory")
    return FaxPDFCategory(db=backend)


def test_create_and_list_ordered_by_name(svc):
    for name in ("Invoices", "Contracts", "Archive"):
        assert svc.create(name) is True and svc.error is None
    assert [c["name"] for c in svc.get_categories()] == ["Archive", "Contracts", "Invoices"]


def test_duplicate_and_empty_names_are_rejected_with_the_legacy_messages(svc):
    svc.create("Invoices")
    assert svc.create("Invoices") is False and svc.get_error() == "Category 'Invoices' already exists"
    assert svc.create("") is False and svc.get_error() == "Category '' could not be created"


def test_rename_get_name_and_delete(svc):
    svc.create("Old")
    catid = svc.get_categories()[0]["catid"]
    assert svc.get_name(catid) == "Old"
    assert svc.set_name("New", catid) is True and svc.get_name(catid) == "New"
    assert svc.get_name(str(catid)) == "New"                    # numeric strings (web forms) work
    assert svc.delete_category(catid) is True and svc.get_name(catid) is None
    assert svc.get_categories() == []


def test_missing_ids_report_errors(svc):
    assert svc.get_name(0) is None and svc.get_error() == "No catid sent"
    assert svc.set_name("x", 0) is False and svc.get_error() == "No name or catid to set"
    assert svc.delete_category(None) is False and svc.get_error() == "No catid sent"
    assert svc.get_name(99999) is None


def test_list_cursor_steps_through_every_category_then_resets(svc):
    for name in ("b", "a"):
        svc.create(name)
    first, second = svc.get_list_step(), svc.get_list_step()
    assert [first[1], second[1]] == ["a", "b"]
    assert svc.get_list_step() is None
    assert svc.get_list_step()[1] == "a"                        # a new traversal starts again


def test_names_with_quotes_backslashes_and_unicode_round_trip(svc):
    tricky = "o'brien\\' OR 1=1 -- \"q\" 한글"
    assert svc.create(tricky) is True
    assert svc.get_categories()[0]["name"] == tricky


# --- views ------------------------------------------------------------------------------------

def test_admin_view_creates_renames_and_deletes_through_the_session(admin_call, dbsession):
    from namifax.views.admin import admin_categories_view

    dbsession.execute(sa.text("DELETE FROM FaxCategory"))
    created = admin_call(admin_categories_view, "POST", {"create": "1", "name": "Invoices"})
    assert created["message"] == "Fax category created successfully"
    catid = created["categories"][0]["catid"]

    renamed = admin_call(admin_categories_view, "POST", {"save": "1", "catid": str(catid), "name": "Bills"})
    assert renamed["message"] == "Fax category updated successfully"
    assert [c["name"] for c in renamed["categories"]] == ["Bills"]

    duplicate = admin_call(admin_categories_view, "POST", {"create": "1", "name": "Bills"})
    assert duplicate["error"] == "Category 'Bills' already exists"

    deleted = admin_call(admin_categories_view, "POST", {"delete": "1", "catid": str(catid)})
    assert deleted["message"] == "Fax category deleted successfully" and deleted["categories"] == []


# --- real servers (optional) -----------------------------------------------------------------

@pytest.mark.serverdb
def test_server_database_service(monkeypatch, server_db_url, alembic_cfg):
    from namifax.services.categories import FaxPDFCategory

    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(server_db_url)
    try:
        with Session(engine) as session:
            svc = FaxPDFCategory(db=session)
            for name in ("Invoices", "한글 'q' \\x", "Archive"):
                assert svc.create(name) is True
            assert svc.create("Invoices") is False
            cats = svc.get_categories()
            assert {c["name"] for c in cats} == {"Invoices", "한글 'q' \\x", "Archive"}  # collation decides the order
            assert [c["name"] for c in cats if c["name"].isascii()] == ["Archive", "Invoices"]
            catid = next(c["catid"] for c in cats if c["name"] == "Archive")
            assert svc.get_name(str(catid)) == "Archive"
            assert svc.set_name("Renamed", catid) is True and svc.get_name(catid) == "Renamed"
            assert svc.delete_category(catid) is True
            session.commit()
        with Session(engine) as session:
            assert len(FaxPDFCategory(db=session).get_categories()) == 2
    finally:
        engine.dispose()
