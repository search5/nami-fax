"""ORM-backed implementation of the MDBOData repository API (B track).

``Repository("Modems", db=<Session>)`` returns an ``OrmRepository``. It offers the same
methods the services already use (``find``, ``new_entry``, ``update_entry``, ``delete_entry``,
``load``, ``get_id``, ``get_info`` and ``data.set_id``) but runs on a SQLAlchemy session, so values
are bound parameters and the table, types and quoting are right for SQLite, MySQL, MariaDB and
PostgreSQL.

Behaviour kept from the original PHP/SQL implementation so callers do not change:

* ``find`` compares with equality only; comparing with ``None`` matches nothing (SQL ``= NULL``).
* values are loosely typed: ``"5"`` matches an integer column (PostgreSQL would not convert it).
* updating or deleting a row that does not exist still succeeds.
* ``reduce_single`` returns a dict for exactly one match.

Behaviour that differs on purpose: database errors (for example a unique violation) are raised as
exceptions instead of turning into ``False``. The raw ``query`` method is not available; use
``select`` for ordered listings.
"""

from __future__ import annotations

from typing import Any, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Session

from namifax.models.types import LegacyHtmlString, LegacyHtmlText

SQL_AND = " AND "
SQL_OR = " OR "


def resolve_model(name_or_class: Any) -> type:
    """Find the mapped class for a table name, class name or class."""
    import namifax.models  # noqa: F401  (registers every model)
    from namifax.models.meta import Base

    name = name_or_class if isinstance(name_or_class, str) else getattr(
        name_or_class, "table_name", getattr(name_or_class, "__name__", str(name_or_class)))
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        if getattr(cls, "__tablename__", None) == name or cls.__name__ == name:
            return cls
    raise LookupError(f"no ORM model for {name!r}")


def _coerce(column: sa.Column, value: Any) -> Any:
    """Convert a loosely typed legacy value for the column; raises ValueError when impossible."""
    if value is None:
        return None
    col_type = column.type
    if isinstance(col_type, (LegacyHtmlString, LegacyHtmlText)):
        col_type = col_type.impl                      # (text that is read with its HTML entities undone)
    if isinstance(col_type, sa.Boolean):
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "on", "yes")
        return bool(value)
    if isinstance(col_type, sa.Integer):
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        return int(str(value).strip())
    if isinstance(col_type, (sa.String, sa.Text)):
        return value if isinstance(value, str) else str(value)
    return value


class OrmRecord:
    """The record an ``OrmRepository`` currently points at (the role of the original PHP ``MDBObject``)."""

    def __init__(self, model: type) -> None:
        self._table = sa.inspect(model).local_table
        self._pk = next(iter(self._table.primary_key.columns)).name
        self._vars: dict[str, Any] = {}

    def get_table_name(self) -> str:
        return self._table.name

    def get_table_id(self) -> str:
        return self._pk

    def get_id(self) -> Optional[int]:
        value = self._vars.get(self._pk)
        try:
            return int(value) if value is not None else None
        except (ValueError, TypeError):
            return None

    def set_id(self, id_val: Any) -> bool:
        try:
            self._vars[self._pk] = int(id_val)
            return True
        except (ValueError, TypeError):
            return False

    def set_vars(self, values: dict[str, Any]) -> None:
        self._vars.update(values)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self._vars.items() if v is not None}


class OrmRepository:
    """MDBOData-compatible repository on a SQLAlchemy session."""

    def __init__(self, model_class: Any, session: Session) -> None:
        self.session = session
        self.model = model_class if isinstance(model_class, type) and hasattr(model_class, "__table__") \
            else resolve_model(model_class)
        self._table = sa.inspect(self.model).local_table
        self._attr = {a.columns[0].name: a.key for a in sa.inspect(self.model).column_attrs}
        self._pk_col = next(iter(self._table.primary_key.columns))
        self.data = OrmRecord(self.model)

    # --- helpers ------------------------------------------------------------------------
    def _column(self, name: str) -> sa.Column:
        try:
            return self._table.c[name]
        except KeyError:
            raise LookupError(f"{self._table.name} has no column {name!r}") from None

    def _row_dict(self, obj: Any) -> dict[str, Any]:
        return {col: getattr(obj, attr) for col, attr in self._attr.items()}

    def _fill(self, row: dict[str, Any]) -> None:
        self.data = OrmRecord(self.model)
        self.data.set_vars(row)

    def _values(self, info: dict[str, Any]) -> dict[str, Any]:
        """Known columns only, coerced; the primary key is left out."""
        out = {}
        for key, value in info.items():
            if key not in self._attr or key == self._pk_col.name:
                continue
            out[self._attr[key]] = _coerce(self._table.c[key], value)
        return out

    # --- API used by the services -------------------------------------------------------
    def get_id(self) -> Optional[int]:
        return self.data.get_id()

    def get_info(self) -> dict[str, Any]:
        return self.data.to_dict()

    def get_error(self) -> Optional[str]:
        return None

    def load(self, id_val: Any) -> bool:
        try:
            pk = _coerce(self._pk_col, id_val)
        except ValueError:
            return False
        row = self.session.get(self.model, pk)
        if row is None:
            return False
        self._fill(self._row_dict(row))
        return True

    def new_entry(self, info: dict[str, Any]) -> bool:
        values = self._values(info)
        pk_name = self._pk_col.name
        if self._pk_col.autoincrement is False and info.get(pk_name) is not None:
            # a key the caller assigns (not generated by the database), e.g. UserTOTP.uid
            values[self._attr[pk_name]] = _coerce(self._pk_col, info[pk_name])
        obj = self.model(**values)
        self.session.add(obj)
        self.session.flush()
        self._fill(self._row_dict(obj))
        return True

    def update_entry(self, info: Optional[dict[str, Any]] = None) -> bool:
        if info:
            self.data.set_vars(info)
        pk = self.data.get_id()
        if pk is None:
            return self.new_entry(self.data.to_dict()) if not info else False
        row = self.session.get(self.model, pk)
        if row is not None:
            for attr, value in self._values(info or self.data.to_dict()).items():
                setattr(row, attr, value)
            self.session.flush()
        return True  # like the legacy UPDATE, a missing row is not an error

    def delete_entry(self, info: Optional[dict[str, Any]] = None) -> bool:
        if info:
            self.data.set_vars(info)
        pk = self.data.get_id()
        if pk is None:
            return False
        row = self.session.get(self.model, pk)
        if row is not None:
            self.session.delete(row)
            self.session.flush()
        return True

    def find(
        self,
        conditions: Optional[dict[str, Any]] = None,
        query_logic: str = SQL_AND,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        reduce_single: bool = True,
    ) -> Any:
        clauses = []
        for key, value in (conditions or {}).items():
            column = self._column(key)
            if value is None:
                clauses.append(sa.false())  # SQL "= NULL" never matches
                continue
            try:
                clauses.append(column == _coerce(column, value))
            except ValueError:
                clauses.append(sa.false())
        stmt = sa.select(self.model)
        if clauses:
            stmt = stmt.where(sa.and_(*clauses) if query_logic == SQL_AND else sa.or_(*clauses))
        stmt = stmt.order_by(self._pk_col)
        if limit is not None:
            stmt = stmt.limit(int(limit))
            if offset is not None:
                stmt = stmt.offset(int(offset))
        records = [self._row_dict(o) for o in self.session.scalars(stmt)]
        if reduce_single and len(records) == 1:
            return records[0]
        return records

    def delete_where(self, conditions: dict[str, Any]) -> int:
        """Delete every row matching all conditions; returns how many. No conditions deletes nothing."""
        if not conditions:
            return 0
        clauses = []
        for key, value in conditions.items():
            column = self._column(key)
            if value is None:
                return 0                      # SQL "= NULL" never matches
            try:
                clauses.append(column == _coerce(column, value))
            except ValueError:
                return 0
        result = self.session.execute(sa.delete(self._table).where(sa.and_(*clauses)))
        self.session.expire_all()
        return int(result.rowcount or 0)

    def update_where(self, conditions: dict[str, Any], values: dict[str, Any]) -> int:
        """Set ``values`` on every row matching all conditions; returns how many. No conditions updates nothing."""
        if not conditions or not values:
            return 0
        clauses = []
        for key, value in conditions.items():
            column = self._column(key)
            if value is None:
                return 0                      # SQL "= NULL" never matches
            try:
                clauses.append(column == _coerce(column, value))
            except ValueError:
                return 0
        assignments = {k: _coerce(self._column(k), v) for k, v in values.items() if k in self._attr}
        result = self.session.execute(sa.update(self._table).where(sa.and_(*clauses)).values(**assignments))
        self.session.expire_all()
        return int(result.rowcount or 0)

    def search_text(self, column: str, text: str, order_by: Optional[str] = None) -> list[dict[str, Any]]:
        """Rows whose ``column`` contains the words of ``text`` in order (case-insensitive, wildcards literal)."""
        from namifax.db.textsearch import ESCAPE_CHAR, like_patterns

        col = self._column(column)
        order_col = self._column(order_by) if order_by else self._pk_col
        stmt = (sa.select(self.model)
                .where(sa.or_(*[sa.func.lower(col).like(p, escape=ESCAPE_CHAR) for p in like_patterns(text)]))
                .order_by(order_col, self._pk_col))
        return [self._row_dict(o) for o in self.session.scalars(stmt)]

    def findext(self, conditions: dict[str, Any]) -> Any:
        return self.find(conditions=conditions, query_logic=SQL_AND, reduce_single=True)

    def select(
        self,
        columns: Optional[list[str]] = None,
        order_by: Optional[str] = None,
        descending: bool = False,
    ) -> list[dict[str, Any]]:
        """Ordered listing (replaces raw ``SELECT ... ORDER BY`` strings)."""
        names = columns or list(self._attr)
        stmt = sa.select(*[self._column(n) for n in names])
        order_col = self._column(order_by) if order_by else self._pk_col
        if order_col.nullable:
            # SQLite and MySQL sort NULL first when ascending, PostgreSQL last: make it the same everywhere
            null_rank = sa.case((order_col.is_(None), 1 if descending else 0), else_=0 if descending else 1)
            stmt = stmt.order_by(null_rank)
        stmt = stmt.order_by(order_col.desc() if descending else order_col.asc(), self._pk_col)
        return [dict(zip(names, row)) for row in self.session.execute(stmt)]

    def query(self, sql: str, reduce_single: bool = True) -> Any:
        raise NotImplementedError("raw SQL is not available on the ORM repository; use select(order_by=...)")
