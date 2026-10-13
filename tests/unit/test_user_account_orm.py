"""B track, group 3d-1: UserAccount. The service behaves the same on a Session and on the legacy engine."""

from __future__ import annotations

from namifax.models.types import IsoText

from datetime import datetime, timedelta

import alembic.command
import pytest
import sqlalchemy as sa
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.dialects.mysql.mariadb import MariaDBDialect
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

LEGACY_COLUMNS = {
    "uid", "name", "username", "password", "email", "email_sig", "user_tsi", "from_company", "from_location",
    "from_voicenumber", "from_faxnumber", "coverpage_id", "audiofile", "faxperpageinbox", "faxperpagearchive",
    "superuser", "can_del", "last_mod", "last_login", "last_ip", "language", "modemdevs", "didrouting", "faxcats",
    "pwdexpire", "pwdcycle", "pwd_reuse", "is_admin", "wasreset", "acc_enabled", "deleted", "any_modem"}
FLAGS = {"superuser", "can_del", "pwd_reuse", "is_admin", "wasreset", "acc_enabled", "deleted", "any_modem"}


def test_model_maps_the_legacy_table():
    from namifax.models import UserAccount

    t = UserAccount.__table__
    assert t.name == "UserAccount" and [c.name for c in t.primary_key.columns] == ["uid"]
    assert set(t.c.keys()) == LEGACY_COLUMNS
    assert isinstance(t.c.uid.type, Integer) and t.c.uid.autoincrement is True
    from namifax.models.types import LegacyBoolean

    for flag in FLAGS:                                   # booleans that also read the old text spellings safely
        assert isinstance(t.c[flag].type, LegacyBoolean) and isinstance(t.c[flag].type.impl, Boolean), flag
    for name in ("username", "password", "email"):
        assert not t.c[name].nullable, name
    assert t.c.username.unique is True and t.c.username.type.length == 64
    assert t.c.email.type.length == 255 and t.c.password.type.length == 255
    for name in ("last_mod", "last_login", "pwdexpire"):              # ISO text, readable on every database
        assert isinstance(t.c[name].type, (String, IsoText)) and t.c[name].type.length == 32, name


@pytest.mark.parametrize("dialect", [sqlite.dialect(), mysql.dialect(), MariaDBDialect(), postgresql.dialect()],
                         ids=["sqlite", "mysql", "mariadb", "postgresql"])
def test_ddl_compiles_for_every_supported_database(dialect):
    from namifax.models import UserAccount

    ddl = str(CreateTable(UserAccount.__table__).compile(dialect=dialect))
    assert "PRIMARY KEY (uid)" in ddl and "UNIQUE (username)" in ddl


@pytest.fixture(params=["session", "engine"])
def acct(request, dbsession, seeded_db):
    from namifax.services.user_account import NFUserAccount

    if request.param == "session":
        dbsession.execute(sa.text("DELETE FROM UserPasswords"))
        dbsession.execute(sa.text("DELETE FROM UserAccount"))
        svc = NFUserAccount(db=dbsession)
    else:
        seeded_db.query("DELETE FROM UserPasswords")
        seeded_db.query("DELETE FROM UserAccount")
        svc = NFUserAccount(db=seeded_db)
    svc.backend = request.param
    return svc


def _fresh(a):
    return type(a)(db=a.db)


def _new(a, username="alice", password="Secret123!", email=None, **extra):
    user = _fresh(a)
    details = {"username": username, "password": password, "name": username.title(),
               "email": email or f"{username}@x.test", **extra}
    assert user.create(details), user.error
    return user


# --- create ----------------------------------------------------------------------------------------

def test_create_validates_and_rejects_duplicates(acct):
    assert acct.create({"username": "bad name!", "email": "a@x.test"}) is False
    assert acct.error.startswith("Invalid username format")
    assert acct.create({"username": "ok", "email": ""}) is False and acct.error == "Email address required"
    _new(acct, "alice")
    other = _fresh(acct)
    assert other.create({"username": "alice", "email": "other@x.test"}) is False and other.error == "Username already in use"
    assert other.create({"username": "bob", "email": "alice@x.test"}) is False and other.error == "Email already in use"


def test_create_stores_the_argon2id_hash_defaults_and_expiry(acct):
    from namifax.common.passwords import verify_password

    user = _new(acct, "alice", "Secret123!", pwdcycle="3")
    row = _fresh(acct)
    assert row.load(user.uid) and verify_password(row.dbdata["password"], "Secret123!")
    assert row.dbdata["acc_enabled"] and not row.dbdata["is_admin"] and not row.dbdata["deleted"]
    assert not row.dbdata["wasreset"]
    expected = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
    assert row.dbdata["pwdexpire"] == expected


def test_create_without_a_password_generates_one_and_forces_a_change(acct):
    user = _fresh(acct)
    assert user.create({"username": "gen", "email": "gen@x.test"}) is True
    row = _fresh(acct)
    assert row.load(user.uid) and row.dbdata["wasreset"] and row.dbdata["password"].startswith("$argon2id$")


def test_the_initial_password_goes_into_the_history(acct):
    user = _new(acct, "alice", "Secret123!")
    assert user.userpasswords.password_used("Secret123!", user.uid) is True


# --- login ------------------------------------------------------------------------------------------

def test_login_succeeds_and_records_the_time_and_address(acct):
    _new(acct, "alice", "Secret123!")
    # a first login always asks for a new password: give the account a login time so it is a normal one
    first = _fresh(acct)
    assert first.login("alice", "Secret123!", remote_ip="10.0.0.5") is True
    assert first.check_login() and not first.check_admin_login() and first.is_expired() is True   # first login
    again = _fresh(acct)
    assert again.login("alice", "Secret123!", remote_ip="10.0.0.6") is True and again.is_expired() is False
    row = _fresh(acct)
    assert row.load(again.uid) and row.dbdata["last_ip"] == "10.0.0.6" and row.dbdata["last_login"]


def test_login_failures(acct):
    _new(acct, "alice", "Secret123!")
    for user, pwd in (("alice", "wrong"), ("nobody", "Secret123!"), ("alice", "")):
        attempt = _fresh(acct)
        assert attempt.login(user, pwd) is False and attempt.error == "Incorrect username or password"
        assert not attempt.check_login()


def test_a_password_hash_cannot_be_used_as_the_password(acct):
    """The stored MD5 must never work as a credential (pass-the-hash)."""
    from namifax.auth.password import PasswordManager

    _new(acct, "alice", "Secret123!")
    stolen = PasswordManager.hash_password("Secret123!")
    assert _fresh(acct).login("alice", stolen) is False
    assert _fresh(acct).login("alice", "Secret123!") is True


def test_a_plaintext_password_in_the_table_is_not_accepted(acct):
    user = _new(acct, "alice", "Secret123!")
    upd = _fresh(acct)
    assert upd.load(user.uid)
    upd.dbdata["password"] = "PlainTextSecret"
    assert upd.update() is True
    assert _fresh(acct).login("alice", "PlainTextSecret") is False


def test_a_disabled_account_cannot_log_in_and_admin_only_login_needs_an_admin(acct):
    user = _new(acct, "alice", "Secret123!")
    admin = _new(acct, "root", "Secret123!", is_admin=1)
    disabled = _fresh(acct)
    assert disabled.load(user.uid)
    disabled.dbdata["acc_enabled"] = 0
    disabled.update()
    attempt = _fresh(acct)
    assert attempt.login("alice", "Secret123!") is False and attempt.error == "Account is disabled"
    assert _fresh(acct).login("alice", "Secret123!", admin=True) is False
    as_admin = _fresh(acct)
    assert as_admin.login("root", "Secret123!", admin=True) is True and as_admin.check_admin_login()


def test_password_expiry_and_reset_flags_force_a_change(acct):
    user = _new(acct, "alice", "Secret123!", pwdcycle="3")
    warm = _fresh(acct)
    warm.login("alice", "Secret123!")                          # consume the first-login flag
    row = _fresh(acct)
    assert row.load(user.uid)
    row.dbdata["pwdexpire"] = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    row.update()
    assert _fresh(acct).login("alice", "Secret123!") and _fresh_login(acct, "alice").is_expired() is True


def _fresh_login(a, username):
    user = _fresh(a)
    assert user.login(username, "Secret123!")
    return user


def test_webauthn_login_by_username(acct):
    _new(acct, "alice", "Secret123!")
    ok = _fresh(acct)
    assert ok.login_webauth("alice", remote_ip="10.1.1.1") is True and ok.check_login()
    missing = _fresh(acct)
    assert missing.login_webauth("nobody") is False and "not found" in missing.error


# --- loading and listing ----------------------------------------------------------------------------

def test_load_by_id_username_and_email(acct):
    user = _new(acct, "alice", email="alice@corp.test")
    for method, arg in (("load", user.uid), ("load", str(user.uid)), ("load_username", "alice"),
                        ("loadbyemail", "alice@corp.test")):
        other = _fresh(acct)
        assert getattr(other, method)(arg) is True and other.dbdata["username"] == "alice"
    other = _fresh(acct)
    assert other.load(99999) is False and other.error == "Invalid userid"
    assert other.load_username("nobody") is False and other.error == "Invalid username"
    assert other.loadbyemail("no@x.test") is False and other.error == "Invalid email"


def test_list_accounts_skips_deleted_ones_and_orders_by_name(acct):
    for name in ("zed", "amy", "bob"):
        _new(acct, name)
    assert [a["username"] for a in _fresh(acct).list_accounts()] == ["amy", "bob", "zed"]
    assert _fresh(acct).remove(_fresh_uid(acct, "bob")) is True
    assert [a["username"] for a in _fresh(acct).list_accounts()] == ["amy", "zed"]


def _fresh_uid(a, username):
    other = _fresh(a)
    assert other.load_username(username)
    return other.uid


# --- changing things --------------------------------------------------------------------------------

def test_update_saves_the_loaded_values(acct):
    user = _new(acct, "alice")
    edit = _fresh(acct)
    assert edit.load(user.uid)
    edit.dbdata.update({"name": "Alice A.", "from_company": "Acme", "faxperpageinbox": 25, "is_admin": 1})
    assert edit.user_update() is True
    check = _fresh(acct)
    assert check.load(user.uid) and (check.dbdata["name"], check.dbdata["from_company"], check.dbdata["faxperpageinbox"]) == (
        "Alice A.", "Acme", 25)
    assert check.dbdata["is_admin"]


def test_change_password_rules_and_reuse(acct):
    user = _new(acct, "alice", "Secret123!")
    edit = _fresh(acct)
    assert edit.load(user.uid)
    assert edit.change_password("short") is False and "too short" in edit.error
    assert edit.change_password("x" * 65) is False and "too long" in edit.error
    assert edit.change_password("Secret123!") is False and edit.error == "Password has already been used before"
    assert edit.change_password("Brand-new456!") is True
    assert _fresh(acct).login("alice", "Brand-new456!") is True and _fresh(acct).login("alice", "Secret123!") is False


def test_set_newpassword_needs_the_old_one(acct):
    user = _new(acct, "alice", "Secret123!")
    edit = _fresh(acct)
    assert edit.load(user.uid)
    assert edit.set_newpassword("WrongOld123!", "Brand-new456!") is False and edit.error == "Incorrect old password"
    assert edit.set_newpassword("Secret123!", "Brand-new456!") is True


def test_reset_password_returns_a_new_one_and_forces_a_change(acct):
    _new(acct, "alice", "Secret123!", email="alice@corp.test")
    flow = _fresh(acct)
    ok, new_pwd = flow.reset_password("alice@corp.test")
    assert ok is True and new_pwd and _fresh(acct).login("alice", new_pwd) is True
    assert _fresh(acct).login("alice", "Secret123!") is False
    assert _fresh(acct).reset_password("nobody@x.test") == (False, None)


def test_username_and_email_must_stay_unique_but_a_user_may_keep_their_own(acct):
    alice, bob = _new(acct, "alice"), _new(acct, "bob")
    edit = _fresh(acct)
    assert edit.load(alice.uid)
    assert edit.set_username("alice") is True and edit.set_email("alice@x.test") is True       # unchanged
    assert edit.set_username("bob") is False and edit.error == "Username already in use"
    assert edit.set_email("bob@x.test") is False and edit.error == "Email already in use"
    assert edit.set_username("alice2") is True and edit.set_username("bad name!") is False


def test_permission_lists_round_trip(acct):
    user = _new(acct, "alice")
    edit = _fresh(acct)
    assert edit.load(user.uid)
    assert edit.set_modemdevs(["ttyS0", "ttyS1"]) and edit.set_faxcats([1, 2]) and edit.set_didrouting(["1000"])
    edit.update()
    check = _fresh(acct)
    assert check.load(user.uid)
    assert (check.get_modemdevs(), check.get_faxcats(), check.get_didrouting()) == (["ttyS0", "ttyS1"], ["1", "2"], ["1000"])
    assert edit.set_modemdevs(None) and edit.update() and _fresh(acct).load(user.uid)


# --- removing an account (the soft delete never worked) ---------------------------------------------

def test_a_removed_account_is_really_gone_and_its_name_and_email_can_be_reused(acct):
    user = _new(acct, "alice", "Secret123!", email="alice@corp.test")
    assert acct.userpasswords.password_used("Secret123!", user.uid) is True
    assert _fresh(acct).remove(user.uid) is True

    assert _fresh(acct).login("alice", "Secret123!") is False                 # cannot log in any more
    assert _fresh(acct).load_username("alice") is False and _fresh(acct).loadbyemail("alice@corp.test") is False
    row = _fresh(acct)
    assert row.load(user.uid) and row.dbdata["deleted"] and not row.dbdata["acc_enabled"] and row.dbdata["wasreset"]
    assert acct.userpasswords.password_used("Secret123!", user.uid) is False  # history cleared
    _new(acct, "alice", "Other456!", email="alice@corp.test")                 # the name and address are free again


def test_removing_two_accounts_does_not_collide(acct):
    one, two = _new(acct, "one"), _new(acct, "two")
    assert _fresh(acct).remove(one.uid) is True and _fresh(acct).remove(two.uid) is True
    assert _fresh(acct).remove(0) is False and _fresh(acct).remove(99999) is False


def test_values_with_quotes_backslashes_and_unicode_round_trip(acct):
    tricky = "o'brien\\' OR 1=1 -- 한글"
    user = _new(acct, "alice", name=tricky, from_company=tricky)
    assert _fresh(acct).load(user.uid) and _fresh(acct).load_username("alice")
    check = _fresh(acct)
    check.load(user.uid)
    assert check.dbdata["name"] == tricky and check.dbdata["from_company"] == tricky


# --- real servers (optional) --------------------------------------------------------------------------

@pytest.mark.serverdb
def test_server_database_service(monkeypatch, server_db_url, alembic_cfg):
    from namifax.models import UserAccount
    from namifax.services.user_account import NFUserAccount

    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(server_db_url)
    try:
        with Session(engine) as session:
            svc = NFUserAccount(db=session)
            assert svc.create({"username": "alice", "password": "Secret123!", "email": "a@x.test", "name": "Amy 'q' 한글 \\x",
                               "is_admin": 1, "pwdcycle": "6"})
            assert NFUserAccount(db=session).create({"username": "alice", "email": "z@x.test"}) is False
            assert NFUserAccount(db=session).login("alice", "Secret123!", admin=True) is True
            assert NFUserAccount(db=session).login("alice", "wrong") is False
            two = NFUserAccount(db=session)
            assert two.create({"username": "bob", "password": "Secret123!", "email": "b@x.test", "name": "Zed Bob"})
            assert [a["username"] for a in NFUserAccount(db=session).list_accounts()] == ["alice", "bob"]
            assert NFUserAccount(db=session).remove(two.uid) is True
            assert NFUserAccount(db=session).create({"username": "bob", "password": "Secret123!", "email": "b@x.test"})
            session.commit()
        with Session(engine) as session:
            rows = session.execute(sa.select(UserAccount.username, UserAccount.deleted, UserAccount.is_admin)
                                   .order_by(UserAccount.uid)).all()
            assert [(r.deleted, r.is_admin) for r in rows if r.username == "alice"] == [(False, True)]
            assert sum(1 for r in rows if r.deleted) == 1 and len(rows) == 3
    finally:
        engine.dispose()
