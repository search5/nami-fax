"""Recovery codes are stored hashed: a copy of the database must not reveal working codes."""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest

from namifax.services.totp import TotpService


@pytest.fixture
def svc(dbsession):
    return TotpService(dbsession)


def _enable(svc, uid=1):
    with patch.object(svc, "verify_code", return_value=True):
        return svc.enable_totp(uid, svc.generate_secret(), "123456")["backup_codes"]


def _stored(svc, uid=1):
    return svc._row(uid)["backup_codes"]


def test_codes_are_long_enough_and_readable(svc):
    codes = _enable(svc)
    assert len(codes) == 8 and len(set(codes)) == 8
    assert all(re.fullmatch(r"[A-Z2-9]{5}-[A-Z2-9]{5}", c) for c in codes)       # ~49 bits each, no 0/O/1/I confusion
    assert not any(ch in "".join(codes) for ch in "01OIL")


def test_the_database_holds_only_salted_hashes(svc):
    codes = _enable(svc)
    stored = _stored(svc)
    for code in codes:
        assert code not in stored and code.replace("-", "") not in stored
    entries = stored.split(",")
    assert len(entries) == 8 and all(e.startswith("scrypt$") for e in entries)
    assert len({e.split("$")[1] for e in entries}) == 8                           # a different salt for each


def test_a_code_works_once_however_it_is_typed(svc):
    codes = _enable(svc)
    code = codes[0]
    assert svc.verify_user_login(1, code.lower().replace("-", " ")) is True
    assert svc.verify_user_login(1, code) is False                                 # used
    assert svc.backup_codes_remaining(1) == 7
    assert svc.verify_user_login(1, codes[1]) is True and svc.backup_codes_remaining(1) == 6


def test_a_wrong_code_removes_nothing(svc):
    _enable(svc)
    assert svc.verify_user_login(1, "AAAAA-AAAAA") is False
    assert svc.backup_codes_remaining(1) == 8


def test_codes_saved_before_hashing_still_work_once(svc):
    """A 2FA enrolment made by an older version holds plaintext 8-hex codes."""
    _enable(svc)
    svc._rows(1).update_where({"uid": 1}, {"backup_codes": "DEADBEEF,0BADF00D"})
    assert svc.backup_codes_remaining(1) == 2
    assert svc.verify_user_login(1, "deadbeef") is True
    assert svc.verify_user_login(1, "DEADBEEF") is False and svc.backup_codes_remaining(1) == 1


def test_regenerating_replaces_every_code(svc):
    old = _enable(svc)
    new = svc.regenerate_backup_codes(1)
    assert len(new) == 8 and not set(new) & set(old)
    assert svc.verify_user_login(1, old[0]) is False
    assert svc.verify_user_login(1, new[0]) is True


def test_no_codes_for_a_user_without_2fa(svc):
    assert svc.backup_codes_remaining(9) == 0 and svc.regenerate_backup_codes(9) == []


def test_hash_helper_round_trip():
    from namifax.services.totp import hash_recovery_code, recovery_code_matches

    h = hash_recovery_code("ABCDE-FGHJK")
    assert h.startswith("scrypt$") and recovery_code_matches(h, "abcde fghjk") and not recovery_code_matches(h, "ABCDE-FGHJL")
    assert hash_recovery_code("ABCDE-FGHJK") != h                                   # salted
    assert recovery_code_matches("DEADBEEF", "deadbeef") and not recovery_code_matches("DEADBEEF", "deadbeee")


def test_encrypt_secrets_also_hashes_old_plaintext_codes(tmp_path, monkeypatch):
    from sqlalchemy.orm import Session

    from namifax.cli.encrypt_secrets import run_encrypt_secrets
    from namifax.db.bootstrap import ensure_schema
    from namifax.db.provider import create_sa_engine
    from namifax.models import UserTOTP

    url = f"sqlite:///{tmp_path / 'c.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_sa_engine(url)
    ensure_schema(engine)
    with Session(engine) as s:
        s.add(UserTOTP(uid=5, secret_key="PLAINSEED", is_enabled=True, backup_codes="DEADBEEF,0BADF00D"))
        s.commit()
    assert run_encrypt_secrets([]) == 0
    assert run_encrypt_secrets([]) == 0
    with Session(engine) as s:
        stored = s.get(UserTOTP, 5).backup_codes
        assert "DEADBEEF" not in stored and stored.count("scrypt$") == 2
        assert TotpService(s).backup_codes_remaining(5) == 2
    engine.dispose()
