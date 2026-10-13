"""CoverPages: fax cover page templates (B track, group 2)."""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from namifax.models.types import LegacyHtmlString
from namifax.models.meta import Base


class CoverPages(Base):
    # Table and column names are kept exactly as the legacy SQL spells them.
    __tablename__ = "CoverPages"

    cover_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(LegacyHtmlString(255), nullable=False)
    file: Mapped[str] = mapped_column(String(255), nullable=False)
