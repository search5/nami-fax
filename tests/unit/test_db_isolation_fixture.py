"""P3: every test runs against its own database, never the working-tree namifax.db."""

from __future__ import annotations

import os

import pytest

from sqlalchemy import text

from namifax.db.provider import cli_session, resolve_database_url


def test_default_database_url_is_not_the_working_tree_file():
    url = resolve_database_url({}, os.environ)
    assert url != f"sqlite:///{os.path.join(os.getcwd(), 'namifax.db')}"
    assert os.getcwd() not in url.replace("sqlite:///", "")


@pytest.mark.skipif(bool(os.environ.get("NAMIFAX_SUITE_DB")), reason="about the SQLite file in the working tree")
def test_cli_session_does_not_touch_the_working_tree_database():
    path = os.path.join(os.getcwd(), "namifax.db")
    before = os.stat(path).st_mtime_ns if os.path.exists(path) else None
    with cli_session(ensure_schema=True) as session:
        assert session.execute(text("SELECT COUNT(*) FROM UserAccount")).scalar() is not None
    after = os.stat(path).st_mtime_ns if os.path.exists(path) else None
    assert before == after
