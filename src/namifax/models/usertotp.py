"""UserTOTP: two-factor secrets and recovery codes (B track, group 3)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from namifax.models.meta import Base
from namifax.models.types import LegacyBoolean


class UserTOTP(Base):
    __tablename__ = "UserTOTP"

    uid: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    secret_key: Mapped[str] = mapped_column(String(255), nullable=False)
    is_enabled: Mapped[Optional[bool]] = mapped_column(LegacyBoolean, server_default=false())
    backup_codes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[str]] = mapped_column(String(40))
    # brute-force protection: consecutive wrong codes and, once too many, when the lock ends (ISO text)
    failed_attempts: Mapped[Optional[int]] = mapped_column(Integer, server_default="0")
    locked_until: Mapped[Optional[str]] = mapped_column(String(32))
