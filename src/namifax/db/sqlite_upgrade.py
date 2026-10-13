"""Bring a SQLite database written by an older version of the port up to the current table layout.

New databases get their tables from the Alembic revisions, on every supported database. This module is for the
one case Alembic cannot see: a SQLite file that already contains tables made by earlier versions of the port (whose
layout differed from the legacy AvantFAX schema the models follow). It runs *before* ``alembic upgrade head`` and
only touches tables that already exist, so on a new database it does nothing. Every step is idempotent.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

_ADDRESS_BOOK_COLUMNS = ["company", "description", "faxtype", "faxnum", "phonenum", "email", "address", "city",
                         "state", "zip", "country"]

# columns older versions did not create (name, DDL) per table
_ADDED_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "AddressBookEmail": [("abookemail_id", "INTEGER"), ("contact_name", "TEXT"), ("contact_email", "TEXT"),
                         ("abook_id", "INTEGER")],
    "AddressBookFAX": [("email", "TEXT"), ("printer", "TEXT"), ("faxcatid", "INTEGER"), ("description", "TEXT"),
                       ("to_person", "TEXT"), ("to_location", "TEXT"), ("to_voicenumber", "TEXT"),
                       ("faxfrom", "INTEGER DEFAULT 0"), ("faxto", "INTEGER DEFAULT 0")],
    "BarcodeRoute": [("barcode_id", "INTEGER")],
    "FaxArchive": [("faxpath", "TEXT"), ("faxnumid", "INTEGER"), ("companyid", "INTEGER"), ("faxcatid", "INTEGER"),
                   ("didr_id", "INTEGER"), ("lastoperation", "TEXT"), ("lastmoduser", "INTEGER"),
                   ("lastmoddate", "TEXT"), ("archstamp", "TEXT"), ("modemdev", "TEXT"), ("userid", "INTEGER"),
                   ("origfaxnum", "TEXT"), ("faxcontent", "TEXT"), ("pages", "INTEGER"), ("description", "TEXT"),
                   ("inbox", "INTEGER DEFAULT 1")],
}

_USER_ACCOUNT_FLAGS = ("superuser", "can_del", "pwd_reuse", "is_admin", "wasreset", "acc_enabled", "deleted", "any_modem")


def _tables(conn: Connection) -> set[str]:
    return {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'"))}


def _columns(conn: Connection, table: str) -> set[str]:
    return {r[0] for r in conn.execute(text(f"SELECT name FROM pragma_table_info('{table}')"))}


def _primary_key(conn: Connection, table: str) -> list[str]:
    return [r[0] for r in conn.execute(text(f"SELECT name FROM pragma_table_info('{table}') WHERE pk = 1"))]


def upgrade_existing_sqlite(conn: Connection) -> None:
    """Run every step that applies to the tables this database already has."""
    _rename_old_table_names(conn)
    _rename_user_passwords_columns(conn)
    _migrate_address_book_keys(conn)
    _add_missing_columns(conn)
    _backfill_alias_columns(conn)
    _normalize_boolean_flags(conn)


def _rename_old_table_names(conn: Connection) -> None:
    """The port once called the tables DIDRouting and FaxPDFCategory; the legacy schema says DIDRoute and FaxCategory."""
    tables = _tables(conn)
    for old, new in (("DIDRouting", "DIDRoute"), ("FaxPDFCategory", "FaxCategory")):
        if old in tables and new not in tables:
            conn.execute(text(f"ALTER TABLE {old} RENAME TO {new}"))


def _rename_user_passwords_columns(conn: Connection) -> None:
    """Older versions created UserPasswords(pwd_id, uid, password, date) while the service uses the legacy names
    (upid, uid, pwdhash), so nothing was ever stored. Rename the columns in place."""
    if "UserPasswords" not in _tables(conn):
        return
    columns = _columns(conn, "UserPasswords")
    if "pwd_id" in columns and "upid" not in columns:
        conn.execute(text("ALTER TABLE UserPasswords RENAME COLUMN pwd_id TO upid"))
    if "password" in columns and "pwdhash" not in columns:
        conn.execute(text("ALTER TABLE UserPasswords RENAME COLUMN password TO pwdhash"))


def _migrate_address_book_keys(conn: Connection) -> None:
    """Older versions made ab_id the key of AddressBook while the code (and the legacy schema) use abook_id, so a
    new company could not be found by id until the next start filled a copy of it.

    Rebuild AddressBook with abook_id as the key, keeping every id (so the links from the fax numbers and e-mail
    contacts stay valid), and fill the link columns of the two child tables from their old copies.
    """
    tables = _tables(conn)
    if "AddressBook" in tables and _primary_key(conn, "AddressBook") == ["ab_id"]:
        old = _columns(conn, "AddressBook")
        selects = ["COALESCE(abook_id, ab_id)" if "abook_id" in old else "ab_id"] + [
            c if c in old else "NULL" for c in _ADDRESS_BOOK_COLUMNS]
        conn.execute(text("DROP TABLE IF EXISTS AddressBook_rebuild"))
        conn.execute(text("CREATE TABLE AddressBook_rebuild (abook_id INTEGER PRIMARY KEY AUTOINCREMENT, "
                          + ", ".join(f"{c} TEXT" for c in _ADDRESS_BOOK_COLUMNS) + ")"))
        conn.execute(text("INSERT INTO AddressBook_rebuild (abook_id, " + ", ".join(_ADDRESS_BOOK_COLUMNS)
                          + ") SELECT " + ", ".join(selects) + " FROM AddressBook"))
        conn.execute(text("DROP TABLE AddressBook"))
        conn.execute(text("ALTER TABLE AddressBook_rebuild RENAME TO AddressBook"))
    for table in ("AddressBookFAX", "AddressBookEmail"):
        if table in tables and {"ab_id", "abook_id"} <= _columns(conn, table):
            conn.execute(text(f"UPDATE {table} SET abook_id = ab_id WHERE abook_id IS NULL AND ab_id IS NOT NULL"))
    if "AddressBookEmail" in tables:
        columns = _columns(conn, "AddressBookEmail")
        if {"to_person", "contact_name"} <= columns:
            conn.execute(text("UPDATE AddressBookEmail SET contact_name = to_person WHERE contact_name IS NULL"))
        if {"email", "contact_email"} <= columns:
            conn.execute(text("UPDATE AddressBookEmail SET contact_email = email WHERE contact_email IS NULL"))


def _add_missing_columns(conn: Connection) -> None:
    tables = _tables(conn)
    for table, columns in _ADDED_COLUMNS.items():
        if table not in tables:
            continue
        present = _columns(conn, table)
        for name, ddl in columns:
            if name not in present:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def _backfill_alias_columns(conn: Connection) -> None:
    """Fill the duplicate id columns the port added from the legacy ones (NULL values only)."""
    tables = _tables(conn)
    if "BarcodeRoute" in tables and {"barcode_id", "bcr_id"} <= _columns(conn, "BarcodeRoute"):
        conn.execute(text("UPDATE BarcodeRoute SET barcode_id = bcr_id WHERE barcode_id IS NULL AND bcr_id IS NOT NULL"))
    if "FaxArchive" in tables and {"archstamp", "archivetime"} <= _columns(conn, "FaxArchive"):
        conn.execute(text("UPDATE FaxArchive SET archstamp = archivetime "
                          "WHERE archstamp IS NULL AND archivetime IS NOT NULL"))


def _normalize_boolean_flags(conn: Connection) -> None:
    """Turn flags the old code stored as the text 'True'/'False' back into 0/1 (only values that really are text)."""
    if "UserAccount" not in _tables(conn):
        return
    present = _columns(conn, "UserAccount")
    for flag in _USER_ACCOUNT_FLAGS:
        if flag in present:
            conn.execute(text(
                f"UPDATE UserAccount SET {flag} = CASE WHEN lower({flag}) IN ('1', 'true', 't', 'yes', 'y', 'on') "
                f"THEN 1 ELSE 0 END WHERE typeof({flag}) = 'text'"))
