"""A database that is already at the newest revision is not migrated again at every start (the hooks run on every ring and fax)."""

from __future__ import annotations

from unittest.mock import patch

import sqlalchemy as sa

from namifax.db import bootstrap


def _engine(tmp_path):
    return sa.create_engine(f"sqlite:///{tmp_path / 'fast.db'}")


def test_the_second_start_does_not_run_the_migrations(tmp_path):
    engine = _engine(tmp_path)
    bootstrap.ensure_schema(engine)
    with patch.object(bootstrap, "upgrade_to_head") as upgrade, patch("namifax.db.adopt.adopt_existing_tables") as adopt:
        bootstrap.ensure_schema(engine)
    assert not upgrade.called and not adopt.called


def test_an_older_database_is_still_upgraded(tmp_path):
    engine = _engine(tmp_path)
    bootstrap.ensure_schema(engine)
    with engine.begin() as connection:
        connection.execute(sa.text("UPDATE alembic_version SET version_num = '0001'"))
    with patch.object(bootstrap, "upgrade_to_head") as upgrade:
        bootstrap.ensure_schema(engine)
    assert upgrade.called


def test_a_new_database_is_created(tmp_path):
    engine = _engine(tmp_path)
    bootstrap.ensure_schema(engine)
    assert "UserAccount" in sa.inspect(engine).get_table_names()
