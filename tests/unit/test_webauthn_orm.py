"""B track, group 3d-2: UserWebAuthnCredentials stored through a Session (it never worked on SQLite)."""

from __future__ import annotations

import alembic.command
import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable


def test_model_maps_the_table():
    from namifax.models import UserWebAuthnCredentials

    t = UserWebAuthnCredentials.__table__
    assert t.name == "UserWebAuthnCredentials" and [c.name for c in t.primary_key.columns] == ["id"]
    assert set(t.c.keys()) == {"id", "uid", "credential_id", "public_key", "sign_count", "transports",
                               "device_name", "created_at", "last_used_at"}
    assert t.c.credential_id.unique is True and not t.c.public_key.nullable
    for d in (sqlite.dialect(), mysql.dialect(), postgresql.dialect()):
        assert "UNIQUE (credential_id)" in str(CreateTable(t).compile(dialect=d))


@pytest.fixture
def svc(dbsession):
    from namifax.services.webauthn import WebAuthnService

    return WebAuthnService(rp_id="fax.example.com", db=dbsession)


def _save(svc, uid=1, cid="cred-1", name="Key", **kw):
    return svc.save_credential(uid=uid, credential_id=cid, public_key="pk", device_name=name, **kw)


def test_save_returns_the_real_row_id_and_list_shows_it(svc):
    a = _save(svc, cid="a", name="Old", transports=["usb", "nfc"])
    b = _save(svc, cid="b", name="New")
    assert a.id and b.id and a.id != b.id and a.transports == "usb,nfc"
    listed = svc.list_credentials(1)
    assert [c.device_name for c in listed] == ["New", "Old"]            # newest first
    assert listed[1].transports == "usb,nfc" and listed[0].last_used_at is None
    assert svc.list_credentials(2) == []


def test_credential_ids_are_unique(svc):
    _save(svc, cid="dup")
    with pytest.raises(Exception):
        _save(svc, cid="dup", uid=2)


def test_get_and_update_sign_count(svc):
    _save(svc, cid="c1", sign_count=1)
    row = svc.get_credential_by_id("c1")
    assert row["uid"] == 1 and row["sign_count"] == 1 and row["public_key"] == "pk"
    assert svc.get_credential_by_id("missing") is None
    svc.update_sign_count("c1", 9)
    row = svc.get_credential_by_id("c1")
    assert row["sign_count"] == 9 and row["last_used_at"]


def test_delete_only_removes_the_owners_credential(svc):
    cred = _save(svc, uid=1, cid="mine")
    assert svc.delete_credential(uid=2, credential_db_id=cred.id) is True   # not theirs: nothing removed
    assert len(svc.list_credentials(1)) == 1
    assert svc.delete_credential(uid=1, credential_db_id=cred.id) is True
    assert svc.list_credentials(1) == []


def test_authentication_options_list_the_users_credentials(svc):
    from webauthn.helpers import bytes_to_base64url

    cid = bytes_to_base64url(b"test_credential_id_123")
    _save(svc, uid=1, cid=cid)
    _save(svc, uid=2, cid=bytes_to_base64url(b"other"))
    opts = svc.generate_authentication_options(user_id=1)
    assert [c["id"] for c in opts["allowCredentials"]] == [cid]
    assert "allowCredentials" not in svc.generate_authentication_options(user_id=99) or \
        svc.generate_authentication_options(user_id=99)["allowCredentials"] == []


@pytest.mark.serverdb
def test_server_database(monkeypatch, server_db_url, alembic_cfg):
    from namifax.models import UserWebAuthnCredentials
    from namifax.services.webauthn import WebAuthnService

    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(server_db_url)
    try:
        with Session(engine) as s:
            w = WebAuthnService(db=s)
            c = _save(w, cid="srv", name="한글 키")
            w.update_sign_count("srv", 3)
            assert w.list_credentials(1)[0].device_name == "한글 키" and w.get_credential_by_id("srv")["sign_count"] == 3
            assert w.delete_credential(1, c.id) and w.list_credentials(1) == []
            s.commit()
        with Session(engine) as s:
            assert s.execute(sa.select(sa.func.count()).select_from(UserWebAuthnCredentials)).scalar() == 0
    finally:
        engine.dispose()


def test_a_binary_credential_id_is_stored_as_base64url(svc):
    from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

    """A real authenticator's credential id is random bytes, not UTF-8 text (registration failed with a codec error)."""
    from types import SimpleNamespace
    from unittest.mock import patch

    raw = bytes([0x00, 0xFF, 0xFE, 0x80, 0x10, 0xC3, 0x28])
    fake = SimpleNamespace(credential_id=raw, credential_public_key=b"\x01\x02", sign_count=0)
    with patch("namifax.services.webauthn.webauthn.verify_registration_response", return_value=fake):
        result = svc.verify_registration_response({"id": "x"}, bytes_to_base64url(b"challenge"))
    assert result["credential_id"] == bytes_to_base64url(raw)
    assert base64url_to_bytes(result["credential_id"]) == raw


def test_registration_asks_for_a_discoverable_passkey(svc):
    """The login page signs in without a user name, so the browser must be able to list the passkey itself."""
    options = svc.generate_registration_options(user_id=1, user_name="admin")
    selection = options["authenticatorSelection"]
    assert selection["residentKey"] == "required" and selection["requireResidentKey"] is True
