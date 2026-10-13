"""UserWebAuthnCredentials: registered passkeys (B track, group 3)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from namifax.models.meta import Base


class UserWebAuthnCredentials(Base):
    # The legacy DDL was MySQL-only (AUTO_INCREMENT, ENGINE=InnoDB, NOW()); it never ran on SQLite.
    __tablename__ = "UserWebAuthnCredentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    credential_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    sign_count: Mapped[Optional[int]] = mapped_column(Integer, server_default="0")
    transports: Mapped[Optional[str]] = mapped_column(String(100))
    device_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[Optional[str]] = mapped_column(String(32))
    last_used_at: Mapped[Optional[str]] = mapped_column(String(32))
