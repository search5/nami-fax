"""P3: a freshly created database is fully seeded on the very first initialisation."""

from __future__ import annotations

from sqlsession import bare_session, empty_session, seeded_session


def test_first_init_links_seed_fax_to_company_without_second_init():
    db = bare_session()
    db.upgrade_schema()
    db.query("SELECT a.company FROM FaxArchive f JOIN AddressBook a ON a.abook_id = f.companyid WHERE f.fid = 1")
    assert db.get_records() == [{"company": "Acme Corp"}]


def test_second_init_is_idempotent():
    db = bare_session()
    db.upgrade_schema()
    db.query("SELECT COUNT(*) AS n FROM FaxArchive")
    first = db.get_records()[0]["n"]
    db.upgrade_schema()
    db.query("SELECT COUNT(*) AS n FROM FaxArchive")
    assert db.get_records()[0]["n"] == first
