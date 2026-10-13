"""Table access for the services: ``Repository("Modems", db=session)``.

The name ``MDBOData`` comes from the original PHP class this replaces; both names return an ``OrmRepository``.
"""

from __future__ import annotations

from typing import Any

from namifax.db.missing import resolve_db
from namifax.db.orm_repository import SQL_AND, SQL_OR, OrmRepository  # noqa: F401


def Repository(model_class: Any, db: Any = None) -> OrmRepository:  # noqa: N802
    """The repository for a table, bound to ``db`` (a session; ``None`` fails loudly on first use)."""
    return OrmRepository(model_class, resolve_db(db, "Repository"))


MDBOData = Repository
