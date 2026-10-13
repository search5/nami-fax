"""Default and demo records, written through the ORM.

* ``seed_default_records``: the fax categories and cover pages every installation starts with; only while those
  tables are empty. Used on every database.
* ``seed_demo_records``: users with a well-known password, a sample address book, routes and two faxes. Only SQLite
  databases get them, and only when they are brand new (no users yet); servers never do. They exist for development
  and the test suites.

Both run on every start, so they must never alter data that already exists.
"""

from __future__ import annotations

import os

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from namifax.models import (
    AddressBook, AddressBookEmail, AddressBookFAX, BarcodeRoute, CoverPages, DIDRoute, DistroList, DynConf, FaxArchive,
    FaxCategory, Modems, SysLog, UserAccount,
)


def _count(session: Session, model) -> int:
    return session.execute(select(func.count()).select_from(model)).scalar_one()


def seed_default_records(session: Session) -> None:
    """The original's three cover pages (their files ship in static/images), only while the table is empty."""
    if _count(session, CoverPages) == 0:
        session.add_all([CoverPages(title="Generic A4", file="cover.ps"),
                         CoverPages(title="Generic Letter", file="cover-letter.ps"),
                         CoverPages(title="Generic HTML", file="coverpage.html")])
    session.flush()


def seed_if_empty(session: Session) -> None:
    """Defaults everywhere; the demo data too when this is a brand-new database (no users yet)."""
    brand_new = _count(session, UserAccount) == 0
    seed_default_records(session)
    if brand_new:
        seed_demo_records(session)


def _add_missing(session: Session, model, key: int, **values) -> None:
    """Add the row with this id unless it exists (``INSERT OR IGNORE``)."""
    if session.get(model, key) is None:
        session.add(model(**{model.__mapper__.primary_key[0].key: key}, **values))


def seed_demo_records(session: Session) -> None:
    """Demo data for a brand-new database."""
    md5_of_password = "5f4dcc3b5aa765d61d8327deb882cf99"  # gitleaks:allow
    if _count(session, UserAccount) == 0:
        session.add_all([
            UserAccount(uid=1, name="System Administrator", username="admin", password=md5_of_password,
                        email="admin@namifax.local", superuser=True, is_admin=True, can_del=True, any_modem=True,
                        acc_enabled=True, last_login="2026-09-29 09:00:00"),   # (no forced password change)
            UserAccount(uid=2, name="Operator User", username="operator", password=md5_of_password,
                        email="operator@namifax.local", superuser=False, is_admin=False, can_del=False,
                        any_modem=True, acc_enabled=True, last_login="2026-09-29 09:00:00"),
        ])

    if _count(session, FaxCategory) == 0:
        for cid, name in ((1, "General"), (2, "Invoices"), (3, "Legal")):
            _add_missing(session, FaxCategory, cid, name=name)

    if _count(session, Modems) < 2:
        _add_missing(session, Modems, 1, device="ttyS0", alias="Sales Inbound", contact="sales@avantfax.local", printer="lp1")
        _add_missing(session, Modems, 2, device="ttyS1", alias="Support Outbound", contact="support@avantfax.local", printer="lp2")

    if _count(session, DIDRoute) < 2:
        _add_missing(session, DIDRoute, 1, routecode="1000", alias="Main Trunk", contact="sales@namifax.local", printer="lp_sales")
        _add_missing(session, DIDRoute, 2, routecode="1001", alias="Accounting Direct", contact="billing@namifax.local", printer="lp_billing")

    if _count(session, BarcodeRoute) == 0:
        session.add(BarcodeRoute(barcode_id=1, barcode="BC-1001", alias="Sales Barcode", contact="sales@company.com",
                                 printer="HPLaserJet"))

    # the demo rule goes only into an empty table, never over the administrator's rules
    if _count(session, DynConf) == 0:
        session.add(DynConf(dynconf_id=1, callid="01012345678", device="ttyS0"))
    session.flush()

    acme = session.execute(select(AddressBook).where(AddressBook.company.in_(["Acme Corp", "Acme Global"]))).first()
    if acme is None:
        company = AddressBook(company="Acme Corp", faxnum="1234567", phonenum="555-0100", email="info@acmeglobal.com",
                              address="100 Enterprise Way", city="Metropolis", state="CA", zip="90210")
        session.add(company)
        session.flush()
        _add_missing(session, AddressBookFAX, 1, abook_id=company.abook_id, faxnumber="1234567", to_person="Acme Main",
                     email="faxes@acme.com", printer="OfficePrinter")
        _add_missing(session, AddressBookEmail, 1, abook_id=company.abook_id, contact_name="Jane Doe",
                     contact_email="jane@example.com")
    if session.execute(select(AddressBook).where(AddressBook.company == "Initech Corp")).first() is None:
        company = AddressBook(company="Initech Corp", faxnum="9876543", phonenum="555-0200", email="contact@initech.com",
                              address="200 Tech Park", city="Silicon Valley", state="CA", zip="94025")
        session.add(company)
        session.flush()
        _add_missing(session, AddressBookFAX, 2, abook_id=company.abook_id, faxnumber="9876543", to_person="Initech Main",
                     email="faxes@cyberdyne.com", printer="MainLaser")
        _add_missing(session, AddressBookEmail, 2, abook_id=company.abook_id, contact_name="John Smith",
                     contact_email="user@example.com")

    if _count(session, DistroList) == 0:
        session.add(DistroList(dl_id=1, listname="Executive Team", listdata="1234567; 9876543",
                               lastmod_date="2026-09-29 10:00:00", lastmod_user=1))

    if _count(session, SysLog) == 0:
        session.add_all([
            SysLog(logdate="2026-09-29 12:35:10", logtext="Fax job #12 dispatched to destination +1-555-0199: SUCCESS"),
            SysLog(logdate="2026-09-29 12:40:22", logtext="User 'admin' successfully authenticated from IP 127.0.0.1"),
        ])
    session.flush()

    acme_id = session.execute(select(AddressBook.abook_id).where(AddressBook.company.like("Acme%"))
                              .order_by(AddressBook.abook_id)).scalars().first()
    if session.execute(select(func.count()).select_from(FaxArchive).where(FaxArchive.inbox == 1)).scalar_one() == 0:
        _add_missing(session, FaxArchive, 1, faxpath="faxes/2026/09/29/fax001", faxnumid=1, companyid=acme_id,
                     origfaxnum="+1-555-0199", pages=2, modemdev="ttyS0", archstamp="2026-09-29 10:00:00",
                     description="Monthly Financial Report", inbox=1)
    if session.execute(select(func.count()).select_from(FaxArchive).where(FaxArchive.inbox == 0)).scalar_one() == 0:
        _add_missing(session, FaxArchive, 2, faxpath="faxes/2026/09/29/fax002", faxnumid=1, companyid=acme_id,
                     origfaxnum="+1-555-0199", pages=2, modemdev="ttyS0", archstamp="2026-09-29 09:30:00",
                     description="Quarterly Financial Fax Transmission", inbox=0, faxcatid=1)
    session.flush()
    first = session.get(FaxArchive, 1)
    if first is not None and first.companyid is None and acme_id is not None:
        first.companyid = acme_id        # the demo inbox fax belongs to the demo company
    session.flush()

    _write_demo_fax_files()


def _write_demo_fax_files() -> None:
    """Valid fixture files for the demo inbox fax (fid 1), so downloading it works."""
    fax1_dir = os.path.join("faxes", "2026", "09", "29", "fax001")
    os.makedirs(fax1_dir, exist_ok=True)
    pdf_path = os.path.join(fax1_dir, "fax.pdf")
    if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
        with open(pdf_path, "wb") as f:
            f.write(
                b"%PDF-1.4\n"
                b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
                b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
                b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
                b"xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n"
                b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF\n"
            )
    tif_path = os.path.join(fax1_dir, "fax.tif")
    if not os.path.exists(tif_path) or os.path.getsize(tif_path) == 0:
        with open(tif_path, "wb") as f:
            f.write(b"II*\x00\x08\x00\x00\x00\x00\x00")
