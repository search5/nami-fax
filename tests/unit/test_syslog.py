"""B track, group 1: SysLog as an ORM model with a portable search service."""

from __future__ import annotations

from namifax.models.types import IsoText

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


def _add(session, *rows):
    from namifax.models import SysLog

    for logdate, logtext in rows:
        session.add(SysLog(logdate=logdate, logtext=logtext))
    session.flush()


# --- model -----------------------------------------------------------------------------

def test_model_maps_the_legacy_table():
    from namifax.models import SysLog

    t = SysLog.__table__
    assert t.name == "SysLog"
    assert [c.name for c in t.primary_key.columns] == ["syslogid"]
    assert set(t.c.keys()) == {"syslogid", "logdate", "logtext"}
    assert isinstance(t.c.syslogid.type, Integer) and t.c.syslogid.autoincrement is True
    # ISO text, not DateTime: the viewer filters by prefix (LIKE), which PostgreSQL does not allow on timestamps
    assert isinstance(t.c.logdate.type, (String, IsoText)) and t.c.logdate.type.length == 32 and not t.c.logdate.nullable
    assert isinstance(t.c.logtext.type, Text) and not t.c.logtext.nullable


@pytest.mark.parametrize("dialect", [sqlite.dialect(), mysql.dialect(), MariaDBDialect(), postgresql.dialect()],
                         ids=["sqlite", "mysql", "mariadb", "postgresql"])
def test_ddl_compiles_for_every_supported_database(dialect):
    from namifax.models import SysLog

    assert "PRIMARY KEY (syslogid)" in str(CreateTable(SysLog.__table__).compile(dialect=dialect))


# --- service ---------------------------------------------------------------------------

def test_newest_first_and_nothing_is_cut_off(dbsession):
    """C8: the original has no row limit; every event of the filter is reachable (here 120 rows > the old 100)."""
    from namifax.services.syslog import SysLogService

    dbsession.execute(text("DELETE FROM SysLog"))
    _add(dbsession, *[(f"2026-10-01 10:{m:02d}:00", f"entry {m}") for m in range(0, 60)],
         *[(f"2026-10-01 11:{m:02d}:00", f"later {m}") for m in range(0, 60)])
    svc = SysLogService(dbsession)
    rows = svc.search()
    assert len(rows) == 120 and svc.count() == 120
    assert rows[0] == {"logdate": "2026-10-01 11:59:00", "logtext": "later 59"}
    assert rows[0]["logdate"] > rows[-1]["logdate"]
    assert rows[-1]["logtext"] == "entry 0"


def test_pages_cover_every_row_once(dbsession):
    from namifax.services.syslog import SysLogService

    dbsession.execute(text("DELETE FROM SysLog"))
    _add(dbsession, *[(f"2026-10-01 10:{m:02d}:00", f"entry {m}") for m in range(0, 60)],
         *[(f"2026-10-01 11:{m:02d}:00", f"later {m}") for m in range(0, 45)])
    svc = SysLogService(dbsession)
    pages = [svc.search(limit=50, offset=o) for o in (0, 50, 100)]
    assert [len(p) for p in pages] == [50, 50, 5]
    assert [r["logtext"] for p in pages for r in p] == [r["logtext"] for r in svc.search()]
    assert svc.count(kw="later") == 45 and len(svc.search(kw="later", limit=50)) == 45


def test_keyword_is_a_case_insensitive_substring(dbsession):
    from namifax.services.syslog import SysLogService

    dbsession.execute(text("DELETE FROM SysLog"))
    _add(dbsession, ("2026-10-01 10:00:00", "Fax job dispatched: SUCCESS"), ("2026-10-01 10:01:00", "login failed"))
    svc = SysLogService(dbsession)
    assert [r["logtext"] for r in svc.search(kw="success")] == ["Fax job dispatched: SUCCESS"]
    assert [r["logtext"] for r in svc.search(kw="LOGIN")] == ["login failed"]
    assert svc.search(kw="nothing like this") == []


def test_wildcard_characters_in_the_keyword_are_literal(dbsession):
    from namifax.services.syslog import SysLogService

    dbsession.execute(text("DELETE FROM SysLog"))
    _add(dbsession, ("2026-10-01 10:00:00", "disk 100% full"), ("2026-10-01 10:01:00", "disk 100 used"),
         ("2026-10-01 10:02:00", "file_name.tif"), ("2026-10-01 10:03:00", "fileXname.tif"))
    svc = SysLogService(dbsession)
    assert [r["logtext"] for r in svc.search(kw="100%")] == ["disk 100% full"]
    assert [r["logtext"] for r in svc.search(kw="file_name")] == ["file_name.tif"]


@pytest.mark.parametrize("filters,expected", [
    ({"year": "2026"}, 4),
    ({"year": "2026", "month": "10"}, 3),
    ({"year": "2026", "month": "9"}, 1),
    ({"year": "2026", "month": "10", "day": "1"}, 2),
    ({"year": "2026", "month": "10", "day": "01"}, 2),
    ({"year": "2026", "month": "*", "day": "*"}, 4),
    ({"year": "*", "month": "10", "day": "01"}, 4),
    ({"year": "2025"}, 0),
])
def test_date_filters(dbsession, filters, expected):
    from namifax.services.syslog import SysLogService

    dbsession.execute(text("DELETE FROM SysLog"))
    _add(dbsession, ("2026-10-01 10:00:00", "a"), ("2026-10-01 23:59:59", "b"), ("2026-10-15 08:00:00", "c"),
         ("2026-09-30 12:00:00", "d"))
    assert len(SysLogService(dbsession).search(**filters)) == expected


def test_injection_payloads_are_only_data(dbsession):
    from namifax.services.syslog import SysLogService

    dbsession.execute(text("DELETE FROM SysLog"))
    _add(dbsession, ("2026-10-01 10:00:00", "Legitimate security test log"))
    svc = SysLogService(dbsession)
    assert svc.search(kw="' OR '1'='1") == []
    assert svc.search(kw="x\\' OR 1=1 -- ") == []
    assert svc.search(day="01' OR '1'='1", month="10", year="2026") == []
    assert len(svc.search(kw="security test")) == 1


def test_text_with_quotes_backslashes_and_unicode_round_trips(dbsession):
    from namifax.services.syslog import SysLogService

    tricky = "user 'o\\'brien' said \"안녕\" 한글 ünï"
    dbsession.execute(text("DELETE FROM SysLog"))
    _add(dbsession, ("2026-10-01 10:00:00", tricky))
    assert SysLogService(dbsession).search(kw="'o\\'brien'")[0]["logtext"] == tricky


def test_reads_rows_written_by_the_legacy_raw_sql_path(dbsession):
    from namifax.services.syslog import SysLogService

    dbsession.execute(text("DELETE FROM SysLog"))
    dbsession.execute(text("INSERT INTO SysLog (logdate, logtext) VALUES ('2026-09-29 12:35:10', 'legacy row')"))
    assert SysLogService(dbsession).search() == [{"logdate": "2026-09-29 12:35:10", "logtext": "legacy row"}]


def test_service_without_a_session_fails_loudly():
    from namifax.services.syslog import SysLogService

    with pytest.raises(RuntimeError, match="session"):
        SysLogService().search()


def test_helper_function_delegates_to_the_service(dbsession):
    from namifax.views.admin import get_all_syslogs

    dbsession.execute(text("DELETE FROM SysLog"))
    _add(dbsession, ("2026-10-01 10:00:00", "helper row"))
    assert get_all_syslogs(kw="helper", session=dbsession) == [{"logdate": "2026-10-01 10:00:00", "logtext": "helper row"}]
    assert get_all_syslogs(kw="helper") == []  # no session: nothing to read


def test_syslog_module_has_no_string_built_sql():
    src = (ROOT / "src/namifax/services/syslog.py").read_text()
    assert ".quote(" not in src and "FROM SysLog" not in src


# --- view ------------------------------------------------------------------------------

def test_view_lists_and_filters(admin_call, dbsession):
    from namifax.views.admin import admin_system_logs_view

    dbsession.execute(text("DELETE FROM SysLog"))
    _add(dbsession, ("2026-10-01 10:00:00", "alpha event"), ("2026-09-01 10:00:00", "beta event"))
    res = admin_call(admin_system_logs_view, "POST", {"kw": "event", "year": "2026", "month": "10", "_submit_check": "1"})
    assert [r["logtext"] for r in res["logs"]] == ["alpha event"]
    assert (res["kw"], res["year"], res["month"]) == ("event", "2026", "10")


# --- real servers (optional) -----------------------------------------------------------

@pytest.mark.serverdb
def test_server_database_search(monkeypatch, server_db_url, alembic_cfg):
    from namifax.models import SysLog
    from namifax.services.syslog import SysLogService

    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(server_db_url)
    try:
        with Session(engine) as session:
            _add(session, ("2026-10-01 10:00:00", "Disk 100% FULL"), ("2026-10-01 10:05:00", "한글 ünï 'q' \\x"),
                 ("2026-09-30 09:00:00", "older"))
            session.commit()
        with Session(engine) as session:
            svc = SysLogService(session)
            assert [r["logtext"] for r in svc.search()] == ["한글 ünï 'q' \\x", "Disk 100% FULL", "older"]
            assert [r["logtext"] for r in svc.search(kw="100%")] == ["Disk 100% FULL"]
            assert [r["logtext"] for r in svc.search(kw="DISK")] == ["Disk 100% FULL"]
            assert [r["logtext"] for r in svc.search(kw="ünï")] == ["한글 ünï 'q' \\x"]
            assert len(svc.search(year="2026", month="10", day="1")) == 2
            assert svc.search(kw="' OR '1'='1") == []
            svc.add("added via the service \\ 'q' 한글", logdate="2026-10-02 08:00:00")
            session.commit()
        with Session(engine) as session:
            svc = SysLogService(session)
            assert svc.search()[0] == {"logdate": "2026-10-02 08:00:00", "logtext": "added via the service \\ 'q' 한글"}
            count = session.execute(sa.select(sa.func.count()).select_from(SysLog)).scalar()
            assert count == 4
    finally:
        engine.dispose()
