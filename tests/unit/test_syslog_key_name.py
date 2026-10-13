"""SysLog's key is called syslogid, as in the legacy AvantFAX schema (the port had called it log_id).

The name matters when the application is pointed at a database that the original AvantFAX created.
"""

from __future__ import annotations

import sqlite3

import alembic.command
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from namifax.db.bootstrap import ensure_schema
from namifax.db.provider import create_sa_engine


def _columns(engine):
    return [c["name"] for c in sa.inspect(engine).get_columns("SysLog")]


def test_a_new_database_uses_the_legacy_key_name(tmp_path):
    engine = create_sa_engine(f"sqlite:///{tmp_path / 'n.db'}")
    ensure_schema(engine)
    assert _columns(engine)[0] == "syslogid" and "log_id" not in _columns(engine)
    assert sa.inspect(engine).get_pk_constraint("SysLog")["constrained_columns"] == ["syslogid"]
    engine.dispose()


def test_an_older_database_is_renamed_in_place_keeping_its_log(tmp_path):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE SysLog (log_id INTEGER PRIMARY KEY AUTOINCREMENT, logdate TEXT NOT NULL, logtext TEXT NOT NULL)")
    con.execute("INSERT INTO SysLog (logdate, logtext) VALUES ('2026-01-01 10:00:00', 'first')")
    con.execute("INSERT INTO SysLog (logdate, logtext) VALUES ('2026-01-01 10:00:00', 'second')")
    con.commit()
    con.close()
    engine = create_sa_engine(f"sqlite:///{path}")
    ensure_schema(engine)
    ensure_schema(engine)                                   # and again: nothing more to do
    assert "syslogid" in _columns(engine) and "log_id" not in _columns(engine)
    with engine.connect() as c:
        rows = c.execute(sa.text("SELECT syslogid, logtext FROM SysLog WHERE logtext IN ('first', 'second') ORDER BY syslogid")).all()
    assert [tuple(r) for r in rows] == [(1, "first"), (2, "second")]
    engine.dispose()


def test_the_service_lists_newest_first_with_the_new_key(dbsession):
    from namifax.services.syslog import SysLogService

    svc = SysLogService(dbsession)
    svc.add("one")
    svc.add("two")
    assert [r["logtext"] for r in svc.search(kw="o")][:2] == ["two", "one"]


@pytest.mark.serverdb
def test_server_database_is_renamed_too(monkeypatch, server_db_url, alembic_cfg):
    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "0022")            # the database as it was before the rename
    engine = sa.create_engine(server_db_url)
    with engine.begin() as c:
        c.execute(sa.text("INSERT INTO \"SysLog\" (logdate, logtext) VALUES ('2026-01-01 10:00:00', 'kept')"
                          if engine.dialect.name == "postgresql" else
                          "INSERT INTO SysLog (logdate, logtext) VALUES ('2026-01-01 10:00:00', 'kept')"))
    alembic.command.upgrade(alembic_cfg, "head")
    assert _columns(engine)[0] == "syslogid"
    with Session(engine) as s:
        from namifax.models import SysLog

        assert [r.logtext for r in s.execute(sa.select(SysLog)).scalars()] == ["kept"]
        s.add(SysLog(logdate="2026-01-02 10:00:00", logtext="next"))          # the key still counts up by itself
        s.commit()
        assert sorted(r.syslogid for r in s.execute(sa.select(SysLog)).scalars()) == [1, 2]
    engine.dispose()
