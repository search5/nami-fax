"""SystemConfig: generic key/value settings table (spec 48 / B track pilot)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from namifax.models.meta import Base


class SystemConfig(Base):
    # The table name is kept exactly as the legacy SQL spells it, so raw queries that still exist
    # keep working on case-sensitive databases (MySQL and MariaDB on Linux).
    __tablename__ = "SystemConfig"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text)
