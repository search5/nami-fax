"""Credentials the application has to read back (cloud secret key, SMTP password, TOTP seeds) are encrypted at rest."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import sqlalchemy as sa

from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv("NAMIFAX_SECRET_KEY", Fernet.generate_key().decode())


def _new_key():
    return Fernet.generate_key().decode()


# --- the box --------------------------------------------------------------------------------------------------

def test_round_trip_and_marker():
    from namifax.common.secretbox import decrypt, encrypt, is_encrypted

    token = encrypt("s3cr3t-Pa$$ word 한글")
    assert token.startswith("enc:v1:") and "s3cr3t" not in token and is_encrypted(token)
    assert decrypt(token) == "s3cr3t-Pa$$ word 한글"
    assert encrypt("same") != encrypt("same")                       # a fresh IV every time


def test_empty_values_stay_empty():
    from namifax.common.secretbox import decrypt, encrypt

    assert encrypt("") == "" and encrypt(None) == "" and decrypt("") == "" and decrypt(None) == ""


def test_old_plaintext_values_are_still_readable():
    from namifax.common.secretbox import decrypt, is_encrypted

    assert decrypt("plain-old-value") == "plain-old-value" and not is_encrypted("plain-old-value")


def test_the_wrong_key_fails_instead_of_returning_garbage(monkeypatch):
    from namifax.common.secretbox import SecretDecryptError, decrypt, encrypt

    token = encrypt("x")
    monkeypatch.setenv("NAMIFAX_SECRET_KEY", _new_key())
    with pytest.raises(SecretDecryptError):
        decrypt(token)


def test_a_tampered_value_is_rejected():
    from namifax.common.secretbox import SecretDecryptError, decrypt, encrypt

    token = encrypt("hello")
    with pytest.raises(SecretDecryptError):
        decrypt(token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB"))


def test_key_rotation_new_key_first_old_key_still_reads(monkeypatch):
    from namifax.common.secretbox import decrypt, encrypt

    old = _new_key()
    monkeypatch.setenv("NAMIFAX_SECRET_KEY", old)
    token = encrypt("rotating")
    new = _new_key()
    monkeypatch.setenv("NAMIFAX_SECRET_KEY", f"{new},{old}")
    assert decrypt(token) == "rotating"
    newer = encrypt("rotating")
    monkeypatch.setenv("NAMIFAX_SECRET_KEY", new)                   # the old key can be dropped once re-encrypted
    assert decrypt(newer) == "rotating"


def test_any_long_passphrase_works_and_short_ones_do_not(monkeypatch):
    from namifax.common.secretbox import SecretKeyError, decrypt, encrypt

    monkeypatch.setenv("NAMIFAX_SECRET_KEY", "a long passphrase that is not a fernet key")
    assert decrypt(encrypt("x")) == "x"
    monkeypatch.setenv("NAMIFAX_SECRET_KEY", "short")
    with pytest.raises(SecretKeyError):
        encrypt("x")


def test_without_a_key_nothing_is_written_in_the_clear(monkeypatch):
    from namifax.common.secretbox import SecretKeyError, decrypt, encrypt

    token = encrypt("x")
    monkeypatch.delenv("NAMIFAX_SECRET_KEY")
    with pytest.raises(SecretKeyError, match="NAMIFAX_SECRET_KEY"):
        encrypt("x")
    with pytest.raises(SecretKeyError):
        decrypt(token)
    assert decrypt("legacy plaintext") == "legacy plaintext"        # reading old rows needs no key


def test_the_key_can_come_from_the_ini_settings(monkeypatch):
    from namifax.common.secretbox import decrypt, encrypt, set_default_key

    monkeypatch.delenv("NAMIFAX_SECRET_KEY")
    set_default_key("an ini file passphrase that is long enough")
    try:
        assert decrypt(encrypt("v")) == "v"
    finally:
        set_default_key(None)


# --- SystemConfig ----------------------------------------------------------------------------------------------

def test_system_config_secrets(dbsession):
    from namifax.models import SystemConfig
    from namifax.services.system_config import SystemConfigService

    cfg = SystemConfigService(dbsession)
    cfg.set_secret("cloud_secret_key", "top-secret")
    raw = dbsession.get(SystemConfig, "cloud_secret_key").value
    assert "top-secret" not in raw and raw.startswith("enc:v1:")
    assert cfg.get_secret("cloud_secret_key") == "top-secret" and cfg.get_secret("missing", "dflt") == "dflt"

    dbsession.merge(SystemConfig(key="old", value="legacy-plain"))
    dbsession.flush()
    assert cfg.get_secret("old") == "legacy-plain"                  # a value saved before encryption existed


# --- SMTP password ------------------------------------------------------------------------------------------------

def test_smtp_password_is_encrypted_and_used_in_the_clear(dbsession):
    from namifax.models import SystemSettings
    from namifax.services.smtp_settings import SmtpSettingsService

    svc = SmtpSettingsService(dbsession)
    svc.save_settings({"smtp_host": "mail.example.test", "smtp_port": 587, "smtp_security": "TLS", "smtp_auth": True,
              "smtp_username": "mailer", "smtp_password": "m41l-p4ss", "from_email": "fax@example.test"})
    row = dbsession.get(SystemSettings, SmtpSettingsService.ROW_ID)
    assert "m41l-p4ss" not in row.smtp_password and row.smtp_password.startswith("enc:v1:")
    config = svc.get_settings()
    assert config.smtp_password == "m41l-p4ss" and config.smtp_username == "mailer"

    row.smtp_password = "legacy-plain"                              # saved before encryption existed
    dbsession.flush()
    assert svc.get_settings().smtp_password == "legacy-plain"


def test_a_long_smtp_password_still_fits_the_column():
    from namifax.models import SystemSettings

    assert SystemSettings.__table__.c.smtp_password.type.length >= 512


# --- TOTP seeds ----------------------------------------------------------------------------------------------------

def test_totp_seed_is_encrypted_and_still_verifies(dbsession):
    import pyotp

    from namifax.models import UserTOTP
    from namifax.services.totp import TotpService

    svc = TotpService(dbsession)
    seed = svc.generate_secret()
    assert svc.enable_totp(1, seed, pyotp.TOTP(seed).now())["success"]
    stored = dbsession.get(UserTOTP, 1).secret_key
    assert seed not in stored and stored.startswith("enc:v1:")
    assert svc.verify_user_login(1, pyotp.TOTP(seed).now()) is True


def test_a_totp_seed_stored_before_encryption_still_works(dbsession):
    import pyotp

    from namifax.models import UserTOTP
    from namifax.services.totp import TotpService

    seed = pyotp.random_base32()
    dbsession.add(UserTOTP(uid=3, secret_key=seed, is_enabled=True, backup_codes=""))
    dbsession.flush()
    assert TotpService(dbsession).verify_user_login(3, pyotp.TOTP(seed).now()) is True


def test_a_seed_that_cannot_be_decrypted_locks_the_user_out_safely(dbsession, monkeypatch):
    import pyotp

    from namifax.services.totp import TotpService

    svc = TotpService(dbsession)
    seed = svc.generate_secret()
    svc.enable_totp(1, seed, pyotp.TOTP(seed).now())
    monkeypatch.setenv("NAMIFAX_SECRET_KEY", _new_key())
    assert svc.verify_user_login(1, pyotp.TOTP(seed).now()) is False        # fails closed, no exception


# --- admin storage page --------------------------------------------------------------------------------------------

def test_the_storage_page_encrypts_the_cloud_secret_and_uses_it(testapp, dbsession):
    from namifax.models import SystemConfig

    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    page = testapp.post("/admin/storage", {"action": "save_cloud", "storage_type": "S3", "bucket_name": "b",
                                           "access_key": "AKIA", "secret_key": "cloud-secret", "region_name": "r"})
    assert page.status_int == 200
    raw = dbsession.get(SystemConfig, "cloud_secret_key").value
    assert "cloud-secret" not in raw and raw.startswith("enc:v1:")
    assert "cloud-secret" not in page.text

    seen = {}

    class FakeProvider:
        def test_connection(self):
            return {"success": True, "message": "ok"}

    def fake_get_provider(cfg):
        seen["secret"] = cfg.secret_key
        return FakeProvider()

    with patch("namifax.services.cloud_storage.CloudStorageManager.get_provider", side_effect=fake_get_provider):
        testapp.post("/admin/storage", {"action": "test_cloud", "storage_type": "S3", "bucket_name": "b"})
    assert seen["secret"] == "cloud-secret"                          # decrypted when it is actually used


def test_the_storage_page_refuses_to_store_a_secret_without_a_key(testapp, dbsession, monkeypatch):
    from namifax.models import SystemConfig

    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    monkeypatch.delenv("NAMIFAX_SECRET_KEY")
    page = testapp.post("/admin/storage", {"action": "save_cloud", "storage_type": "S3", "secret_key": "nope"})
    assert "NAMIFAX_SECRET_KEY" in page.text
    assert dbsession.get(SystemConfig, "cloud_secret_key") is None


def test_the_saved_policy_run_reads_the_encrypted_cloud_secret(dbsession, tmp_path):
    from namifax.services.storage_lifecycle import StorageLifecycleService
    from namifax.services.system_config import SystemConfigService

    cfg = SystemConfigService(dbsession)
    cfg.set("cloud_storage_type", "S3")
    cfg.set_secret("cloud_secret_key", "cloud-secret")
    cfg.set("storage_purge_tiff_days", "7")
    cfg.set("storage_retention_days", "365")
    svc = StorageLifecycleService(db=dbsession, archive_dir=str(tmp_path))
    with patch("namifax.services.cloud_storage.CloudStorageManager.get_provider") as get_provider:
        svc.run_saved_policy()
    assert get_provider.call_args.args[0].secret_key == "cloud-secret"


# --- converting what is already stored ---------------------------------------------------------------------------

def test_encrypt_secrets_command_converts_plaintext_once(tmp_path, monkeypatch):
    from sqlalchemy.orm import Session

    from namifax.cli.encrypt_secrets import run_encrypt_secrets
    from namifax.db.bootstrap import ensure_schema
    from namifax.db.provider import create_sa_engine
    from namifax.models import SystemConfig, SystemSettings, UserTOTP

    url = f"sqlite:///{tmp_path / 'e.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_sa_engine(url)
    ensure_schema(engine)
    with Session(engine) as s:
        s.merge(SystemConfig(key="cloud_secret_key", value="plain-cloud"))
        s.add(SystemSettings(id=1, smtp_host="h", smtp_password="plain-smtp"))
        s.add(UserTOTP(uid=5, secret_key="PLAINSEED", is_enabled=True))
        s.commit()

    assert run_encrypt_secrets([]) == 0
    assert run_encrypt_secrets([]) == 0                              # idempotent
    with Session(engine) as s:
        values = [s.get(SystemConfig, "cloud_secret_key").value, s.get(SystemSettings, 1).smtp_password,
                  s.get(UserTOTP, 5).secret_key]
    assert all(v.startswith("enc:v1:") for v in values)
    from namifax.common.secretbox import decrypt

    assert [decrypt(v) for v in values] == ["plain-cloud", "plain-smtp", "PLAINSEED"]
    engine.dispose()


def test_encrypt_secrets_needs_a_key(monkeypatch, capsys):
    from namifax.cli.encrypt_secrets import run_encrypt_secrets

    monkeypatch.delenv("NAMIFAX_SECRET_KEY")
    assert run_encrypt_secrets([]) == 1
    assert "NAMIFAX_SECRET_KEY" in capsys.readouterr().out
