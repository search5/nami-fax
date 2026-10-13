"""Database provisioning (spec 48).

The SQLAlchemy engine is created once at start-up from the settings; requests and commands get
sessions from it. There is no process-wide singleton.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool



def resolve_database_url(settings: Mapping[str, Any] | None, environ: Mapping[str, str]) -> str:
    """Resolve DB URL: settings > DATABASE_URL > AFDB_URL > NAMIFAX_DB_PATH/cwd sqlite file."""
    if settings and settings.get("sqlalchemy.url"):
        return str(settings["sqlalchemy.url"])
    for key in ("DATABASE_URL", "AFDB_URL"):
        if environ.get(key):
            return environ[key]
    db_path = environ.get("NAMIFAX_DB_PATH") or os.path.join(os.getcwd(), "namifax.db")
    return f"sqlite:///{db_path}"


def create_sa_engine(url: str) -> Engine:
    """Create the SQLAlchemy engine; in-memory SQLite shares one DB across connections."""
    if url.startswith("sqlite"):
        kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
        return create_engine(url, **kwargs)
    return create_engine(url, pool_pre_ping=True)


# The session of the command-line run in progress, so helpers such as avantfaxlog() and send_mail()
# reuse its connection: a second writing connection would be locked out by the run's pending writes.
_ACTIVE_SESSION: ContextVar[Optional[Session]] = ContextVar("namifax_active_session", default=None)


def active_session() -> Optional[Session]:
    """Session of the ``cli_session()`` block currently running, if any."""
    return _ACTIVE_SESSION.get()


@contextmanager
def use_session(session: Session) -> Iterator[Session]:
    """Make an already open session the active one for the block (``cli_session`` does this for its own)."""
    token = _ACTIVE_SESSION.set(session)
    try:
        yield session
    finally:
        _ACTIVE_SESSION.reset(token)


@contextmanager
def cli_session(
    settings: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    ensure_schema: bool = False,
) -> Iterator[Session]:
    """Open an ORM session for a command-line entry point (no request object).

    Uses the same URL resolution as the web app. The session is committed when the block ends
    normally, rolled back on error, and the engine pool is released either way.

    ``ensure_schema=True`` brings the schema up to date first (see ``namifax.db.bootstrap``).
    """
    engine = create_sa_engine(resolve_database_url(settings, os.environ if environ is None else environ))
    if ensure_schema:
        from namifax.db.bootstrap import ensure_schema as bootstrap

        bootstrap(engine)
    session = Session(engine, expire_on_commit=False)
    token = _ACTIVE_SESSION.set(session)
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        _ACTIVE_SESSION.reset(token)
        session.close()
        engine.dispose()
