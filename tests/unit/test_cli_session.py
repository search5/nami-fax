"""cli_session(): an ORM session for command-line entry points (no request object)."""

from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy import text


def _url(tmp_path, name="s.db"):
    return {"DATABASE_URL": f"sqlite:///{tmp_path / name}"}


def test_session_uses_the_configured_database_and_commits_on_success(tmp_path):
    from namifax.db.provider import cli_session

    env = _url(tmp_path)
    with cli_session(environ=env, ensure_schema=True) as session:  # creates the schema
        session.execute(text("INSERT INTO SystemConfig (key, value) VALUES ('cs', 'committed')"))

    con = sqlite3.connect(tmp_path / "s.db")
    try:
        assert con.execute("SELECT value FROM SystemConfig WHERE key = 'cs'").fetchone() == ("committed",)
    finally:
        con.close()


def test_session_rolls_back_on_error(tmp_path):
    from namifax.db.provider import cli_session

    env = _url(tmp_path)
    with cli_session(environ=env, ensure_schema=True):
        pass
    with pytest.raises(RuntimeError):
        with cli_session(environ=env) as session:
            session.execute(text("INSERT INTO SystemConfig (key, value) VALUES ('rb', 'x')"))
            raise RuntimeError("boom")

    con = sqlite3.connect(tmp_path / "s.db")
    try:
        assert con.execute("SELECT COUNT(*) FROM SystemConfig WHERE key = 'rb'").fetchone() == (0,)
    finally:
        con.close()


def test_application_setting_beats_the_environment(tmp_path):
    from namifax.db.provider import cli_session

    env_file, app_file = tmp_path / "env.db", tmp_path / "app.db"
    with cli_session({"sqlalchemy.url": f"sqlite:///{app_file}"}, environ={"DATABASE_URL": f"sqlite:///{env_file}"}) as s:
        s.execute(text("SELECT 1"))
    assert app_file.exists() and not env_file.exists()


def test_session_is_closed_and_the_pool_released_on_exit(tmp_path):
    from namifax.db.provider import cli_session

    with cli_session(environ=_url(tmp_path)) as session:
        session.execute(text("SELECT 1"))
    assert not session.in_transaction()
