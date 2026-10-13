"""The placeholder a service holds when it was built without a database session."""

from __future__ import annotations

from typing import Any


class MissingDatabase:
    """Bound when a service is built without a session (spec 48).

    Any attribute access raises, so a forgotten injection fails loudly on first use instead of
    silently doing nothing.
    """

    def __init__(self, owner: str = "service") -> None:
        self._owner = owner

    def __getattr__(self, name: str) -> Any:
        raise RuntimeError(
            f"{self._owner}: no database session injected (pass request.dbsession); "
            f"cannot access '{name}'"
        )


def resolve_db(db: Any, owner: str) -> Any:
    """Return the injected session, or a loud ``MissingDatabase`` placeholder."""
    return db if db is not None else MissingDatabase(owner)
