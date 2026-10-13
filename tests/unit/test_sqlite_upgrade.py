"""SQLite databases written by older versions of the port are brought to the current layout, keeping their data."""

from __future__ import annotations

import sqlalchemy as sa

from sqlsession import bare_session, seeded_session


def _tables(db):
    db.query("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {r["name"] for r in db.get_records()}


def _columns(db, table):
    db.query(f"SELECT name FROM pragma_table_info('{table}')")
    return {r["name"] for r in db.get_records()}


def test_a_new_database_is_untouched_by_the_upgrade_step():
    from namifax.db.sqlite_upgrade import upgrade_existing_sqlite

    db = bare_session()
    with db.owned_engine.begin() as conn:
        upgrade_existing_sqlite(conn)
    assert _tables(db) == set()                      # nothing to upgrade, nothing created


def test_old_table_names_are_renamed_and_their_rows_kept():
    db = bare_session()
    db.query("CREATE TABLE DIDRouting (didr_id INTEGER PRIMARY KEY, routecode TEXT, alias TEXT, contact TEXT, printer TEXT, "
             "faxcatid INTEGER)")
    db.query("INSERT INTO DIDRouting (didr_id, routecode, alias) VALUES (4, '2000', 'Old route')")
    db.query("CREATE TABLE FaxPDFCategory (catid INTEGER PRIMARY KEY, name TEXT)")
    db.query("INSERT INTO FaxPDFCategory (catid, name) VALUES (9, 'Kept')")
    db.upgrade_schema()

    assert {"DIDRoute", "FaxCategory"} <= _tables(db) and not {"DIDRouting", "FaxPDFCategory"} & _tables(db)
    db.query("SELECT didr_id, routecode, alias FROM DIDRoute WHERE didr_id = 4")
    assert db.get_records() == [{"didr_id": 4, "routecode": "2000", "alias": "Old route"}]
    db.query("SELECT name FROM FaxCategory")
    assert [r["name"] for r in db.get_records()] == ["Kept"]            # no default categories on top of an existing one
    db.disconnect()


def test_columns_older_versions_lacked_are_added_without_touching_rows():
    db = bare_session()
    db.query("CREATE TABLE AddressBookFAX (abookfax_id INTEGER PRIMARY KEY AUTOINCREMENT, abook_id INTEGER, faxnumber TEXT NOT NULL)")
    db.query("INSERT INTO AddressBookFAX (abookfax_id, abook_id, faxnumber) VALUES (1, 5, '5551111')")
    db.query("CREATE TABLE FaxArchive (fid INTEGER PRIMARY KEY AUTOINCREMENT, pages INTEGER)")
    db.query("INSERT INTO FaxArchive (fid, pages) VALUES (3, 2)")
    db.upgrade_schema()

    assert {"email", "printer", "faxcatid", "description", "faxfrom", "faxto"} <= _columns(db, "AddressBookFAX")
    assert {"faxpath", "archstamp", "modemdev", "inbox", "faxcontent"} <= _columns(db, "FaxArchive")
    db.query("SELECT abook_id, faxnumber FROM AddressBookFAX WHERE abookfax_id = 1")
    assert db.get_records() == [{"abook_id": 5, "faxnumber": "5551111"}]
    db.query("SELECT fid, pages FROM FaxArchive WHERE fid = 3")
    assert db.get_records() == [{"fid": 3, "pages": 2}]
    db.disconnect()


def test_duplicate_id_columns_the_port_added_are_filled_from_the_legacy_ones():
    db = bare_session()
    db.query("CREATE TABLE BarcodeRoute (bcr_id INTEGER PRIMARY KEY AUTOINCREMENT, barcode TEXT NOT NULL, barcode_id INTEGER)")
    db.query("INSERT INTO BarcodeRoute (bcr_id, barcode) VALUES (6, 'B-6')")
    db.query("CREATE TABLE FaxArchive (fid INTEGER PRIMARY KEY AUTOINCREMENT, archivetime TEXT, archstamp TEXT)")
    db.query("INSERT INTO FaxArchive (fid, archivetime) VALUES (1, '2026-05-05 10:00:00')")
    db.upgrade_schema()

    db.query("SELECT barcode_id FROM BarcodeRoute WHERE bcr_id = 6")
    assert db.get_records() == [{"barcode_id": 6}]
    db.query("SELECT archstamp FROM FaxArchive WHERE fid = 1")
    assert db.get_records() == [{"archstamp": "2026-05-05 10:00:00"}]
    db.disconnect()


def test_the_upgrade_is_repeatable():
    db = seeded_session()
    db.query("SELECT name, sql FROM sqlite_master ORDER BY name")
    first = db.get_records()
    db.upgrade_schema()
    db.upgrade_schema()
    db.query("SELECT name, sql FROM sqlite_master ORDER BY name")
    assert db.get_records() == first
    db.disconnect()
