"""B track, group 3a: DistroList. The service behaves the same on a Session and on the legacy engine."""

from __future__ import annotations

from namifax.models.types import IsoText

import re

import alembic.command
import pytest
import sqlalchemy as sa
from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.dialects.mysql.mariadb import MariaDBDialect
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable


def test_model_maps_the_legacy_table():
    from namifax.models import DistroList

    t = DistroList.__table__
    assert t.name == "DistroList" and [c.name for c in t.primary_key.columns] == ["dl_id"]
    assert set(t.c.keys()) == {"dl_id", "listname", "listdata", "lastmod_date", "lastmod_user"}
    assert isinstance(t.c.dl_id.type, Integer) and t.c.dl_id.autoincrement is True
    assert isinstance(getattr(t.c.listname.type, "impl", t.c.listname.type), String) and t.c.listname.type.length == 255 and not t.c.listname.nullable
    assert isinstance(t.c.listdata.type, Text) and t.c.listdata.nullable
    assert isinstance(t.c.lastmod_date.type, (String, IsoText)) and t.c.lastmod_date.type.length == 32
    assert isinstance(t.c.lastmod_user.type, Integer) and t.c.lastmod_user.nullable


@pytest.mark.parametrize("dialect", [sqlite.dialect(), mysql.dialect(), MariaDBDialect(), postgresql.dialect()],
                         ids=["sqlite", "mysql", "mariadb", "postgresql"])
def test_ddl_compiles_for_every_supported_database(dialect):
    from namifax.models import DistroList

    assert "PRIMARY KEY (dl_id)" in str(CreateTable(DistroList.__table__).compile(dialect=dialect))


@pytest.fixture(params=["session", "engine"])
def dl(request, dbsession, seeded_db):
    from namifax.services.distro import DistributionList

    if request.param == "session":
        dbsession.execute(sa.text("DELETE FROM DistroList"))
        svc = DistributionList(db=dbsession)
    else:
        seeded_db.query("DELETE FROM DistroList")
        svc = DistributionList(db=seeded_db)
    svc.backend = request.param
    return svc


def test_create_validates_and_rejects_duplicates_with_the_legacy_messages(dl):
    assert dl.create("") is False and dl.error == "Please enter a list name"
    assert dl.create("Sales") is True and dl.get_dl_id() > 0
    assert dl.create("Sales") is False and dl.error == "A distribution list by that name already exists"


def test_lists_are_ordered_by_name_and_can_be_deleted(dl):
    for name in ("Zeta", "Alpha", "Beta"):
        dl.create(name)
    assert [r["listname"] for r in dl.get_distrolists()] == ["Alpha", "Beta", "Zeta"]
    assert set(dl.get_distrolists()[0]) == {"dl_id", "listname"}
    alpha = dl.get_distrolists()[0]["dl_id"]
    assert dl.delete_list(alpha) is True
    assert [r["listname"] for r in dl.get_distrolists()] == ["Beta", "Zeta"]


def test_load_rename_and_entry_management(dl):
    dl.create("Sales")
    dl_id = dl.get_dl_id()
    assert dl.load_list(str(dl_id)) is True and dl.get_listname() == "Sales" and dl.list_entries() == []
    assert dl.set_listname("Sales EU") is True
    assert dl.add_entries(["5551234", "5559999", "5551234"]) is True          # duplicates are ignored
    assert dl.list_entries() == ["5551234", "5559999"]
    assert dl.remove_entries(["5551234"]) is True and dl.list_entries() == ["5559999"]

    fresh = type(dl)(db=dl.db)
    assert fresh.load_list(dl_id) and fresh.get_listname() == "Sales EU" and fresh.list_entries() == ["5559999"]
    assert fresh.load_list(99999) is False and fresh.error == "List 99999 doesn't exist."
    assert fresh.load_list(0) is False and fresh.error == "DList not selected"


def test_moduser_is_recorded(dl):
    dl.set_moduser(3)
    dl.create("Owned")
    assert dl.load_list(dl.get_dl_id()) and dl.get_lastmod()["user"] == 3


def test_modification_time_is_maintained_by_the_orm_like_the_legacy_timestamp(dl):
    if dl.backend != "session":
        pytest.skip("the legacy raw-SQL path never maintained it")
    dl.create("Dated")
    assert dl.load_list(dl.get_dl_id())
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", dl.get_lastmod()["date"])


def test_names_and_entries_with_quotes_backslashes_and_unicode_round_trip(dl):
    tricky = "o'brien\\' OR 1=1 -- 한글"
    assert dl.create(tricky) is True
    assert dl.load_list(dl.get_dl_id()) and dl.add_entries([tricky]) is True
    assert dl.get_distrolists()[0]["listname"] == tricky and dl.list_entries() == [tricky]


def test_distrolist_pages_run_on_the_request_session(admin_call, dbsession):
    from namifax.views.distrolist import distrolist_edit_view, distrolist_view

    dbsession.execute(sa.text("DELETE FROM DistroList"))
    admin_call(distrolist_edit_view, "POST", {"listname": "Board"})
    page = admin_call(distrolist_view)
    assert [d["listname"] for d in page["distrolists"]] == ["Board"]
    dl_id = page["distrolists"][0]["dl_id"]
    admin_call(distrolist_edit_view, "POST", {"dl_id": str(dl_id), "listname": "Board EU"})
    assert [d["listname"] for d in admin_call(distrolist_view)["distrolists"]] == ["Board EU"]
    admin_call(distrolist_edit_view, "POST", {"delete": "1", "dl_id": str(dl_id)})
    assert admin_call(distrolist_view)["distrolists"] == []


@pytest.mark.serverdb
def test_server_database_service(monkeypatch, server_db_url, alembic_cfg):
    from namifax.models import DistroList
    from namifax.services.distro import DistributionList

    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(server_db_url)
    try:
        with Session(engine) as session:
            svc = DistributionList(db=session)
            assert svc.create("Beta") and svc.create("Alpha") and svc.create("한글 'q' \\x")
            assert svc.create("Beta") is False
            assert [r["listname"] for r in svc.get_distrolists() if r["listname"].isascii()] == ["Alpha", "Beta"]
            assert svc.load_list(str(svc.get_dl_id())) and svc.add_entries(["1", "2"]) and svc.set_listname("Renamed")
            session.commit()
        with Session(engine) as session:
            svc = DistributionList(db=session)
            row = next(r for r in svc.get_distrolists() if r["listname"] == "Renamed")
            assert svc.load_list(row["dl_id"]) and svc.list_entries() == ["1", "2"] and svc.get_lastmod()["date"]
            assert svc.delete_list(row["dl_id"]) is True
            session.commit()
            count = session.execute(sa.select(sa.func.count()).select_from(DistroList)).scalar()
            assert count == 2
    finally:
        engine.dispose()
