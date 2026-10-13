"""B track, group 3c: AddressBook, AddressBookFAX, AddressBookEmail on the legacy primary keys."""

from __future__ import annotations

import alembic.command
import pytest
import sqlalchemy as sa
from sqlalchemy import Integer, String
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.dialects.mysql.mariadb import MariaDBDialect
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from sqlsession import bare_session, empty_session, seeded_session

DIALECTS = [sqlite.dialect(), mysql.dialect(), MariaDBDialect(), postgresql.dialect()]
IDS = ["sqlite", "mysql", "mariadb", "postgresql"]


# --- models --------------------------------------------------------------------------------------

def test_models_use_the_legacy_primary_keys_and_leave_out_the_port_duplicates():
    import namifax.models as m

    ab, fax, email = m.AddressBook.__table__, m.AddressBookFAX.__table__, m.AddressBookEmail.__table__
    assert [c.name for c in ab.primary_key.columns] == ["abook_id"]
    assert [c.name for c in fax.primary_key.columns] == ["abookfax_id"]
    assert [c.name for c in email.primary_key.columns] == ["abookemail_id"]
    assert {"abook_id", "company"} <= set(ab.c.keys()) and "ab_id" not in ab.c
    assert {"abookfax_id", "abook_id", "faxnumber", "email", "description", "to_person", "to_location",
            "to_voicenumber", "to_address", "to_zip", "to_city", "faxcatid", "faxfrom", "faxto", "printer"} == set(fax.c.keys())
    assert set(email.c.keys()) == {"abookemail_id", "abook_id", "contact_name", "contact_email"}
    assert isinstance(getattr(ab.c.company.type, "impl", ab.c.company.type), String) and ab.c.company.type.length == 255
    assert not fax.c.faxnumber.nullable and not email.c.contact_email.nullable
    for table in (ab, fax, email):
        assert table.c[list(table.primary_key.columns)[0].name].autoincrement is True


@pytest.mark.parametrize("dialect", DIALECTS, ids=IDS)
@pytest.mark.parametrize("model", ["AddressBook", "AddressBookFAX", "AddressBookEmail"])
def test_ddl_compiles_for_every_supported_database(model, dialect):
    import namifax.models as models

    assert "PRIMARY KEY" in str(CreateTable(getattr(models, model).__table__).compile(dialect=dialect))


# --- the legacy SQLite schema --------------------------------------------------------------------

def _pk(db, table):
    db.query(f"SELECT name FROM pragma_table_info('{table}') WHERE pk = 1")
    return [r["name"] for r in db.get_records()]


def _cols(db, table):
    db.query(f"SELECT name FROM pragma_table_info('{table}')")
    return {r["name"] for r in db.get_records()}


def test_a_new_sqlite_database_has_the_legacy_keys_and_no_duplicate_columns(seeded_db):
    assert _pk(seeded_db, "AddressBook") == ["abook_id"]
    assert _pk(seeded_db, "AddressBookFAX") == ["abookfax_id"]
    assert _pk(seeded_db, "AddressBookEmail") == ["abookemail_id"]
    assert "ab_id" not in _cols(seeded_db, "AddressBook")
    assert not ({"fax_id", "ab_id", "default_num"} & _cols(seeded_db, "AddressBookFAX"))
    assert not ({"email_id", "ab_id", "to_person", "email", "default_email"} & _cols(seeded_db, "AddressBookEmail"))


def _port_v1_layout(db):
    """The layout older port versions created (ab_id was the real key, abook_id was filled at the next start)."""

    db.upgrade_schema()
    for t in ("AddressBook", "AddressBookFAX", "AddressBookEmail"):
        db.query(f"DROP TABLE {t}")
    db.query("CREATE TABLE AddressBook (ab_id INTEGER PRIMARY KEY AUTOINCREMENT, company TEXT, description TEXT, "
             "faxtype TEXT, faxnum TEXT, phonenum TEXT, email TEXT, address TEXT, city TEXT, state TEXT, zip TEXT, "
             "country TEXT, abook_id INTEGER)")
    db.query("CREATE TABLE AddressBookFAX (abookfax_id INTEGER PRIMARY KEY AUTOINCREMENT, fax_id INTEGER, abook_id INTEGER, "
             "ab_id INTEGER, faxnumber TEXT, to_person TEXT, default_num INTEGER DEFAULT 0, email TEXT, printer TEXT, "
             "faxcatid INTEGER, description TEXT, faxfrom INTEGER DEFAULT 0, faxto INTEGER DEFAULT 0)")
    db.query("CREATE TABLE AddressBookEmail (abookemail_id INTEGER PRIMARY KEY AUTOINCREMENT, email_id INTEGER, "
             "abook_id INTEGER, ab_id INTEGER, contact_name TEXT, to_person TEXT, contact_email TEXT, email TEXT, "
             "default_email INTEGER DEFAULT 0)")
    db.query("INSERT INTO AddressBook (ab_id, company, faxnum, abook_id) VALUES (3, 'Real Co', '555', 3)")
    db.query("INSERT INTO AddressBook (ab_id, company) VALUES (7, 'Never restarted Co')")        # abook_id still NULL
    db.query("INSERT INTO AddressBookFAX (abookfax_id, abook_id, ab_id, faxnumber) VALUES (1, NULL, 3, '5551111')")
    db.query("INSERT INTO AddressBookEmail (abookemail_id, abook_id, ab_id, contact_name, contact_email) "
             "VALUES (1, 7, 7, 'Jo', 'jo@x.test')")


def test_an_old_port_database_is_rebuilt_keeping_ids_and_links():

    db = bare_session()
    _port_v1_layout(db)
    db.upgrade_schema()

    assert _pk(db, "AddressBook") == ["abook_id"] and "ab_id" not in _cols(db, "AddressBook")
    db.query("SELECT abook_id, company, faxnum FROM AddressBook ORDER BY abook_id")
    assert db.get_records() == [{"abook_id": 3, "company": "Real Co", "faxnum": "555"},
                                {"abook_id": 7, "company": "Never restarted Co", "faxnum": None}]
    db.query("SELECT abook_id FROM AddressBookFAX WHERE abookfax_id = 1")
    assert db.get_records() == [{"abook_id": 3}]                   # link filled from ab_id
    db.query("SELECT abook_id FROM AddressBookEmail WHERE abookemail_id = 1")
    assert db.get_records() == [{"abook_id": 7}]
    # the key keeps counting from the old maximum
    db.query("INSERT INTO AddressBook (company) VALUES ('Next')")
    db.query("SELECT abook_id FROM AddressBook WHERE company = 'Next'")
    assert db.get_records() == [{"abook_id": 8}]


def test_rebuilding_twice_changes_nothing():

    db = bare_session()
    _port_v1_layout(db)
    db.upgrade_schema()
    db.query("SELECT * FROM AddressBook ORDER BY abook_id")
    first = db.get_records()
    db.upgrade_schema()
    db.query("SELECT * FROM AddressBook ORDER BY abook_id")
    assert db.get_records() == first


# --- repositories: conditional bulk update ---------------------------------------------------------

def test_update_where_on_both_repository_implementations(dbsession, seeded_db):
    from namifax.db.repository import Repository

    for backend in (dbsession, seeded_db):
        run = (lambda q: backend.execute(sa.text(q))) if backend is dbsession else (lambda q: backend.query(q))
        run("DELETE FROM AddressBookFAX")
        repo = Repository("AddressBookFAX", db=backend)
        for cid, num in ((1, "111"), (1, "222"), (2, "333")):
            repo.new_entry({"abook_id": cid, "faxnumber": num})
        assert repo.update_where({"abook_id": 1}, {"abook_id": 9}) == 2
        assert sorted(r["faxnumber"] for r in repo.find({"abook_id": 9}, reduce_single=False)) == ["111", "222"]
        assert repo.update_where({"abook_id": 99}, {"abook_id": 5}) == 0
        assert repo.update_where({}, {"abook_id": 5}) == 0 and repo.update_where({"abook_id": None}, {"abook_id": 5}) == 0


# --- the service on both backends --------------------------------------------------------------------

@pytest.fixture(params=["session", "engine"])
def ab(request, dbsession, seeded_db):
    from namifax.services.addressbook import NFAddressBook

    backend = dbsession if request.param == "session" else seeded_db
    for t in ("AddressBookFAX", "AddressBookEmail", "AddressBook"):
        (backend.execute(sa.text(f"DELETE FROM {t}")) if request.param == "session" else backend.query(f"DELETE FROM {t}"))
    return NFAddressBook(db=backend)


def _fresh(ab):
    return type(ab)(db=ab.db)


def test_a_new_company_can_be_loaded_by_its_id_right_away(ab):
    """Used to fail until the next server start filled the duplicate id column."""
    assert ab.create("Brand New Co") is True and ab.abook_id > 0
    other = _fresh(ab)
    assert other.loadbycid(ab.abook_id) is True and other.get_company() == "Brand New Co"
    assert other.loadbycid(str(ab.abook_id)) is True


def test_company_rules_rename_delete_and_listing(ab):
    for name in ("Zeta", "Alpha"):
        assert ab.create(name)
    assert ab.create("Alpha") is False and ab.error == "Company already exists"
    assert ab.create("") is False and ab.error == "You must enter a company name"
    assert [c["company"] for c in ab.get_companies()] == ["Alpha", "Zeta"]
    cid = [c for c in ab.get_companies() if c["company"] == "Alpha"][0]["abook_id"]
    other = _fresh(ab)
    assert other.loadbycid(cid) and other.set_company("Alpha Ltd") is True
    assert [c["company"] for c in other.get_companies()] == ["Alpha Ltd", "Zeta"]
    assert other.delete_cid(cid) is True and [c["company"] for c in other.get_companies()] == ["Zeta"]
    assert other.loadbycid(99999) is False


def test_search_companies(ab):
    ab.create("Acme Corp")
    ab.create("Initech")
    assert [c["company"] for c in ab.search_companies("acm corp")] == ["Acme Corp"]
    assert ab.search_companies("x'OR(1=1)--") == []


def test_fax_numbers_of_a_company(ab):
    ab.create("Acme")
    assert ab.create_faxnumid("(555) 010-100") is True and ab.get_faxnumber() == "555010100"
    assert ab.create_faxnumid("555-010-100") is False and ab.error == "Company already has this fax number"
    assert ab.create_faxnumid("") is False and ab.error == "fax number missing"
    ab.create_faxnumid("5559999")
    assert [f["faxnumber"] for f in ab.get_faxnums()] == ["555010100", "5559999"]

    fresh = _fresh(ab)
    assert fresh.loadbyfaxnumid(ab.get_faxnumid()) is True and fresh.get_faxnumber() == "5559999"
    assert fresh.loadbyfaxnumid(99999) is False and fresh.error == "No company configured for fax number"
    assert _fresh(ab).loadbyfaxnum("555-9999") == (True, False)


def test_a_fax_number_shared_by_two_companies_is_reported_as_multiple(ab):
    for name in ("One", "Two"):
        ab.create(name)
        ab.create_faxnumid("5551234")
    assert _fresh(ab).loadbyfaxnum("5551234") == (True, True)
    other = _fresh(ab)
    assert other.loadbyfaxnum("000") == (False, False) and "No company configured for fax number" in other.error


def test_fax_number_settings_counters_and_fax2email(ab):
    ab.create("Acme")
    ab.create_faxnumid("5551234")
    assert ab.has_fax2email() is False
    assert ab.save_settings({"description": "Main", "printer": "lp1", "faxcatid": 2, "email": "fax@acme.test",
                             "to_person": "Jane", "to_location": "HQ", "to_voicenumber": "555-0100"}) is True
    assert ab.inc_faxfrom() and ab.inc_faxfrom() and ab.inc_faxto()
    reloaded = _fresh(ab)
    assert reloaded.loadbyfaxnumid(ab.get_faxnumid())
    assert (reloaded.get_description(), reloaded.get_printer(), reloaded.get_category(), reloaded.get_email()) == (
        "Main", "lp1", 2, "fax@acme.test")
    assert (reloaded.get_faxfrom(), reloaded.get_faxto(), reloaded.get_to_person()) == (2, 1, "Jane")
    assert reloaded.totalfaxes() == (2, 1)
    assert _fresh(ab).loadbycid(ab.abook_id) and ab.has_fax2email() is True


def test_deleting_fax_numbers_and_reassigning_a_company(ab):
    ab.create("Old Co")
    old = ab.abook_id
    ab.create_faxnumid("5551111")
    ab.create_faxnumid("5552222")
    new = _fresh(ab)
    new.create("New Co")
    mover = _fresh(ab)
    assert mover.loadbycid(old) and mover.reassign(new.abook_id) is True
    assert [f["faxnumber"] for f in new.get_faxnums()] == ["5551111", "5552222"]   # numbers moved to the new company
    assert _fresh(ab).loadbycid(old) is False                                      # and the old one is gone
    assert mover.reassign(99999) is False and mover.error == "Invalid cid"

    new.delete_companyfaxids(new.abook_id)
    assert new.get_faxnums() == []
    new.create_faxnumid("5553333")
    assert new.delete_faxnumid(new.get_faxnumid()) is True and new.get_faxnums() == []


def test_email_contacts(ab):
    assert ab.create_contact("Jo", "not-an-email") is False and ab.error == "Please enter a valid e-mail address."
    assert ab.create_contact("", "jo@x.test") is False and ab.error == "You must enter a name."
    assert ab.create_contact("Zed", "zed@x.test") is True and ab.create_contact("Amy", "amy@x.test") is True
    assert ab.create_contact("Other", "amy@x.test") is False
    ab.create_contacts('Bob Marley <bob@x.test>; carol.smith@x.test; junk')
    contacts = list(_fresh(ab).get_contacts().values())
    assert set(contacts) == {'"Amy" <amy@x.test>', '"Bob Marley" <bob@x.test>', '"carol smith" <carol.smith@x.test>',
                             '"Zed" <zed@x.test>'}
    capitalised = [c for c in contacts if c[1].isupper()]
    assert capitalised == ['"Amy" <amy@x.test>', '"Bob Marley" <bob@x.test>', '"Zed" <zed@x.test>']   # collation decides the rest
    stepper = _fresh(ab)
    stepped = [stepper.make_contact_list_step()[1] for _ in range(4)]
    assert set(stepped) == {"Amy", "Bob Marley", "carol smith", "Zed"} and stepper.make_contact_list_step() is None


def test_updating_and_removing_a_contact(ab):
    ab.create_contact("Zed", "zed@x.test")
    eid = ab.email_array["abookemail_id"]
    other = _fresh(ab)
    assert other.load_contact_by_id(str(eid)) and other.update_contact("Zed Z", "zz@x.test") is True
    assert other.get_contact_name() == "Zed Z" and other.get_contact_email() == "zz@x.test"
    assert other.update_contact("", "zz@x.test") is False
    assert other.remove_contact(eid) is True and other.load_contact_by_id(eid) is False


def test_names_with_quotes_backslashes_and_unicode_round_trip(ab):
    tricky = "o'brien\\' OR 1=1 -- 한글"
    assert ab.create(tricky) is True and _fresh(ab).loadbycid(ab.abook_id)
    assert ab.create_faxnumid("5551234") and ab.create_contact(tricky, "t@x.test")
    assert [c["company"] for c in ab.get_companies()] == [tricky]


def test_phone_lookup_finds_the_company_by_fax_number(ab):
    from namifax.common.helpers import phone_lookup

    ab.create("Lookup Co")
    ab.create_faxnumid("5557777")
    ab.save_settings({"to_person": "Pat"})
    found = phone_lookup("555-7777", db=ab.db)
    assert found and found["company"] == "Lookup Co"
    assert phone_lookup("000", db=ab.db) is None


# --- real servers (optional) --------------------------------------------------------------------------

@pytest.mark.serverdb
def test_server_database_service(monkeypatch, server_db_url, alembic_cfg):
    from namifax.models import AddressBook, AddressBookEmail, AddressBookFAX
    from namifax.services.addressbook import NFAddressBook

    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(server_db_url)
    try:
        with Session(engine) as session:
            ab = NFAddressBook(db=session)
            assert ab.create("Acme") and ab.create_faxnumid("5551234") and ab.create_faxnumid("5559999")
            assert ab.save_settings({"description": "Main", "email": "f@x.test", "faxcatid": 3}) and ab.inc_faxfrom()
            other = NFAddressBook(db=session)
            assert other.create("한글 'q' \\x") and other.create_faxnumid("5551234")
            assert other.create_contact("Zed", "zed@x.test") and other.create_contacts("Amy <amy@x.test>") is None
            assert [c["company"] for c in other.search_companies("acm")] == ["Acme"]
            assert NFAddressBook(db=session).loadbyfaxnum("5551234") == (True, True)
            mover = NFAddressBook(db=session)
            assert mover.loadbycid(ab.abook_id) and mover.reassign(other.abook_id) is True
            session.commit()
        with Session(engine) as session:
            count = lambda m: session.execute(sa.select(sa.func.count()).select_from(m)).scalar()  # noqa: E731
            assert (count(AddressBook), count(AddressBookFAX), count(AddressBookEmail)) == (1, 3, 2)
            assert list(NFAddressBook(db=session).get_contacts().values()) == ['"Amy" <amy@x.test>', '"Zed" <zed@x.test>']
    finally:
        engine.dispose()
