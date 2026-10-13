"""B track, group 3d-2: UserTOTP on a Session and on the legacy engine."""

from __future__ import annotations

from unittest.mock import patch

import alembic.command
import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable


def test_model_maps_the_table():
    from namifax.models import UserTOTP

    t = UserTOTP.__table__
    assert t.name == "UserTOTP" and [c.name for c in t.primary_key.columns] == ["uid"]
    assert set(t.c.keys()) == {"uid", "secret_key", "is_enabled", "backup_codes", "created_at",
                               "failed_attempts", "locked_until"}
    assert not t.c.secret_key.nullable
    for d in (sqlite.dialect(), mysql.dialect(), postgresql.dialect()):
        assert "PRIMARY KEY (uid)" in str(CreateTable(t).compile(dialect=d))


@pytest.fixture(params=["session", "engine"])
def svc(request, dbsession, seeded_db):
    from namifax.services.totp import TotpService

    return TotpService(dbsession if request.param == "session" else seeded_db)


def _enable(svc, uid=1):
    secret = svc.generate_secret()
    with patch.object(svc, "verify_code", return_value=True):
        return secret, svc.enable_totp(uid, secret, "123456")


def test_disabled_by_default_and_enable_gives_eight_codes(svc):
    assert svc.is_totp_enabled(1) is False
    assert svc.verify_user_login(1, "anything") is True          # no 2FA configured
    _, res = _enable(svc)
    assert res["success"] and len(res["backup_codes"]) == 8
    assert svc.is_totp_enabled(1) is True and svc.is_totp_enabled(2) is False


def test_invalid_code_does_not_enable(svc):
    assert svc.enable_totp(1, svc.generate_secret(), "000000")["success"] is False
    assert svc.is_totp_enabled(1) is False


def test_enabling_again_replaces_the_configuration(svc):
    _enable(svc)
    _, res = _enable(svc)
    assert res["success"] and svc.is_totp_enabled(1)


def test_backup_code_is_single_use_and_wrong_code_fails(svc):
    _, res = _enable(svc)
    code = res["backup_codes"][0]
    assert svc.verify_user_login(1, "NOPE0000") is False
    assert svc.verify_user_login(1, code.lower()) is True
    assert svc.verify_user_login(1, code) is False                # already used
    assert svc.verify_user_login(1, res["backup_codes"][1]) is True


def test_the_current_totp_code_logs_in(svc):
    import pyotp

    secret, _ = _enable(svc)
    assert svc.verify_user_login(1, pyotp.TOTP(secret).now()) is True


def test_disable_removes_the_configuration(svc):
    _enable(svc)
    assert svc.disable_totp(1) is True
    assert svc.is_totp_enabled(1) is False and svc.verify_user_login(1, "x") is True


@pytest.mark.serverdb
def test_server_database(monkeypatch, server_db_url, alembic_cfg):
    from namifax.models import UserTOTP
    from namifax.services.totp import TotpService

    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(server_db_url)
    try:
        with Session(engine) as s:
            t = TotpService(s)
            _, res = _enable(t, 7)
            assert t.is_totp_enabled(7) and t.verify_user_login(7, res["backup_codes"][0])
            assert not t.verify_user_login(7, res["backup_codes"][0])
            s.commit()
        with Session(engine) as s:
            assert s.execute(sa.select(sa.func.count()).select_from(UserTOTP)).scalar() == 1
            assert TotpService(s).disable_totp(7)
    finally:
        engine.dispose()
