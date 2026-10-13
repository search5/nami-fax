"""Kept for the tests that were written for a legacy engine and a session over one database.

Both are the same ``SqlSession`` now: one object, one connection, one set of data.
"""

from __future__ import annotations

from sqlsession import seeded_session


def linked_db():
    """Return ``(db, session)``; both names refer to the same session."""
    session = seeded_session()
    return session, session


def close_linked(db, session) -> None:
    session.disconnect()
