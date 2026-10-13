"""DistroList: fax distribution lists (B track, group 3)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from namifax.models.meta import Base
from namifax.models.types import IsoText, LegacyHtmlString


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class DistroList(Base):
    # Table and column names are kept exactly as the legacy SQL spells them.
    __tablename__ = "DistroList"

    dl_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    listname: Mapped[str] = mapped_column(LegacyHtmlString(255), nullable=False)
    listdata: Mapped[Optional[str]] = mapped_column(Text)
    # The legacy column was a MySQL TIMESTAMP that updated itself on every change. ISO text keeps existing
    # rows readable on every database, and the ORM maintains it on insert and update.
    lastmod_date: Mapped[Optional[str]] = mapped_column(IsoText(32), default=_now, onupdate=_now)
    lastmod_user: Mapped[Optional[int]] = mapped_column(Integer)
