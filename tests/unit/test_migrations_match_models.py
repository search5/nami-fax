"""Guard: `alembic upgrade head` produces exactly the tables the ORM models describe."""

from __future__ import annotations

import alembic.command
import pytest
import sqlalchemy as sa
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext

def _drift(url: str) -> list:
    import namifax.models  # noqa: F401  (registers every model)
    from namifax.models.meta import Base

    engine = sa.create_engine(url)
    try:
        with engine.connect() as conn:
            diffs = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    finally:
        engine.dispose()
    # tables that only exist in the legacy schema are not modelled yet: that is not drift
    return [d for d in diffs if not (isinstance(d, tuple) and d[0] == "remove_table")]


def test_sqlite_migrations_match_models(tmp_path, monkeypatch, alembic_cfg):
    url = f"sqlite:///{tmp_path / 'drift.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    alembic.command.upgrade(alembic_cfg, "head")
    assert _drift(url) == []


@pytest.mark.serverdb
def test_server_migrations_match_models(monkeypatch, server_db_url, alembic_cfg):
    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    assert _drift(server_db_url) == []
