"""Legacy schema init: no dead twin table, and the demo rule never overwrites the administrator's data."""

from __future__ import annotations

import pytest

from sqlsession import bare_session, empty_session, seeded_session


@pytest.fixture
def db():
    engine = bare_session()
    engine.upgrade_schema()
    yield engine
    engine.disconnect()


def _tables(db):
    db.query("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {r["name"] for r in db.get_records()}


def test_the_unused_twin_table_is_no_longer_created(db):
    assert "DynConf" in _tables(db)
    assert "DynamicConfig" not in _tables(db)


def test_a_fresh_database_gets_the_demo_rule(db):
    db.query("SELECT dynconf_id, callid, device FROM DynConf")
    assert db.get_records() == [{"dynconf_id": 1, "callid": "01012345678", "device": "ttyS0"}]


def test_restarting_does_not_overwrite_an_edited_rule(db):
    db.query("UPDATE DynConf SET callid = '5551234', device = 'ttyS9' WHERE dynconf_id = 1")
    db.query("INSERT INTO DynConf (callid, device) VALUES ('5559999', NULL)")
    db.upgrade_schema()  # what happens on every application start
    db.query("SELECT dynconf_id, callid, device FROM DynConf ORDER BY dynconf_id")
    assert db.get_records() == [
        {"dynconf_id": 1, "callid": "5551234", "device": "ttyS9"},
        {"dynconf_id": 2, "callid": "5559999", "device": None},
    ]


def test_an_existing_twin_table_from_an_older_install_is_left_alone(db):
    db.query("CREATE TABLE DynamicConfig (dynconf_id INTEGER PRIMARY KEY AUTOINCREMENT, device TEXT, callid TEXT NOT NULL)")
    db.upgrade_schema()
    assert "DynamicConfig" in _tables(db)  # harmless leftover: never dropped behind the administrator's back
