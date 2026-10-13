"""Test support: a real ORM ``Session`` that also understands the raw-SQL conveniences older tests use.

The application talks to the database only through SQLAlchemy sessions. Many tests, however, set up or check
data with a line of SQL (``db.query("INSERT ...")``, ``db.get_records()``). ``SqlSession`` is an ordinary
``Session`` plus those helpers, so such a test can pass the same object to a service, to ``SELECT`` through, or to
``INSERT`` into.

``query`` shadows the SQLAlchemy 1.x ``Session.query`` (the Query API), which nothing here uses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import sqlalchemy as sa

_SELECT = re.compile(r"^\s*(SELECT|WITH|PRAGMA)\b", re.IGNORECASE)


@dataclass
class QueryResult:
    executed: bool
    row_count: int = 0
    affected_rows: int = 0


class SqlSession(Session):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("expire_on_commit", False)
        super().__init__(*args, **kwargs)
        self._records: list[dict[str, Any]] = []
        self._error: str | None = None
        self._insert_id: int | None = None
        self._affected = 0
        self._iter: Any = None
        self.owned_engine: sa.Engine | None = None

    # --- raw SQL ---------------------------------------------------------------------------------------------
    def query(self, sql: str, params: Sequence[Any] | dict[str, Any] | None = None, fetch_type: int = 1) -> QueryResult:  # type: ignore[override]
        self._records, self._error, self._iter = [], None, None
        bind: dict[str, Any] = {}
        if isinstance(params, dict):
            bind = dict(params)
        elif params:
            parts = sql.split("?")
            sql = "".join(f"{part}:p{i}" if i < len(parts) - 1 else part for i, part in enumerate(parts))
            bind = {f"p{i}": v for i, v in enumerate(params)}
        try:
            result = self.execute(text(sql), bind)
            if _SELECT.match(sql) and result.returns_rows:
                self._records = [dict(r._mapping) for r in result]
                self._affected = 0
                return QueryResult(True, row_count=len(self._records))
            self._affected = result.rowcount
            self._insert_id = getattr(result, "lastrowid", None)
            return QueryResult(True, affected_rows=self._affected)
        except Exception as exc:                    # the legacy engine reported errors instead of raising
            self._error = str(exc)
            self.rollback() if not self.in_transaction() else None
            return QueryResult(False)

    def get_records(self) -> list[dict[str, Any]]:
        return self._records

    def get_result(self) -> dict[str, Any] | bool:
        if self._iter is None:
            self._iter = iter(self._records)
        return next(self._iter, False)

    def get_insert_id(self) -> int | None:
        return self._insert_id

    def get_error(self) -> str | None:
        return self._error

    @property
    def affected_rows(self) -> int:
        return self._affected

    def quote(self, value: Any) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "1" if value else "0"
        return "'" + str(value).replace("'", "''") + "'"

    def upgrade_schema(self) -> None:
        """Run the application's start-up schema step on this session's database (creates or upgrades tables)."""
        from namifax.db.bootstrap import ensure_schema

        self.commit()
        assert self.owned_engine is not None
        ensure_schema(self.owned_engine)

    # --- life cycle ---------------------------------------------------------------------------------------------
    def disconnect(self) -> None:
        self.close()
        if self.owned_engine is not None:
            self.owned_engine.dispose()
            self.owned_engine = None


def memory_engine() -> sa.Engine:
    """One shared in-memory SQLite database (every connection sees the same data)."""
    return sa.create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def seeded_session(seed: bool = True) -> SqlSession:
    """A ``SqlSession`` on a fresh in-memory database with the schema (and, by default, the demo data)."""
    from namifax.db.bootstrap import ensure_schema

    engine = memory_engine()
    if seed:
        ensure_schema(engine)
    session = SqlSession(engine)
    session.owned_engine = engine
    return session


def empty_session() -> SqlSession:
    """A ``SqlSession`` on a fresh in-memory database whose tables exist (from the models) but hold no rows."""
    import namifax.models  # noqa: F401  (registers every table)
    from namifax.models.meta import Base

    engine = memory_engine()
    Base.metadata.create_all(engine)
    session = SqlSession(engine)
    session.owned_engine = engine
    return session


def bare_session() -> SqlSession:
    """A ``SqlSession`` on a fresh in-memory database with no tables at all."""
    engine = memory_engine()
    session = SqlSession(engine)
    session.owned_engine = engine
    return session
