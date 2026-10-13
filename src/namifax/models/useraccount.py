"""UserAccount: login accounts (B track, group 3)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, String, Text, false, true
from sqlalchemy.orm import Mapped, mapped_column

from namifax.models.meta import Base
from namifax.models.types import IsoText, LegacyBoolean, LegacyHtmlString, LegacyHtmlText


class UserAccount(Base):
    # Table and column names are kept exactly as the legacy SQL spells them. The flag columns are booleans
    # (MySQL BOOL in the legacy schema) read through LegacyBoolean; dates stay ISO text on every database.
    __tablename__ = "UserAccount"

    uid: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[Optional[str]] = mapped_column(LegacyHtmlString(255))
    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)    # Argon2id (MD5 hex, the legacy format, until the next login)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email_sig: Mapped[Optional[str]] = mapped_column(LegacyHtmlText)
    user_tsi: Mapped[Optional[str]] = mapped_column(LegacyHtmlString(255))
    from_company: Mapped[Optional[str]] = mapped_column(LegacyHtmlString(255))
    from_location: Mapped[Optional[str]] = mapped_column(LegacyHtmlString(255))
    from_voicenumber: Mapped[Optional[str]] = mapped_column(String(255))
    from_faxnumber: Mapped[Optional[str]] = mapped_column(String(255))
    coverpage_id: Mapped[Optional[int]] = mapped_column(Integer)
    audiofile: Mapped[Optional[str]] = mapped_column(String(255))
    faxperpageinbox: Mapped[Optional[int]] = mapped_column(Integer)
    faxperpagearchive: Mapped[Optional[int]] = mapped_column(Integer)
    superuser: Mapped[Optional[bool]] = mapped_column(LegacyBoolean, server_default=false())
    can_del: Mapped[Optional[bool]] = mapped_column(LegacyBoolean, server_default=false())
    last_mod: Mapped[Optional[str]] = mapped_column(IsoText(32))
    last_login: Mapped[Optional[str]] = mapped_column(IsoText(32))
    last_ip: Mapped[Optional[str]] = mapped_column(String(45))            # long enough for IPv6
    language: Mapped[Optional[str]] = mapped_column(String(16), server_default="en")
    modemdevs: Mapped[Optional[str]] = mapped_column(Text)
    didrouting: Mapped[Optional[str]] = mapped_column(Text)
    faxcats: Mapped[Optional[str]] = mapped_column(Text)
    pwdexpire: Mapped[Optional[str]] = mapped_column(IsoText(32))
    pwdcycle: Mapped[Optional[int]] = mapped_column(Integer, server_default="0")
    pwd_reuse: Mapped[Optional[bool]] = mapped_column(LegacyBoolean, server_default=false())
    is_admin: Mapped[Optional[bool]] = mapped_column(LegacyBoolean, server_default=false())
    wasreset: Mapped[Optional[bool]] = mapped_column(LegacyBoolean, server_default=false())
    acc_enabled: Mapped[Optional[bool]] = mapped_column(LegacyBoolean, server_default=true())
    deleted: Mapped[Optional[bool]] = mapped_column(LegacyBoolean, server_default=false())
    any_modem: Mapped[Optional[bool]] = mapped_column(LegacyBoolean, server_default=false())
