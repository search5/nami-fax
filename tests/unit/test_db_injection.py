"""Spec 48: database provisioning (URL resolution, engine, isolation between apps)."""

from __future__ import annotations

import pytest
from pyramid.scripting import prepare


# --- 2.1 resolve_database_url -------------------------------------------------

def test_url_prefers_settings_over_env():
    from namifax.db.provider import resolve_database_url

    env = {"DATABASE_URL": "sqlite:///env.db", "AFDB_URL": "sqlite:///afdb.db"}
    assert resolve_database_url({"sqlalchemy.url": "sqlite:///s.db"}, env) == "sqlite:///s.db"


def test_url_database_url_beats_afdb_url():
    from namifax.db.provider import resolve_database_url

    env = {"DATABASE_URL": "sqlite:///env.db", "AFDB_URL": "sqlite:///afdb.db"}
    assert resolve_database_url({}, env) == "sqlite:///env.db"
    assert resolve_database_url({}, {"AFDB_URL": "sqlite:///afdb.db"}) == "sqlite:///afdb.db"


def test_url_falls_back_to_namifax_db_path():
    from namifax.db.provider import resolve_database_url

    assert resolve_database_url({}, {"NAMIFAX_DB_PATH": "/x/y.db"}) == "sqlite:////x/y.db"


def test_url_default_is_cwd_namifax_db(tmp_path, monkeypatch):
    from namifax.db.provider import resolve_database_url

    monkeypatch.chdir(tmp_path)
    url = resolve_database_url({}, {})
    assert url == f"sqlite:///{tmp_path.resolve() / 'namifax.db'}" or url.endswith("/namifax.db")


# --- 2.2 create_sa_engine -----------------------------------------------------

def test_memory_engine_shares_one_database_across_connections():
    from namifax.db.provider import create_sa_engine

    engine = create_sa_engine("sqlite://")
    c1 = engine.raw_connection()
    c1.driver_connection.execute("CREATE TABLE t (a INTEGER)")
    c1.driver_connection.execute("INSERT INTO t VALUES (1)")
    c1.driver_connection.commit()
    c2 = engine.raw_connection()
    assert c2.driver_connection.execute("SELECT a FROM t").fetchall() == [(1,)]


# --- 2.4 create_app -----------------------------------------------------------

def _make_app(db_file):
    from namifax import create_app

    return create_app(**{"sqlalchemy.url": f"sqlite:///{db_file}"})


def test_registry_holds_engine_and_tables_are_initialised(tmp_path):
    import sqlalchemy as sa

    app = _make_app(tmp_path / "a.db")
    engine = app.registry["dbengine"]
    assert engine is not None
    assert "UserAccount" in sa.inspect(engine).get_table_names()


def test_two_apps_with_different_urls_are_isolated(tmp_path):
    import sqlalchemy as sa

    app1 = _make_app(tmp_path / "one.db")
    app2 = _make_app(tmp_path / "two.db")
    with app1.registry["dbengine"].begin() as conn:
        conn.execute(sa.text("CREATE TABLE probe (v INTEGER)"))
    assert "probe" in sa.inspect(app1.registry["dbengine"]).get_table_names()
    assert "probe" not in sa.inspect(app2.registry["dbengine"]).get_table_names()   # app2 has no such table


def test_request_has_no_legacy_db_attribute(tmp_path):
    app = _make_app(tmp_path / "a.db")
    env = prepare(registry=app.registry)
    try:
        assert not hasattr(env["request"], "db")
    finally:
        env["closer"]()
