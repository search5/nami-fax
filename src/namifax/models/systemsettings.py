"""SystemSettings: the single-row SMTP gateway configuration (B track, group 1)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Integer, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from namifax.models.meta import Base


class SystemSettings(Base):
    # Table and column names are kept exactly as the legacy SQL spells them.
    __tablename__ = "SystemSettings"

    # always the one row with id = 1
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    smtp_host: Mapped[Optional[str]] = mapped_column(String(255), server_default="localhost")
    smtp_port: Mapped[Optional[int]] = mapped_column(Integer, server_default="25")
    smtp_security: Mapped[Optional[str]] = mapped_column(String(16), server_default="NONE")
    smtp_auth: Mapped[Optional[bool]] = mapped_column(Boolean, server_default=false())
    smtp_username: Mapped[Optional[str]] = mapped_column(String(255))
    smtp_password: Mapped[Optional[str]] = mapped_column(String(512))   # holds an encrypted token
    from_email: Mapped[Optional[str]] = mapped_column(String(255), server_default="root@localhost")
    from_name: Mapped[Optional[str]] = mapped_column(String(255), server_default="NamiFAX")
    email_sig_text: Mapped[Optional[str]] = mapped_column(Text)
    email_sig_html: Mapped[Optional[str]] = mapped_column(Text)
    # ISO-8601 text (the legacy column is TEXT), so existing rows keep working on every database
    updated_at: Mapped[Optional[str]] = mapped_column(String(40))
