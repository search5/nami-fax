"""B0-6: the Alembic baseline creates SystemConfig portably and coexists with the legacy SQLite schema."""

from __future__ import annotations

import sqlite3

import alembic.command
import alembic.config
import pytest
import sqlalchemy as sa

def _columns(engine, table):
    return {c["name"]: c for c in sa.inspect(engine).get_columns(table)}


def test_upgrade_creates_the_table_on_an_empty_database(tmp_path, monkeypatch, alembic_cfg):
    db_file = tmp_path / "fresh.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    alembic.command.upgrade(alembic_cfg, "head")

    engine = sa.create_engine(f"sqlite:///{db_file}")
    cols = _columns(engine, "SystemConfig")
    assert set(cols) == {"key", "value"}
    assert cols["key"]["nullable"] is False and cols["value"]["nullable"] is True
    assert sa.inspect(engine).get_pk_constraint("SystemConfig")["constrained_columns"] == ["key"]
    engine.dispose()


def test_upgrade_is_a_noop_for_a_table_the_legacy_schema_already_created(tmp_path, monkeypatch, alembic_cfg):
    from sqlsession import bare_session, empty_session, seeded_session

    db_file = tmp_path / "legacy.db"
    from namifax.db.bootstrap import ensure_schema
    from namifax.db.provider import create_sa_engine

    legacy = create_sa_engine(f"sqlite:///{db_file}")
    ensure_schema(legacy)                  # the start-up path creates the table (and fills the demo data)
    with legacy.begin() as conn:
        conn.execute(sa.text("INSERT INTO SystemConfig (key, value) VALUES ('keep', 'me')"))
    legacy.dispose()

    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    alembic.command.upgrade(alembic_cfg, "head")

    con = sqlite3.connect(db_file)
    try:
        assert con.execute("SELECT value FROM SystemConfig WHERE key = 'keep'").fetchone() == ("me",)
        assert con.execute("SELECT COUNT(*) FROM alembic_version").fetchone() == (1,)
    finally:
        con.close()


def test_downgrade_removes_the_table(tmp_path, monkeypatch, alembic_cfg):
    db_file = tmp_path / "down.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    alembic.command.upgrade(alembic_cfg, "head")
    alembic.command.downgrade(alembic_cfg, "base")

    engine = sa.create_engine(f"sqlite:///{db_file}")
    assert not sa.inspect(engine).has_table("SystemConfig")
    engine.dispose()


def test_there_is_exactly_one_head_revision(alembic_cfg):
    from alembic.script import ScriptDirectory

    assert len(ScriptDirectory.from_config(alembic_cfg).get_heads()) == 1


# --- real servers (optional): PostgreSQL, MySQL and MariaDB, see tests/conftest.py ---------------

@pytest.mark.serverdb
def test_server_database_baseline_and_orm_upsert(monkeypatch, server_db_url, alembic_cfg):
    from sqlalchemy.orm import Session

    from namifax.models import SystemConfig
    from namifax.services.system_config import SystemConfigService

    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")

    engine = sa.create_engine(server_db_url)
    try:
        cols = _columns(engine, "SystemConfig")
        assert str(cols["key"]["type"]) == "VARCHAR(255)" and str(cols["value"]["type"]).startswith("TEXT")
        with Session(engine) as session:
            svc = SystemConfigService(session)
            svc.set("k", "one")
            svc.set("k", "two")
            svc.set("tricky", "x\\' OR 1=1 --")
            svc.set("unicode", "한글 ünï")
            session.commit()
        with Session(engine) as session:
            svc = SystemConfigService(session)
            assert svc.get("k") == "two"
            assert svc.get("tricky") == "x\\' OR 1=1 --"
            assert svc.get("unicode") == "한글 ünï"
            count = session.execute(sa.select(sa.func.count()).select_from(SystemConfig)).scalar()
            assert count == 3
    finally:
        engine.dispose()
