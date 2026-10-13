"""Starting the application must never alter data that already exists.

The legacy schema code used to re-apply demo values on every start: it overwrote administrators' edits,
reset the admin password, replaced real faxes and linked unknown senders to the demo company.
"""

from __future__ import annotations

import pytest

from sqlsession import bare_session, empty_session, seeded_session


@pytest.fixture
def db():
    engine = bare_session()
    engine.upgrade_schema()
    yield engine
    engine.disconnect()


def _snapshot(db):
    db.query("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    out = {}
    for table in [r["name"] for r in db.get_records()]:
        db.query(f'SELECT * FROM "{table}"')
        out[table] = sorted((tuple(sorted(r.items())) for r in db.get_records()), key=repr)
    return out


def _as_edited_production_data(db):
    """Turn the demo rows into what an administrator's own data looks like."""
    for sql in [
        "UPDATE UserAccount SET password = 'e5768ace40674f0a98b2a1f2dd14e563' WHERE username = 'admin'",  # gitleaks:allow
        "UPDATE DIDRoute SET alias = 'My trunk' WHERE didr_id = 1",
        "UPDATE BarcodeRoute SET barcode_id = 7, barcode = 'REAL-7' WHERE barcode_id = 1",
        "UPDATE AddressBook SET company = 'Real Co Ltd' WHERE abook_id = 1",
        "UPDATE DistroList SET listname = 'Board' WHERE dl_id = 1",
        "DELETE FROM Modems WHERE devid = 2",
        "UPDATE Modems SET alias = 'Real modem', device = 'ttyUSB0' WHERE devid = 1",
        "DELETE FROM FaxCategory WHERE catid = 3",
        "UPDATE FaxCategory SET name = 'Contracts' WHERE catid = 1",
        "DELETE FROM CoverPages WHERE cover_id = 2",
        "UPDATE CoverPages SET title = 'house', file = 'house.ps' WHERE cover_id = 1",
        "UPDATE DynConf SET callid = '5551234' WHERE dynconf_id = 1",
        "DELETE FROM FaxArchive WHERE fid = 2",
        # an archived fax from an unknown sender: no company, no fax number link, no modem
        "UPDATE FaxArchive SET inbox = 0, companyid = NULL, faxnumid = NULL, modemdev = NULL, "
        "description = 'Real fax' WHERE fid = 1",
    ]:
        assert db.query(sql).executed, sql


def test_restarting_changes_nothing_in_a_database_with_real_data(db):
    _as_edited_production_data(db)
    before = _snapshot(db)
    db.upgrade_schema()  # what happens on every application start
    assert _snapshot(db) == before


def test_restarting_a_fresh_database_is_idempotent(db):
    before = _snapshot(db)
    db.upgrade_schema()
    assert _snapshot(db) == before


def test_no_demo_data_is_added_to_a_database_that_already_has_users():
    """`namifax createuser` first, then the server starts: the inbox must not fill with demo faxes."""
    engine = empty_session()          # the tables exist, no rows
    assert engine.query(
        "INSERT INTO UserAccount (uid, name, username, password, email, superuser, is_admin, can_del, any_modem, acc_enabled) "
        "VALUES (1, 'Real Admin', 'realadmin', 'e5768ace40674f0a98b2a1f2dd14e563', 'real@corp.test', 1, 1, 1, 1, 1)"  # gitleaks:allow
    ).executed

    engine.upgrade_schema()
    for table in ("AddressBook", "DistroList", "FaxArchive", "Modems", "DIDRoute", "BarcodeRoute", "DynConf", "SysLog"):
        engine.query(f"SELECT COUNT(*) AS n FROM {table}")
        assert engine.get_records()[0]["n"] == 0, f"demo rows were added to {table}"
    engine.query("SELECT username FROM UserAccount")
    assert [r["username"] for r in engine.get_records()] == ["realadmin"]
    engine.disconnect()


def test_the_original_default_cover_pages_are_provided_and_no_categories_are_made_up():
    """The original ships three cover pages (files that exist in the install) and no categories."""
    engine = empty_session()
    engine.query("INSERT INTO UserAccount (uid, name, username, password, email) VALUES (1, 'x', 'u', 'p', 'u@x.test')")
    engine.upgrade_schema()
    engine.query("SELECT file FROM CoverPages ORDER BY file")
    assert [r["file"] for r in engine.get_records()] == ["cover-letter.ps", "cover.ps", "coverpage.html"]
    engine.query("SELECT name FROM FaxCategory")
    assert engine.get_records() == []
    from pathlib import Path
    images = Path(__file__).resolve().parents[2] / "src" / "namifax" / "static" / "images"
    assert all((images / name).exists() for name in ("cover.ps", "cover-letter.ps", "coverpage.html"))
    engine.disconnect()
