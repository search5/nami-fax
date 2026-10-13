"""Boolean flags must never turn into text: 'False' is a true string and would grant privileges."""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from sqlsession import bare_session, empty_session, seeded_session

FLAGS = ("superuser", "can_del", "pwd_reuse", "is_admin", "wasreset", "acc_enabled", "deleted", "any_modem")


# --- the service writes real numbers ------------------------------------------------------------------

def test_an_account_created_through_the_service_stores_integers(seeded_db):
    from namifax.services.user_account import NFUserAccount

    assert NFUserAccount(db=seeded_db).create({"username": "viaservice", "password": "Secret123!", "email": "e@x.test"})
    columns = ", ".join(f"typeof({f}) AS t_{f}, {f}" for f in FLAGS)
    seeded_db.query(f"SELECT {columns} FROM UserAccount WHERE username = 'viaservice'")
    row = seeded_db.get_records()[0]
    for flag in FLAGS:
        assert row[f"t_{flag}"] == "integer", f"{flag} was stored as {row[f't_{flag}']}"
    assert (row["superuser"], row["can_del"], row["pwd_reuse"], row["any_modem"]) == (0, 0, 0, 0)
    assert (row["acc_enabled"], row["deleted"]) == (1, 0)


# --- existing rows written as text are repaired when the schema is initialised ---------------------

def _text_flag_account(db, username="legacytext"):
    assert db.query(
        "INSERT INTO UserAccount (username, password, email, superuser, can_del, pwd_reuse, any_modem, is_admin, "
        "wasreset, acc_enabled, deleted) VALUES "
        f"('{username}', 'x', '{username}@x.test', 'False', 'False', 'False', 'False', 'True', 'False', 'True', 'False')"
    ).executed


def test_text_flags_are_normalised_by_the_schema_initialisation():
    db = bare_session()
    db.upgrade_schema()
    _text_flag_account(db)
    db.upgrade_schema()
    db.query("SELECT superuser, can_del, pwd_reuse, any_modem, is_admin, wasreset, acc_enabled, deleted, "
             "typeof(superuser) AS t FROM UserAccount WHERE username = 'legacytext'")
    row = db.get_records()[0]
    assert (row["superuser"], row["can_del"], row["pwd_reuse"], row["any_modem"], row["wasreset"], row["deleted"]) == (0,) * 6
    assert (row["is_admin"], row["acc_enabled"]) == (1, 1) and row["t"] == "integer"


def test_normalising_twice_changes_nothing():
    db = bare_session()
    db.upgrade_schema()
    _text_flag_account(db)
    db.upgrade_schema()
    db.query("SELECT * FROM UserAccount ORDER BY uid")
    first = db.get_records()
    db.upgrade_schema()
    db.query("SELECT * FROM UserAccount ORDER BY uid")
    assert db.get_records() == first


# --- the ORM reads text flags correctly even if some writer still produces them --------------------

def test_the_orm_never_reads_the_text_false_as_true():
    from namifax.models import UserAccount

    db = bare_session()
    db.upgrade_schema()
    _text_flag_account(db)
    db.query("UPDATE UserAccount SET superuser = 'False'")      # undo the repair: simulate a stray writer
    user = db.execute(sa.select(UserAccount).where(UserAccount.username == "legacytext")).scalar_one()
    assert user.superuser is False and user.can_del is False and user.any_modem is False
    assert user.is_admin is True and user.acc_enabled is True
    db.disconnect()


@pytest.mark.parametrize("raw,expected", [
    (True, True), (False, False), (1, True), (0, False), ("1", True), ("0", False), ("True", True), ("False", False),
    ("true", True), ("false", False), ("t", True), ("f", False), ("yes", True), ("no", False), ("", False), (None, None),
    ("garbage", False),     # unknown text is refused rather than granted
])
def test_the_legacy_boolean_type_reads_every_spelling(raw, expected):
    from namifax.models.types import LegacyBoolean

    assert LegacyBoolean().process_result_value(raw, None) is expected


def test_the_legacy_boolean_type_is_a_normal_boolean_column_everywhere():
    from sqlalchemy.dialects import mysql, postgresql, sqlite
    from sqlalchemy.schema import CreateTable

    from namifax.models import UserAccount

    for dialect, needle in ((sqlite.dialect(), "BOOLEAN"), (mysql.dialect(), "BOOL"), (postgresql.dialect(), "BOOLEAN")):
        assert f"superuser {needle}" in str(CreateTable(UserAccount.__table__).compile(dialect=dialect))
