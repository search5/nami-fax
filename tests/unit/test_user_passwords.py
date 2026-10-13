"""B track, group 3b: UserPasswords (password history). It never worked in the port: the column names differed."""

from __future__ import annotations

import alembic.command
import pytest
import sqlalchemy as sa
from sqlalchemy import Integer, String
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.dialects.mysql.mariadb import MariaDBDialect
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from sqlsession import bare_session, empty_session, seeded_session


def test_model_maps_the_legacy_table():
    from namifax.models import UserPasswords

    t = UserPasswords.__table__
    assert t.name == "UserPasswords" and [c.name for c in t.primary_key.columns] == ["upid"]
    assert set(t.c.keys()) == {"upid", "uid", "pwdhash"}
    assert isinstance(t.c.upid.type, Integer) and t.c.upid.autoincrement is True
    assert isinstance(t.c.uid.type, Integer) and not t.c.uid.nullable
    assert isinstance(t.c.pwdhash.type, String) and t.c.pwdhash.type.length == 255 and not t.c.pwdhash.nullable


@pytest.mark.parametrize("dialect", [sqlite.dialect(), mysql.dialect(), MariaDBDialect(), postgresql.dialect()],
                         ids=["sqlite", "mysql", "mariadb", "postgresql"])
def test_ddl_compiles_for_every_supported_database(dialect):
    from namifax.models import UserPasswords

    assert "PRIMARY KEY (upid)" in str(CreateTable(UserPasswords.__table__).compile(dialect=dialect))


# --- the legacy SQLite schema uses the legacy column names --------------------------------------

def _columns(db, table):
    db.query(f"SELECT name FROM pragma_table_info('{table}')")
    return [r["name"] for r in db.get_records()]


def test_a_new_sqlite_database_has_the_legacy_columns(seeded_db):
    assert _columns(seeded_db, "UserPasswords")[:3] == ["upid", "uid", "pwdhash"]


def test_a_table_created_by_an_older_port_version_is_renamed_in_place_keeping_its_rows():

    db = bare_session()
    db.upgrade_schema()
    db.query("DROP TABLE UserPasswords")
    db.query("CREATE TABLE UserPasswords (pwd_id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER NOT NULL, "
             "password TEXT NOT NULL, date TEXT)")
    db.query("INSERT INTO UserPasswords (uid, password, date) VALUES (7, 'abc123', '2026-01-01')")

    db.upgrade_schema()
    assert _columns(db, "UserPasswords")[:3] == ["upid", "uid", "pwdhash"]
    db.query("SELECT upid, uid, pwdhash FROM UserPasswords")
    assert db.get_records() == [{"upid": 1, "uid": 7, "pwdhash": "abc123"}]


# --- repositories: delete by condition (replaces a named-parameter raw DELETE) --------------------

def test_delete_where_on_both_repository_implementations(dbsession, seeded_db):
    from namifax.db.repository import Repository

    for backend, run in ((dbsession, lambda q: backend.execute(sa.text(q))), (seeded_db, lambda q: seeded_db.query(q))):
        run("DELETE FROM UserPasswords")
        repo = Repository("UserPasswords", db=backend)
        for uid, h in ((1, "a"), (1, "b"), (2, "c")):
            repo.new_entry({"uid": uid, "pwdhash": h})
        assert repo.delete_where({"uid": 1}) == 2
        assert [r["pwdhash"] for r in repo.find(reduce_single=False)] == ["c"]
        assert repo.delete_where({"uid": 99}) == 0
        assert repo.delete_where({"uid": None}) == 0          # = NULL matches nothing
        assert repo.delete_where({}) == 0                     # never wipes a table by accident


# --- the service on both backends -----------------------------------------------------------------

@pytest.fixture(params=["session", "engine"])
def history(request, dbsession, seeded_db):
    from namifax.services.user_passwords import NFUserPasswords

    if request.param == "session":
        dbsession.execute(sa.text("DELETE FROM UserPasswords"))
        return NFUserPasswords(db=dbsession)
    seeded_db.query("DELETE FROM UserPasswords")
    return NFUserPasswords(db=seeded_db)


def test_a_logged_password_is_recognised_as_used(history):
    assert history.log_password("Secret123!", 5) is True
    assert history.password_used("Secret123!", 5) is True
    assert history.password_used("Other456!", 5) is False
    assert history.password_used("Secret123!", 6) is False        # history is per user


def test_the_hash_not_the_password_is_stored(history):
    from namifax.common.passwords import verify_password
    from namifax.db.repository import Repository

    history.log_password("Secret123!", 5)
    stored = Repository("UserPasswords", db=history.db).find({"uid": 5})
    assert stored["pwdhash"].startswith("$argon2id$") and verify_password(stored["pwdhash"], "Secret123!")
    assert stored["pwdhash"] != "Secret123!"


def test_missing_arguments_are_rejected(history):
    assert history.log_password("", 1) is False and history.log_password("x", None) is False
    assert history.password_used("", 1) is False and history.password_used("x", None) is False
    assert history.clear_hashes(None) is False


def test_clear_hashes_removes_only_that_users_history(history):
    history.log_password("One1!aaaa", 1)
    history.log_password("Two2!bbbb", 1)
    history.log_password("Three3!ccc", 2)
    assert history.clear_hashes(1) is True
    assert history.password_used("One1!aaaa", 1) is False and history.password_used("Three3!ccc", 2) is True


# --- the account policy that depends on it ---------------------------------------------------------

def test_a_new_account_logs_its_initial_password_and_reuse_is_blocked(seeded_db):
    from namifax.services.user_account import NFUserAccount

    seeded_db.query("DELETE FROM UserPasswords")
    acct = NFUserAccount(db=seeded_db)
    assert acct.create({"username": "histuser", "password": "Initial123!", "name": "H", "email": "h@x.test",
                        "pwd_reuse": 0})
    assert acct.userpasswords.password_used("Initial123!", acct.uid) is True
    assert acct.change_password("Initial123!") is False and acct.error == "Password has already been used before"
    assert acct.change_password("Brand-new456!") is True


@pytest.mark.serverdb
def test_server_database_history(monkeypatch, server_db_url, alembic_cfg):
    from namifax.models import UserPasswords
    from namifax.services.user_passwords import NFUserPasswords

    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(server_db_url)
    try:
        with Session(engine) as session:
            svc = NFUserPasswords(db=session)
            assert svc.log_password("pa'ss\\' 한글", 1) and svc.log_password("two", 1) and svc.log_password("x", 2)
            assert svc.password_used("pa'ss\\' 한글", 1) and not svc.password_used("pa'ss\\' 한글", 2)
            assert svc.clear_hashes(1) is True
            session.commit()
        with Session(engine) as session:
            count = session.execute(sa.select(sa.func.count()).select_from(UserPasswords)).scalar()
            assert count == 1
    finally:
        engine.dispose()
