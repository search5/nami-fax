"""FaxArchive: every received (inbox) and archived fax (B track, group 4)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from namifax.models.meta import Base
from namifax.models.types import IsoText, LegacyHtmlText


class FaxArchive(Base):
    # The legacy columns only. Dates are ISO text (as in the other models) so that the prefix and range
    # filters of the archive search behave the same on every database. The port's SQLite table carries a
    # few extra columns of its own; they are left alone and not mapped.
    __tablename__ = "FaxArchive"

    fid: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    faxnumid: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    companyid: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    faxpath: Mapped[str] = mapped_column(String(255), nullable=False)
    pages: Mapped[Optional[int]] = mapped_column(Integer)
    faxcatid: Mapped[Optional[int]] = mapped_column(Integer)
    didr_id: Mapped[Optional[int]] = mapped_column(Integer)
    description: Mapped[Optional[str]] = mapped_column(LegacyHtmlText)
    lastoperation: Mapped[Optional[str]] = mapped_column(IsoText(32))
    lastmoduser: Mapped[Optional[int]] = mapped_column(Integer)
    lastmoddate: Mapped[Optional[str]] = mapped_column(IsoText(32))
    archstamp: Mapped[Optional[str]] = mapped_column(IsoText(32), index=True)
    modemdev: Mapped[Optional[str]] = mapped_column(String(64))
    userid: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    origfaxnum: Mapped[Optional[str]] = mapped_column(String(32))
    faxcontent: Mapped[Optional[str]] = mapped_column(Text)
    inbox: Mapped[Optional[int]] = mapped_column(Integer, server_default="1", index=True)
