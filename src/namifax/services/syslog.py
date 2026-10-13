"""Search the SysLog event table through an ORM session."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from namifax.models.syslog import SysLog

class SysLogService:
    """Read access to the ``SysLog`` table for the admin viewer.

    Filters are bound parameters (no string-built SQL). The keyword match is a case-insensitive
    substring match on every database, and ``%`` / ``_`` in the keyword are taken literally.
    """

    def __init__(self, session: Optional[Session] = None) -> None:
        self.session = session

    def _require_session(self) -> Session:
        if self.session is None:
            raise RuntimeError("SysLogService: no database session injected (pass request.dbsession)")
        return self.session

    def add(self, logtext: str, logdate: Optional[str] = None) -> None:
        """Record an event ('YYYY-MM-DD HH:MM:SS' local time unless a date is given)."""
        session = self._require_session()
        session.add(SysLog(logdate=logdate or datetime.now().strftime("%Y-%m-%d %H:%M:%S"), logtext=logtext))
        session.flush()

    @staticmethod
    def _date_prefix(day: str, month: str, year: str) -> str:
        """Build the 'YYYY[-MM[-DD]]' prefix from the viewer's drop-downs ('*' means any)."""
        if day and month and year and day != "*" and month != "*" and year != "*":
            d_val = f"{int(day):02d}" if day.isdecimal() else day
            m_val = f"{int(month):02d}" if month.isdecimal() else month
            return f"{year}-{m_val}-{d_val}"
        if month and year and month != "*" and year != "*":
            m_val = f"{int(month):02d}" if month.isdecimal() else month
            return f"{year}-{m_val}"
        if year and year != "*":
            return f"{year}"
        return ""

    def _filtered(self, stmt, kw: str, day: str, month: str, year: str):
        if kw:
            stmt = stmt.where(func.lower(SysLog.logtext).contains(kw.lower(), autoescape=True))
        prefix = self._date_prefix(day, month, year)
        if prefix:
            stmt = stmt.where(SysLog.logdate.startswith(prefix, autoescape=True))
        return stmt

    def count(self, kw: str = "", day: str = "", month: str = "", year: str = "") -> int:
        """How many events the filter matches."""
        session = self._require_session()
        return int(session.scalar(self._filtered(select(func.count()).select_from(SysLog), kw, day, month, year)) or 0)

    def search(self, kw: str = "", day: str = "", month: str = "", year: str = "",
               limit: Optional[int] = None, offset: int = 0) -> list[dict[str, str]]:
        """The matching events, newest first. Like the original there is no row limit unless the caller asks for a page."""
        session = self._require_session()
        stmt = self._filtered(select(SysLog.logdate, SysLog.logtext), kw, day, month, year)
        stmt = stmt.order_by(SysLog.logdate.desc(), SysLog.syslogid.desc())
        if limit is not None:
            stmt = stmt.limit(limit).offset(max(offset, 0))
        return [{"logdate": str(r.logdate), "logtext": str(r.logtext)} for r in session.execute(stmt)]
