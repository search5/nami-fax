"""Let the application run on tables it did not create.

Existing installations of the original AvantFAX (and databases written by older versions of this port) already have
tables. Alembic leaves a table that exists alone, so what the models need on top of it is added here, before the
revisions run:

* **missing columns**: added as nullable columns (or with the model's server default). The original tables lack columns
  the application uses (for example the address book's extra fields) and an old installation lacks columns that later
  versions of the original added.
* **missing indexes**: the models declare indexes the original never had (the archive search relies on them); they are
  created when no index covers the same columns yet.
* **too narrow columns**: a few legacy columns are too small for values the application writes today and are widened
  (``UserAccount.last_ip`` held 15 characters, an IPv6 address needs 45).

Nothing is ever dropped, renamed or retyped, and existing rows are not touched, so the original application can keep
using the same database. Every step is idempotent and does nothing on a database that has none of these tables.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateColumn, CreateIndex

# (table, column) -> the length it must hold at least
_WIDEN = {("UserAccount", "last_ip"): 45}


def adopt_existing_tables(engine: Engine) -> None:
    import namifax.models  # noqa: F401  (registers every table)
    from namifax.models.meta import Base

    inspector = sa.inspect(engine)
    existing = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing:
                continue
            columns = {c["name"]: c for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in columns and not column.primary_key:
                    _add_column(conn, engine, table, column)
            _widen(conn, engine, table.name, columns)
            _add_indexes(conn, engine, inspector, table)


def _add_column(conn: Any, engine: Engine, table: sa.Table, column: sa.Column) -> None:
    # a detached copy: nullable unless the model gives a default, so rows that already exist stay valid
    keep_not_null = not column.nullable and column.server_default is not None
    clone = sa.Column(column.name, column.type, nullable=not keep_not_null, server_default=column.server_default)
    holder = sa.Table(table.name, sa.MetaData(), clone)
    spec = str(CreateColumn(clone).compile(dialect=engine.dialect))
    conn.execute(sa.text(f"ALTER TABLE {engine.dialect.identifier_preparer.format_table(holder)} ADD COLUMN {spec}"))


def _widen(conn: Any, engine: Engine, table: str, columns: dict) -> None:
    if engine.dialect.name not in ("mysql", "mariadb"):
        return                       # SQLite does not enforce lengths and PostgreSQL columns are made at full size
    for (name_table, name), length in _WIDEN.items():
        info = columns.get(name)
        if name_table == table and info is not None and isinstance(info["type"], sa.String) \
                and info["type"].length and info["type"].length < length:
            quote = engine.dialect.identifier_preparer.quote
            nullable = "NULL" if info.get("nullable", True) else "NOT NULL"
            conn.execute(sa.text(f"ALTER TABLE {quote(table)} MODIFY {quote(name)} VARCHAR({length}) {nullable}"))


def _add_indexes(conn: Any, engine: Engine, inspector: sa.Inspector, table: sa.Table) -> None:
    have = [tuple(i["column_names"]) for i in inspector.get_indexes(table.name)]
    have.append(tuple(c for c in (inspector.get_pk_constraint(table.name) or {}).get("constrained_columns", [])))
    present = {c["name"] for c in inspector.get_columns(table.name)}
    for index in table.indexes:
        names = tuple(c.name for c in index.columns)
        if index.unique or names in have or not set(names) <= present:
            continue
        conn.execute(CreateIndex(index))
