"""Modems: a fax modem line (B track, group 2)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from namifax.models.types import LegacyHtmlString
from namifax.models.meta import Base


class Modems(Base):
    # Table and column names are kept exactly as the legacy SQL spells them.
    __tablename__ = "Modems"

    devid: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    alias: Mapped[Optional[str]] = mapped_column(LegacyHtmlString(255))
    contact: Mapped[Optional[str]] = mapped_column(String(255))
    printer: Mapped[Optional[str]] = mapped_column(String(255))
    faxcatid: Mapped[Optional[int]] = mapped_column(Integer)
