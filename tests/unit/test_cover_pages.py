"""B track, group 2: CoverPages. The service behaves the same on a Session and on the legacy engine."""

from __future__ import annotations

import alembic.command
import pytest
import sqlalchemy as sa
from sqlalchemy import Integer, String
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.dialects.mysql.mariadb import MariaDBDialect
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable


def test_model_maps_the_legacy_table():
    from namifax.models import CoverPages

    t = CoverPages.__table__
    assert t.name == "CoverPages" and [c.name for c in t.primary_key.columns] == ["cover_id"]
    assert set(t.c.keys()) == {"cover_id", "title", "file"}
    assert isinstance(t.c.cover_id.type, Integer) and t.c.cover_id.autoincrement is True
    for name in ("title", "file"):
        assert isinstance(getattr(t.c[name].type, "impl", t.c[name].type), String) and t.c[name].type.length == 255 and not t.c[name].nullable


@pytest.mark.parametrize("dialect", [sqlite.dialect(), mysql.dialect(), MariaDBDialect(), postgresql.dialect()],
                         ids=["sqlite", "mysql", "mariadb", "postgresql"])
def test_ddl_compiles_for_every_supported_database(dialect):
    from namifax.models import CoverPages

    assert "PRIMARY KEY (cover_id)" in str(CreateTable(CoverPages.__table__).compile(dialect=dialect))


@pytest.fixture(params=["session", "engine"])
def covers(request, dbsession, seeded_db):
    from namifax.services.covers import Covers

    if request.param == "session":
        dbsession.execute(sa.text("DELETE FROM CoverPages"))
        return Covers(db=dbsession)
    seeded_db.query("DELETE FROM CoverPages")
    return Covers(db=seeded_db)


def test_create_list_and_file_names_are_ordered(covers):
    assert covers.create("Standard", "standard.ps") is True and covers.get_cover_id() > 0
    assert covers.create("Alpha", "alpha.ps") is True
    assert covers.get_covers() == ["alpha.ps", "standard.ps"]
    assert [c["title"] for c in covers.list_all()] == ["Alpha", "Standard"]


def test_create_validates_and_rejects_duplicates_with_the_legacy_messages(covers):
    assert covers.create("", "x.ps") is False and covers.error == "Cover page could not be created"
    covers.create("One", "one.ps")
    assert covers.create("Other", "one.ps") is False and covers.error == "Cover page already exists"


def test_an_empty_list_reports_no_covers_configured(covers):
    assert covers.get_covers() is None and covers.error == "No cover pages configured"
    assert covers.list_all() == []


def test_load_by_file_and_by_id_then_rename(covers):
    covers.create("Old title", "t.ps")
    cover_id = covers.get_cover_id()
    assert covers.load_cover("t.ps") is True and covers.get_title() == "Old title"
    assert covers.load_by_id(str(cover_id)) is True                     # numeric strings (web forms) work
    assert covers.set_title("New title") is True and covers.set_file("t2.ps") is True
    assert covers.load_by_id(cover_id) and (covers.get_title(), covers.get_file()) == ("New title", "t2.ps")
    assert covers.load_cover("missing.ps") is False and covers.error == "Cover page 'missing.ps' doesn't exist"
    assert covers.load_by_id(99999) is False


def test_delete_cover(covers):
    covers.create("Gone", "gone.ps")
    assert covers.delete_cover(covers.get_cover_id()) is True
    assert covers.list_all() == []


def test_list_cursor_steps_then_resets(covers):
    covers.create("B", "b.ps")
    covers.create("A", "a.ps")
    assert [covers.list_covers_step(), covers.list_covers_step()] == [("A", "a.ps"), ("B", "b.ps")]
    assert covers.list_covers_step() is None
    assert covers.list_covers_step() == ("A", "a.ps")


def test_titles_with_quotes_backslashes_and_unicode_round_trip(covers):
    tricky = "o'brien\\' OR 1=1 -- \"q\" 한글"
    assert covers.create(tricky, "tricky.ps") is True
    assert covers.list_all()[0]["title"] == tricky


def test_admin_view_registers_renames_and_removes_through_the_session(admin_call, dbsession):
    from namifax.views.admin import admin_covers_view

    dbsession.execute(sa.text("DELETE FROM CoverPages"))
    made = admin_call(admin_covers_view, "POST", {"create": "1", "title": "Standard", "file": "standard.ps"})
    assert made["message"] == "Cover page template registered successfully"
    cover_id = made["covers"][0]["cover_id"]
    dup = admin_call(admin_covers_view, "POST", {"create": "1", "title": "Other", "file": "standard.ps"})
    assert dup["error"] == "Cover page already exists"
    saved = admin_call(admin_covers_view, "POST", {"save": "1", "cover_id": str(cover_id), "title": "Renamed"})
    assert saved["message"] == "The cover page was updated"
    assert [c["title"] for c in saved["covers"]] == ["Renamed"]
    gone = admin_call(admin_covers_view, "POST", {"delete": "1", "cover_id": str(cover_id)})
    assert gone["message"] == "Cover page template removed successfully" and gone["covers"] == []


@pytest.mark.serverdb
def test_server_database_service(monkeypatch, server_db_url, alembic_cfg):
    from namifax.services.covers import Covers

    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(server_db_url)
    try:
        with Session(engine) as session:
            svc = Covers(db=session)
            assert svc.create("한글 'q' \\x", "b.ps") and svc.create("Alpha", "a.ps")
            assert svc.create("Dup", "a.ps") is False
            assert svc.get_covers() == ["a.ps", "b.ps"]
            assert svc.load_by_id(str(svc.get_cover_id())) and svc.get_title() == "Alpha"
            assert svc.set_title("Renamed") is True
            titles = [c["title"] for c in svc.list_all()]
            assert set(titles) == {"한글 'q' \\x", "Renamed"}  # the order of mixed scripts is the database's collation
            assert svc.delete_cover(svc.get_cover_id()) is True
            session.commit()
        with Session(engine) as session:
            assert len(Covers(db=session).list_all()) == 1
    finally:
        engine.dispose()
