"""B track, group 2: DynConf (call reject rules). The service behaves the same on a Session and the legacy engine."""

from __future__ import annotations

import alembic.command
import pytest
import sqlalchemy as sa
from sqlalchemy import Integer, String
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.dialects.mysql.mariadb import MariaDBDialect
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable


def test_model_maps_the_legacy_table():
    from namifax.models import DynConf

    t = DynConf.__table__
    assert t.name == "DynConf" and [c.name for c in t.primary_key.columns] == ["dynconf_id"]
    assert set(t.c.keys()) == {"dynconf_id", "device", "callid"}   # DynamicConfig (a twin nothing reads) is not modelled
    assert isinstance(t.c.dynconf_id.type, Integer) and t.c.dynconf_id.autoincrement is True
    assert isinstance(t.c.device.type, String) and t.c.device.type.length == 64 and t.c.device.nullable
    assert isinstance(t.c.callid.type, String) and t.c.callid.type.length == 255 and not t.c.callid.nullable


@pytest.mark.parametrize("dialect", [sqlite.dialect(), mysql.dialect(), MariaDBDialect(), postgresql.dialect()],
                         ids=["sqlite", "mysql", "mariadb", "postgresql"])
def test_ddl_compiles_for_every_supported_database(dialect):
    from namifax.models import DynConf

    assert "PRIMARY KEY (dynconf_id)" in str(CreateTable(DynConf.__table__).compile(dialect=dialect))


@pytest.fixture(params=["session", "engine"])
def rules(request, dbsession, seeded_db):
    from namifax.services.dynconf import DynamicConfig

    if request.param == "session":
        dbsession.execute(sa.text("DELETE FROM DynConf"))
        return DynamicConfig(db=dbsession)
    seeded_db.query("DELETE FROM DynConf")
    return DynamicConfig(db=seeded_db)


def test_create_lookup_and_ordered_listing(rules):
    assert rules.create("ttyS0", "5559999") is True and rules.create(None, "5551111") is True
    assert [r["callid"] for r in rules.list_rules()] == ["5551111", "5559999"]
    assert rules.lookup("ttyS0", "5559999") is True
    assert rules.lookup("ttyS1", "5559999") is False        # the rule is for ttyS0 only
    assert rules.lookup("ttyS1", "5551111") is True         # a rule without a device matches every modem
    assert rules.lookup("ttyS0", "000") is False


def test_duplicate_rules_are_rejected(rules):
    rules.create("ttyS0", "5559999")
    assert rules.create("ttyS0", "5559999") is False and rules.get_error() == "Rule already exists"


def test_load_save_and_remove(rules):
    rules.create("ttyS0", "5559999")
    rule_id = rules.get_dynconf_id()
    assert rules.load_rule(str(rule_id)) is True and (rules.get_device(), rules.get_callid()) == ("ttyS0", "5559999")
    assert rules.save_rule("ttyS1", "5550000") is True
    assert rules.load_rule(rule_id) and (rules.get_device(), rules.get_callid()) == ("ttyS1", "5550000")
    assert rules.remove(rule_id) is True and rules.list_rules() == []
    assert rules.load_rule(rule_id) is False and rules.get_error() == f"Rule {rule_id} doesn't exist"
    assert rules.load_rule(0) is False and rules.get_error() == "DynConf not selected"


def test_call_ids_with_quotes_backslashes_and_unicode_round_trip(rules):
    tricky = "o'brien\\' OR 1=1 -- 한글"
    rules.create("ttyS0", tricky)
    assert rules.lookup("ttyS0", tricky) is True


def test_admin_view_creates_updates_and_removes_rules_through_the_session(admin_call, dbsession):
    from namifax.views.admin import admin_dynconf_view

    dbsession.execute(sa.text("DELETE FROM DynConf"))
    made = admin_call(admin_dynconf_view, "POST", {"create": "1", "callid": "5551234", "device": "ttyS0"})
    assert made["message"] == "Blacklist rule created"
    rule_id = made["dynconf_rules"][0]["dynconf_id"]
    dup = admin_call(admin_dynconf_view, "POST", {"create": "1", "callid": "5551234", "device": "ttyS0"})
    assert dup["error"] == "Rule already exists"
    saved = admin_call(admin_dynconf_view, "POST", {"save": "1", "dynconf_id": str(rule_id), "callid": "5559999"})
    assert saved["message"] == "Blacklist rule updated"
    gone = admin_call(admin_dynconf_view, "POST", {"delete": "1", "dynconf_id": str(rule_id)})
    assert gone["message"] == "Blacklist rule removed" and gone["dynconf_rules"] == []


# --- command line: hooks use a session on the configured database -----------------------------

def test_dynconf_hook_rejects_a_blacklisted_caller_using_a_session(app, dbengine, capsys):
    from namifax.cli.dynconf import run_dynconf
    from namifax.services.dynconf import DynamicConfig

    with Session(dbengine) as session:
        DynamicConfig(db=session).create("ttyS0", "5559999")
        session.commit()
    assert run_dynconf(["dynconf", "ttyS0", "5559999"]) == 0
    assert "RejectCall: true" in capsys.readouterr().out
    assert run_dynconf(["dynconf", "ttyS0", "1111"]) == 0
    assert "RejectCall" not in capsys.readouterr().out


def test_import_blacklist_stores_rules_through_a_session(app, dbengine, tmp_path, capsys):
    from namifax.cli.import_blacklist import main

    listing = tmp_path / "bl.txt"
    listing.write_text("5551234\n5559999\n")
    assert main([str(listing), "ttyS0"]) == 0
    assert "Created 2 rules" in capsys.readouterr().out
    with Session(dbengine) as session:
        from namifax.services.dynconf import DynamicConfig

        callids = [r["callid"] for r in DynamicConfig(db=session).list_rules()]
        assert [c for c in callids if c in ("5551234", "5559999")] == ["5551234", "5559999"]  # next to the seeded demo rule


@pytest.mark.serverdb
def test_server_database_service(monkeypatch, server_db_url, alembic_cfg):
    from namifax.services.dynconf import DynamicConfig

    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(server_db_url)
    try:
        with Session(engine) as session:
            svc = DynamicConfig(db=session)
            assert svc.create("ttyS0", "5559999") and svc.create(None, "한글 'q' \\x")
            assert svc.create("ttyS0", "5559999") is False
            assert svc.lookup("ttyS0", "5559999") and svc.lookup("ttyS9", "한글 'q' \\x")
            assert {r["callid"] for r in svc.list_rules()} == {"5559999", "한글 'q' \\x"}  # collation decides the order
            assert svc.load_rule(str(svc.get_dynconf_id())) and svc.save_rule("ttyS1", "123")
            assert svc.remove(svc.get_dynconf_id()) is True
            session.commit()
        with Session(engine) as session:
            assert len(DynamicConfig(db=session).list_rules()) == 1
    finally:
        engine.dispose()
