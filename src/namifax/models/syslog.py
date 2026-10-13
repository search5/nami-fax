"""SysLog: application event log shown in the admin viewer (B track, group 1)."""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from namifax.models.meta import Base
from namifax.models.types import IsoText


class SysLog(Base):
    # Table and column names are kept exactly as the legacy SQL spells them (the key is syslogid; the port
    # first called it log_id, which revision 0023 renames).
    __tablename__ = "SysLog"

    syslogid: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # ISO text 'YYYY-MM-DD HH:MM:SS' (the legacy column is TEXT). It stays text because the viewer filters
    # by date prefix with LIKE, which PostgreSQL does not allow on timestamp columns, and ISO text sorts
    # chronologically on every database.
    logdate: Mapped[str] = mapped_column(IsoText(32), nullable=False)
    logtext: Mapped[str] = mapped_column(Text, nullable=False)
