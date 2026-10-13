"""Read and write SystemConfig key/value settings through an ORM session."""

from __future__ import annotations

from typing import Callable

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from namifax.models.systemconfig import SystemConfig


class SystemConfigService:
    """Key/value settings backed by the ``SystemConfig`` table.

    A write is one atomic upsert statement of the database (``ON DUPLICATE KEY UPDATE`` on MySQL and MariaDB, ``ON CONFLICT`` on
    PostgreSQL and SQLite), so it is portable and values are bound parameters, never string-built SQL. Requests that overlap are
    safe: a key that another connection created first is not an error. (``Session.merge`` used to read first and then INSERT, which
    failed with a duplicate key when two connections created the key together, and on MySQL/MariaDB when this transaction had read
    before the other one committed. A savepoint and a retry are no cure on MySQL: locking a row that does not exist makes two
    requests wait for each other, and InnoDB ends one of the transactions.) A value that is changed from its old value (a counter)
    goes through ``locked_update``.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, key: str, default: str = "") -> str:
        row = self.session.get(SystemConfig, key)
        if row is None or row.value is None:
            return default
        return row.value

    def get_secret(self, key: str, default: str = "") -> str:
        """A value stored with ``set_secret`` (or, from before encryption existed, in plain text)."""
        from namifax.common.secretbox import decrypt

        stored = self.get(key, "")
        return decrypt(stored) if stored else default

    def set_secret(self, key: str, value: str) -> None:
        """Store ``value`` encrypted; raises ``SecretKeyError`` when no encryption key is configured."""
        from namifax.common.secretbox import encrypt

        self.set(key, encrypt(value))

    def _upsert(self, key: str, value: str, overwrite: bool) -> None:
        """Create the key with ``value``; when it exists, replace its value (``overwrite``) or leave it. One statement, no error."""
        table = SystemConfig.__table__
        dialect = self.session.get_bind().dialect.name
        # (aimed at the mapped class, not the table: that makes it an ORM statement, which the transaction manager of a request
        # sees as a change and commits; a statement on the bare table would be rolled back as "nothing changed")
        if dialect in ("mysql", "mariadb"):
            statement = mysql_insert(SystemConfig).values(key=key, value=value)
            # the existing row is written either way: that takes its lock, which is what ``locked_update`` relies on
            statement = statement.on_duplicate_key_update(value=statement.inserted.value if overwrite else table.c.value)
        elif dialect in ("postgresql", "sqlite"):
            statement = (postgresql_insert if dialect == "postgresql" else sqlite_insert)(SystemConfig).values(key=key, value=value)
            statement = (statement.on_conflict_do_update(index_elements=[table.c.key], set_={"value": statement.excluded.value})
                         if overwrite else statement.on_conflict_do_nothing(index_elements=[table.c.key]))
        else:                                                   # another database: the portable (and slower to settle) way
            if overwrite or self.session.get(SystemConfig, key) is None:
                self.session.merge(SystemConfig(key=key, value=value))
            return
        self.session.execute(statement)
        for cached in list(self.session.identity_map.values()):          # a row already loaded in this session is stale now
            if isinstance(cached, SystemConfig) and cached.key == key:
                self.session.expire(cached)

    def set(self, key: str, value: str) -> None:
        self._upsert(key, value, overwrite=True)
        self.session.flush()

    def lock(self, key: str) -> SystemConfig:
        """The row of ``key`` (made empty if it is missing), read with ``SELECT ... FOR UPDATE`` and fresh.

        It waits for a transaction that changes the key and then reads what that one committed. The lock is held until this
        transaction ends. Take the locks of several keys always in the same order, or two requests can wait for each other.
        (SQLite has no row lock; it has one writer at a time, and it is not a production database.)
        """
        self._upsert(key, "", overwrite=False)
        statement = select(SystemConfig).where(SystemConfig.key == key).with_for_update().execution_options(populate_existing=True)
        return self.session.execute(statement).scalar_one()

    def locked_update(self, key: str, change: Callable[[str], str]) -> str:
        """Store ``change(old value)`` (an empty string for a missing key) while no other transaction can change the key.

        Two requests that add one to a counter at the same moment give two, not one (see ``lock``).
        """
        row = self.lock(key)
        new = change(row.value or "")
        row.value = new
        self.session.flush()
        return new
