"""Password hashing: Argon2id for everything the application writes, MD5 (the original's format) still accepted.

An account made by the original AvantFAX keeps its MD5 hash until its owner logs in; that login stores an Argon2id hash instead
(``needs_rehash``). ``NAMIFAX_PASSWORD_HASH=md5`` keeps writing the original's format, for the time when the original program and this
one share a database (the original cannot read Argon2).
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


def _hasher() -> PasswordHasher:
    """Argon2id with the library's defaults (RFC 9106 low-memory profile); the costs can be tuned for the machine."""
    kwargs = {}
    for env, key in (("NAMIFAX_ARGON2_TIME_COST", "time_cost"), ("NAMIFAX_ARGON2_MEMORY_COST", "memory_cost"),
                     ("NAMIFAX_ARGON2_PARALLELISM", "parallelism")):
        value = os.environ.get(env, "")
        if value.isdecimal() and int(value) > 0:
            kwargs[key] = int(value)
    return PasswordHasher(**kwargs)


def md5_hex(password: str) -> str:
    return hashlib.md5(str(password).encode("utf-8")).hexdigest()


def legacy_mode() -> bool:
    return os.environ.get("NAMIFAX_PASSWORD_HASH", "argon2").strip().lower() == "md5"


def _is_md5(stored: str) -> bool:
    return len(stored) == 32 and all(c in "0123456789abcdefABCDEF" for c in stored)


def hash_password(password: str) -> str:
    return md5_hex(password) if legacy_mode() else _hasher().hash(str(password))


def verify_password(stored: Optional[str], password: str) -> bool:
    """Does ``password`` match the stored hash (Argon2id, or the original's MD5)? Never raises."""
    if not stored or not isinstance(stored, str):
        return False
    if _is_md5(stored):
        return hmac.compare_digest(md5_hex(password), stored.lower())
    if stored.startswith("$argon2"):
        try:
            return _hasher().verify(stored, str(password))
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False
    return False


def needs_rehash(stored: Optional[str]) -> bool:
    """Should this (already verified) hash be replaced by a fresh one?"""
    if not stored:
        return False
    if _is_md5(stored):
        return not legacy_mode()
    if legacy_mode():
        return False
    try:
        return _hasher().check_needs_rehash(stored)
    except InvalidHashError:
        return False
