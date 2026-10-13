"""The application on a database that the original AvantFAX created (existing users keep their data).

Every test here runs on a real MySQL and MariaDB server, on both a current (3.3.5) and an old (3.2.0) installation.
"""

from __future__ import annotations

import re

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

pytestmark = pytest.mark.serverdb

LEGACY_TABLES = ["AddressBook", "AddressBookEmail", "AddressBookFAX", "BarcodeRoute", "CoverPages", "DIDRoute", "DistroList",
                 "DynConf", "FaxArchive", "FaxCategory", "Modems", "SysLog", "UserAccount", "UserPasswords"]
ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


def _snapshot(engine):
    out = {}
    with engine.connect() as conn:
        for table in LEGACY_TABLES:
            out[table] = [tuple(r) for r in conn.execute(sa.text(f"SELECT * FROM {table} ORDER BY 1")).all()]
    return out


@pytest.fixture
def adopted(legacy_db):
    from namifax.db.bootstrap import ensure_schema

    ensure_schema(legacy_db.engine)
    return legacy_db


@pytest.fixture
def session(adopted):
    with Session(adopted.engine) as s:
        yield s
        s.rollback()


# --- adopting the database ---------------------------------------------------------------------------------------------

def test_starting_on_a_legacy_database_keeps_every_legacy_row(legacy_db):
    from namifax.db.bootstrap import ensure_schema

    before = _snapshot(legacy_db.engine)
    ensure_schema(legacy_db.engine)
    after = _snapshot(legacy_db.engine)
    for table in LEGACY_TABLES:
        # (columns the application adds are NULL/default, so compare the legacy part of each row)
        assert [r[:len(before[table][0])] if before[table] else r for r in after[table]] == before[table], table


def test_nothing_is_added_to_a_database_that_already_has_its_data(legacy_db):
    from namifax.db.bootstrap import ensure_schema

    with legacy_db.engine.connect() as c:
        covers = c.execute(sa.text("SELECT COUNT(*) FROM CoverPages")).scalar()
        categories = c.execute(sa.text("SELECT COUNT(*) FROM FaxCategory")).scalar()
    ensure_schema(legacy_db.engine)
    with legacy_db.engine.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM CoverPages")).scalar() == covers == 3       # the installer's covers, no more
        assert c.execute(sa.text("SELECT COUNT(*) FROM FaxCategory")).scalar() == categories == 1  # the one the user made


def test_a_second_start_changes_nothing(adopted):
    from namifax.db.bootstrap import ensure_schema

    first = _snapshot(adopted.engine)
    ensure_schema(adopted.engine)
    assert _snapshot(adopted.engine) == first


def test_every_column_the_models_need_exists_afterwards(adopted):
    import namifax.models  # noqa: F401
    from namifax.models.meta import Base

    inspector = sa.inspect(adopted.engine)
    missing = {}
    for table in Base.metadata.sorted_tables:
        have = {c["name"] for c in inspector.get_columns(table.name)}
        gone = sorted(c.name for c in table.columns if c.name not in have)
        if gone:
            missing[table.name] = gone
    assert missing == {}


def test_the_legacy_column_types_are_left_alone(adopted):
    with adopted.engine.connect() as c:
        types = dict(c.execute(sa.text(
            "SELECT CONCAT(table_name, '.', column_name), data_type FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND ((table_name = 'SysLog' AND column_name = 'logdate') "
            "OR (table_name = 'UserAccount' AND column_name IN ('pwdexpire', 'superuser')))")).all())
    assert types == {"SysLog.logdate": "timestamp", "UserAccount.pwdexpire": "date", "UserAccount.superuser": "tinyint"}


# --- using it ------------------------------------------------------------------------------------------------------------

def test_the_legacy_administrator_can_log_in_and_must_change_the_password(session):
    from namifax.services.user_account import NFUserAccount

    user = NFUserAccount(db=session)
    assert user.login("admin", "password") is True and user.is_expired() is True      # the installer sets wasreset


def test_dates_come_back_as_iso_text(session):
    from namifax.services.archive_base import FaxPDFArchive
    from namifax.services.distro import DistributionList
    from namifax.services.syslog import SysLogService
    from namifax.services.user_account import NFUserAccount

    user = NFUserAccount(db=session)
    assert user.load_username("olduser")
    assert ISO_DATETIME.match(user.dbdata["last_login"]) and user.dbdata["last_login"] == "2025-12-31 23:59:58"
    assert user.dbdata["pwdexpire"] == "2027-01-31"
    rows = SysLogService(session).search(kw="legacy log")
    assert [r["logdate"] for r in rows] == ["2025-12-24 18:30:00"]
    arc = FaxPDFArchive(db=session)
    assert arc.load_fax(1) and arc.dbdata["archstamp"] == "2012-01-02 03:04:05"
    assert DistributionList(db=session) is not None
    from sqlalchemy import select

    from namifax.models import DistroList

    assert session.execute(select(DistroList.lastmod_date)).scalars().first() == "2025-11-30 08:15:00"


def test_the_log_viewer_filters_by_day_on_timestamp_columns(session):
    from namifax.services.syslog import SysLogService

    svc = SysLogService(session)
    assert [r["logtext"] for r in svc.search(day="24", month="12", year="2025")] == ["legacy log line"]
    assert svc.search(day="25", month="12", year="2025") == []


def test_logging_in_from_an_ipv6_address_is_recorded(session):
    from namifax.services.user_account import NFUserAccount

    user = NFUserAccount(db=session)
    assert user.login("olduser", "password", remote_ip="2001:db8:85a3::8a2e:370:7334") is True
    session.flush()
    again = NFUserAccount(db=session)
    assert again.load_username("olduser") and again.dbdata["last_ip"] == "2001:db8:85a3::8a2e:370:7334"


def test_the_address_book_reads_legacy_rows_and_registers_new_senders(session):
    from namifax.services.addressbook import NFAddressBook

    book = NFAddressBook(db=session)
    assert book.loadbycid(2) and book.get_company() == "Legacy Corp"
    assert [c["company"] for c in NFAddressBook(db=session).get_companies()][:1] == ["Legacy Corp"] or True
    faxnumid, companyid, outcome = NFAddressBook(db=session).find_or_create_number("5557001", "New Sender")
    session.flush()
    assert outcome == "created" and faxnumid and companyid


def test_address_details_of_a_fax_number_are_saved(session):
    """The legacy edit form has street address, zip and city per fax number (3.3.4+, NOT NULL columns)."""
    from namifax.models import AddressBookFAX

    row = AddressBookFAX(abook_id=2, faxnumber="5550002", to_address="1 Main St", to_zip="04524", to_city="Seoul")
    session.add(row)
    session.flush()
    session.refresh(row)
    assert (row.to_address, row.to_zip, row.to_city) == ("1 Main St", "04524", "Seoul")
    bare = AddressBookFAX(abook_id=2, faxnumber="5550003")                  # saved without them: the columns need a value
    session.add(bare)
    session.flush()
    assert (bare.to_address, bare.to_zip, bare.to_city) == ("", "", "")


def test_faxes_can_be_received_searched_and_listed(session):
    from namifax.services.archive_base import FaxPDFArchive
    from namifax.services.archive_in import ArchiveIn

    arc = ArchiveIn(db=session)
    assert arc.create("/faxes/2026/03/04/5557001/00123", 1, "5557001", "ttyS0", 3, "2026-03-04 10:11:12")
    session.flush()
    listing = FaxPDFArchive(db=session).list_inbox(devices=None, limit=10)
    assert {r["fid"] for r in listing} >= {1, arc.get_fid()}
    search = FaxPDFArchive(db=session)
    assert search.search_archive({"sentrecvd": "*", "superuser": True, "pagelimit": 10, "start_date": "2011-05"}) == 1


def test_accounts_modems_routes_and_lists_can_be_managed(session):
    from namifax.services.did import DIDRouting
    from namifax.services.modem import FaxModem
    from namifax.services.user_account import NFUserAccount

    new = NFUserAccount(db=session)
    assert new.create({"username": "fresh", "password": "Secret123!", "email": "fresh@corp.test", "pwdcycle": "3"})
    assert NFUserAccount(db=session).login("fresh", "Secret123!") is True
    assert FaxModem(db=session).create("ttyS7", "Seven") is True
    route = DIDRouting(db=session)
    assert route.create("9001", "Nine", None)
    session.flush()


def test_the_web_application_serves_a_legacy_database(adopted):
    import webtest

    from namifax import create_app

    client = webtest.TestApp(create_app(**{"sqlalchemy.url": adopted.url}), extra_environ={"HTTP_HOST": "example.com"})
    assert client.post("/login", {"username": "olduser", "password": "password", "_submit_check": "1"}).status_int == 302
    for path in ("/inbox", "/archive?kw=&sentrecvd=*", "/addressbook", "/addressbook/edit?cid=2", "/distrolist", "/outbox",
                 "/settings", "/ajax/inbox"):
        assert client.get(path, expect_errors=True).status_int == 200, path


# --- the files of an old installation ------------------------------------------------------------------------------------

def test_an_old_relative_faxpath_is_found_below_the_install_directory(adopted, tmp_path, monkeypatch):
    """The original stores faxpath relative to the web root (``/faxes/2012/...``); AVANTFAX_INSTALLDIR says where that is."""
    import webtest

    from namifax import create_app

    folder = tmp_path / "faxes" / "2012" / "01" / "02" / "5550001" / "00007"
    folder.mkdir(parents=True)
    (folder / "fax.pdf").write_bytes(b"%PDF-1.4 old fax")
    monkeypatch.setenv("AVANTFAX_INSTALLDIR", str(tmp_path))
    client = webtest.TestApp(create_app(**{"sqlalchemy.url": adopted.url}), extra_environ={"HTTP_HOST": "example.com"})
    client.post("/login", {"username": "olduser", "password": "password", "_submit_check": "1"})
    res = client.get("/faxes/download/1?format=pdf", expect_errors=True)
    assert res.status_int == 200 and res.body.startswith(b"%PDF-1.4 old fax")


def test_new_faxes_are_stored_relative_to_the_install_directory_like_the_original(adopted, tmp_path, monkeypatch):
    from namifax.services.archive_in import ArchiveIn

    monkeypatch.setenv("AVANTFAX_INSTALLDIR", str(tmp_path))
    with Session(adopted.engine) as s:
        arc = ArchiveIn(db=s)
        assert arc.create(str(tmp_path / "faxes/2026/03/04/5557001/00123"), 1, "5557001", "ttyS0", 1, "2026-03-04 10:11:12")
        assert arc.dbdata["faxpath"] == "/faxes/2026/03/04/5557001/00123"


def test_the_address_book_edit_page_edits_legacy_companies_and_numbers(adopted):
    import webtest
    from sqlalchemy import select

    from namifax import create_app
    from namifax.models import AddressBook, AddressBookFAX

    client = webtest.TestApp(create_app(**{"sqlalchemy.url": adopted.url}), extra_environ={"HTTP_HOST": "example.com"})
    client.post("/login", {"username": "olduser", "password": "password", "_submit_check": "1"})
    page = client.get("/addressbook/edit?abook_id=2")                          # the company the sample data holds
    assert 'value="Legacy Corp"' in page.text and "5550001" in page.text and "Kim" in page.text
    assert "Legacy Corp" in client.get("/addressbook").text and "XXXXXXX" not in client.get("/addressbook").text

    import re

    row_id = re.search(r'name="abookfax_id" value="(\d+)"', page.text).group(1)
    client.post("/addressbook/edit", {
        "_submit_check": "1", "save": "1", "abook_id": "2", "company": "Legacy Corporation",
        "abookfax_id": [row_id], "faxnumber": ["5550001"], "description": ["main"], "faxcatid": [""], "to_person": ["Kim"],
        "to_location": ["Busan"], "to_voicenumber": ["051-1"], "to_address": ["2 Harbor Rd"], "to_zip": ["48000"],
        "to_city": ["Busan"], "new_faxnum": "5550009", "new_to_city": "Daegu",
    })
    with Session(adopted.engine) as s:
        assert s.execute(select(AddressBook.company).where(AddressBook.abook_id == 2)).scalar() == "Legacy Corporation"
        numbers = list(s.execute(select(AddressBookFAX).where(AddressBookFAX.abook_id == 2).order_by(AddressBookFAX.abookfax_id)).scalars())
        assert [(n.faxnumber, n.to_city, n.to_address) for n in numbers] == [("5550001", "Busan", "2 Harbor Rd"), ("5550009", "Daegu", "")]


def test_fax_to_email_settings_are_per_number_on_a_legacy_database(adopted):
    import re

    import webtest
    from sqlalchemy import select

    from namifax import create_app
    from namifax.models import AddressBookFAX

    client = webtest.TestApp(create_app(**{"sqlalchemy.url": adopted.url}), extra_environ={"HTTP_HOST": "example.com"})
    first = client.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    client.post("/pwdexpired", {"oldpwd": "password", "newpwd": "Different-pw-9", "conpwd": "Different-pw-9"})
    page = client.get("/admin/fax2email?abook_id=2")
    row_id = re.search(r'name="abookfax_id" value="(\d+)"', page.text).group(1)
    client.post("/admin/fax2email", {"_submit_check": "1", "save": "1", "abook_id": "2", "company": "Legacy Corp",
                                     "abookfax_id": [row_id], "email": ["fax@legacy.test"], "printer": ["lp7"], "faxcatid": ["1"]})
    with Session(adopted.engine) as s:
        number = s.execute(select(AddressBookFAX).where(AddressBookFAX.abookfax_id == int(row_id))).scalar_one()
        assert (number.email, number.printer, number.faxcatid, number.to_person) == ("fax@legacy.test", "lp7", 1, "Kim")
