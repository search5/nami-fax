"""Passwords are stored as Argon2id. Accounts made by the original (MD5) still log in, and are upgraded to Argon2id on that login;
NAMIFAX_PASSWORD_HASH=md5 keeps the original's format for a time when both programs share the database."""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import select, update

from namifax.common import passwords
from namifax.models import UserAccount, UserPasswords
from namifax.services.user_account import NFUserAccount

PW = "Correct-horse-9"


def _md5(text):
    return hashlib.md5(text.encode()).hexdigest()


def _row(session, username):
    session.expire_all()
    return session.execute(select(UserAccount).where(UserAccount.username == username)).scalar_one()


def _make(session, username="argo", password=PW, **extra):
    svc = NFUserAccount(db=session)
    assert svc.create({"username": username, "password": password, "email": f"{username}@x.test", "name": "A", "acc_enabled": 1,
                       "last_login": "2026-01-01 10:00:00", **extra})
    session.flush()
    return svc


# --- the hash itself --------------------------------------------------------------------------------------------------------

def test_new_hashes_are_argon2id_with_their_own_salt():
    a, b = passwords.hash_password(PW), passwords.hash_password(PW)
    assert a.startswith("$argon2id$") and a != b
    assert passwords.verify_password(a, PW) and not passwords.verify_password(a, PW + "x")


def test_the_originals_md5_still_verifies():
    stored = _md5(PW)
    assert passwords.verify_password(stored, PW) and not passwords.verify_password(stored, "other")
    assert passwords.verify_password(stored.upper(), PW)


def test_nothing_verifies_against_junk():
    for stored in ("", None, "x", "$argon2id$broken"):
        assert passwords.verify_password(stored, PW) is False


def test_only_old_formats_need_an_upgrade():
    assert passwords.needs_rehash(_md5(PW)) is True
    assert passwords.needs_rehash(passwords.hash_password(PW)) is False


def test_md5_mode_keeps_the_originals_format(monkeypatch):
    monkeypatch.setenv("NAMIFAX_PASSWORD_HASH", "md5")
    assert passwords.hash_password(PW) == _md5(PW)
    assert passwords.needs_rehash(_md5(PW)) is False


# --- the account ------------------------------------------------------------------------------------------------------------

def test_a_new_account_is_stored_as_argon2id_and_can_log_in(dbsession):
    _make(dbsession)
    assert _row(dbsession, "argo").password.startswith("$argon2id$")
    assert NFUserAccount(db=dbsession).login("argo", PW)
    assert not NFUserAccount(db=dbsession).login("argo", "wrong-password")


def test_an_md5_account_logs_in_and_is_upgraded(dbsession):
    _make(dbsession)
    dbsession.execute(update(UserAccount).where(UserAccount.username == "argo").values(password=_md5(PW)))
    dbsession.flush()
    assert NFUserAccount(db=dbsession).login("argo", PW)
    assert _row(dbsession, "argo").password.startswith("$argon2id$")
    assert NFUserAccount(db=dbsession).login("argo", PW)                      # and the upgraded hash works


def test_a_wrong_password_does_not_upgrade_anything(dbsession):
    _make(dbsession)
    dbsession.execute(update(UserAccount).where(UserAccount.username == "argo").values(password=_md5(PW)))
    dbsession.flush()
    assert not NFUserAccount(db=dbsession).login("argo", "nope-nope-1")
    assert _row(dbsession, "argo").password == _md5(PW)


def test_in_md5_mode_nothing_is_upgraded(dbsession, monkeypatch):
    monkeypatch.setenv("NAMIFAX_PASSWORD_HASH", "md5")
    _make(dbsession)
    assert _row(dbsession, "argo").password == _md5(PW)
    assert NFUserAccount(db=dbsession).login("argo", PW)
    assert _row(dbsession, "argo").password == _md5(PW)


def test_the_admin_login_still_requires_the_admin_flag(dbsession):
    _make(dbsession, "plain")
    _make(dbsession, "boss", is_admin=1)
    assert not NFUserAccount(db=dbsession).login("plain", PW, admin=True)
    assert NFUserAccount(db=dbsession).login("boss", PW, admin=True)


def test_changing_the_password_stores_argon2id(dbsession):
    svc = _make(dbsession)
    assert svc.change_password("Another-pass-7")
    assert _row(dbsession, "argo").password.startswith("$argon2id$")
    assert NFUserAccount(db=dbsession).login("argo", "Another-pass-7")


def test_the_old_password_is_checked_against_either_format(dbsession):
    svc = _make(dbsession)
    assert svc.set_newpassword(PW, "Second-pass-8")
    svc2 = NFUserAccount(db=dbsession)
    assert svc2.load_username("argo") and not svc2.set_newpassword("wrong-old-1", "Third-pass-9")
    dbsession.execute(update(UserAccount).where(UserAccount.username == "argo").values(password=_md5("Second-pass-8")))
    dbsession.flush()
    svc3 = NFUserAccount(db=dbsession)
    assert svc3.load_username("argo") and svc3.set_newpassword("Second-pass-8", "Fourth-pass-1")


def test_a_reset_password_works_for_login(dbsession):
    _make(dbsession)
    ok, new = NFUserAccount(db=dbsession).reset_password("argo@x.test")
    assert ok and NFUserAccount(db=dbsession).login("argo", new)
    assert _row(dbsession, "argo").password.startswith("$argon2id$")


def test_a_generated_password_works_for_login(dbsession):
    svc = _make(dbsession, "gen", password="")
    assert NFUserAccount(db=dbsession).login("gen", svc.generated_password)


# --- the history that blocks reuse ------------------------------------------------------------------------------------------

def test_a_used_password_is_refused_again_whatever_its_stored_format(dbsession):
    svc = _make(dbsession)
    uid = svc.uid
    from namifax.services.user_passwords import NFUserPasswords

    history = NFUserPasswords(db=dbsession)
    dbsession.add(UserPasswords(uid=uid, pwdhash=_md5("Old-legacy-pass-3")))           # a row the original wrote
    dbsession.flush()
    assert history.password_used("Old-legacy-pass-3", uid) and history.password_used(PW, uid)
    assert not history.password_used("Never-used-pass-5", uid)


def test_the_history_holds_argon2id_hashes(dbsession):
    svc = _make(dbsession)
    stored = dbsession.execute(select(UserPasswords.pwdhash).where(UserPasswords.uid == svc.uid)).scalars().all()
    assert stored and all(h.startswith("$argon2id$") for h in stored)


def test_the_columns_are_wide_enough_for_an_argon2id_hash():
    assert UserAccount.__table__.c.password.type.length >= 128 and UserPasswords.__table__.c.pwdhash.type.length >= 128
