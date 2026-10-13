"""AddressBook, AddressBookFAX and AddressBookEmail: companies, their fax numbers and e-mail contacts (group 3)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from namifax.models.types import LegacyHtmlString
from namifax.models.meta import Base


class AddressBook(Base):
    # Table and column names are kept exactly as the legacy SQL spells them. The legacy table only had
    # abook_id and company; the other columns are extensions the port added and only the demo data fills.
    __tablename__ = "AddressBook"

    abook_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    company: Mapped[Optional[str]] = mapped_column(LegacyHtmlString(255))
    description: Mapped[Optional[str]] = mapped_column(LegacyHtmlString(255))
    faxtype: Mapped[Optional[str]] = mapped_column(String(32))
    faxnum: Mapped[Optional[str]] = mapped_column(String(64))
    phonenum: Mapped[Optional[str]] = mapped_column(String(64))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    address: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(128))
    state: Mapped[Optional[str]] = mapped_column(String(64))
    zip: Mapped[Optional[str]] = mapped_column(String(32))
    country: Mapped[Optional[str]] = mapped_column(String(64))


class AddressBookFAX(Base):
    __tablename__ = "AddressBookFAX"

    abookfax_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    abook_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    faxnumber: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(LegacyHtmlString(255))
    to_person: Mapped[Optional[str]] = mapped_column(LegacyHtmlString(255))
    to_location: Mapped[Optional[str]] = mapped_column(LegacyHtmlString(255))
    to_voicenumber: Mapped[Optional[str]] = mapped_column(LegacyHtmlString(255))
    # street address, zip and city of the contact (the original added them in 3.3.4 as NOT NULL columns without a
    # default, so a row must always carry a value)
    to_address: Mapped[str] = mapped_column(LegacyHtmlString(50), nullable=False, default="", server_default="")
    to_zip: Mapped[str] = mapped_column(String(16), nullable=False, default="", server_default="")
    to_city: Mapped[str] = mapped_column(LegacyHtmlString(50), nullable=False, default="", server_default="")
    faxcatid: Mapped[Optional[int]] = mapped_column(Integer)
    faxfrom: Mapped[Optional[int]] = mapped_column(Integer, server_default="0")
    faxto: Mapped[Optional[int]] = mapped_column(Integer, server_default="0")
    printer: Mapped[Optional[str]] = mapped_column(String(255))


class AddressBookEmail(Base):
    __tablename__ = "AddressBookEmail"

    abookemail_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    abook_id: Mapped[Optional[int]] = mapped_column(Integer)
    contact_name: Mapped[Optional[str]] = mapped_column(LegacyHtmlString(255))
    contact_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
