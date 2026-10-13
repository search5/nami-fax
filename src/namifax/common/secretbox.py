"""Encryption at rest for credentials the application must be able to read back.

Used for the cloud storage secret key, the SMTP password and the TOTP seeds. (Login passwords are hashed,
not encrypted: nothing needs to read those back.)

* The key comes from ``NAMIFAX_SECRET_KEY`` or the ``secret.key`` ini setting. Either a Fernet key
  (``python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"``) or any
  passphrase of at least 16 characters. Several keys separated by commas allow rotation: the first
  encrypts, every one decrypts.
* Stored values look like ``enc:v1:<token>``. A value without that marker is an old plaintext value: it is
  still read as it is and becomes encrypted the next time it is saved (``namifax encrypt-secrets`` converts
  everything at once).
* Without a key nothing is written in the clear: ``encrypt`` raises ``SecretKeyError``. The wrong key or a
  damaged value raises ``SecretDecryptError``; callers treat that as "secret unavailable", never as garbage.
"""

from __future__ import annotations

import base64
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

PREFIX = "enc:v1:"
MIN_PASSPHRASE = 16
_ENV = "NAMIFAX_SECRET_KEY"
_default_key: Optional[str] = None


class SecretKeyError(RuntimeError):
    """No usable key is configured."""


class SecretDecryptError(RuntimeError):
    """The stored value cannot be decrypted (wrong key or damaged data)."""


def set_default_key(key: Optional[str]) -> None:
    """Key from the ini file; the environment variable takes precedence."""
    global _default_key
    _default_key = key or None


def _one(key: str) -> Fernet:
    key = key.strip()
    try:
        if len(key) == 44 and len(base64.urlsafe_b64decode(key)) == 32:
            return Fernet(key.encode())
    except ValueError:
        pass
    if len(key) < MIN_PASSPHRASE:
        raise SecretKeyError(
            f"{_ENV} must be a Fernet key or a passphrase of at least {MIN_PASSPHRASE} characters")
    derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"namifax-secretbox-v1", info=b"fernet").derive(
        key.encode("utf-8"))
    return Fernet(base64.urlsafe_b64encode(derived))


def _box() -> MultiFernet:
    raw = os.environ.get(_ENV) or _default_key
    keys = [k for k in (raw or "").split(",") if k.strip()]
    if not keys:
        raise SecretKeyError(f"No encryption key configured: set {_ENV} (or secret.key in the ini file)")
    return MultiFernet([_one(k) for k in keys])


def is_encrypted(value: Optional[str]) -> bool:
    return bool(value) and str(value).startswith(PREFIX)


def encrypt(value: Optional[str]) -> str:
    """Encrypt ``value`` (empty stays empty)."""
    if not value:
        return ""
    return PREFIX + _box().encrypt(str(value).encode("utf-8")).decode("ascii")


def decrypt(value: Optional[str]) -> str:
    """Plain text for a stored value; old plaintext is returned unchanged."""
    if not value:
        return ""
    value = str(value)
    if not value.startswith(PREFIX):
        return value
    try:
        return _box().decrypt(value[len(PREFIX):].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError) as exc:
        raise SecretDecryptError("The stored secret cannot be decrypted with the configured key") from exc
