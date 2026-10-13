"""vCard uploads for the e-mail book and the address book (the original upload_contacts.php / upload_faxcontacts.php)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from namifax.models import AddressBook, AddressBookEmail, AddressBookFAX

CARD = "BEGIN:VCARD\nVERSION:2.1\n{}\nEND:VCARD\n"


def _cards(*cards):
    return "".join(CARD.format("\n".join(lines)) for lines in cards).encode()


@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


def _upload(client, path, data, **fields):
    form = {"_submit_check": "1", **fields}
    return client.post(path, form, upload_files=[("upload", "contacts.vcf", data)])


def _companies(session):
    session.expire_all()
    return {r.company: r for r in session.execute(select(AddressBook)).scalars()}


# --- e-mail book -----------------------------------------------------------------------------------------------------------

def test_every_email_line_of_a_card_with_a_name_is_imported_and_counted(client, dbsession):
    res = _upload(client, "/upload/contacts", _cards(
        ["FN:Alice Upload", "EMAIL;INTERNET;WORK:alice@upload.test"],
        ["FN:Bob Upload", "EMAIL;INTERNET:bob@upload.test"]))
    assert "Successfully uploaded 2 contacts" in res.text
    rows = {r.contact_email: r.contact_name for r in dbsession.execute(select(AddressBookEmail)).scalars()}
    assert rows["alice@upload.test"] == "Alice Upload" and rows["bob@upload.test"] == "Bob Upload"


def test_an_address_that_is_already_in_the_book_is_not_counted(client, dbsession):
    _upload(client, "/upload/contacts", _cards(["FN:Alice Upload", "EMAIL;INTERNET:alice@upload.test"]))
    res = _upload(client, "/upload/contacts", _cards(["FN:Alice Upload", "EMAIL;INTERNET:alice@upload.test"]))
    assert "Successfully uploaded 0 contacts" in res.text
    assert len([r for r in dbsession.execute(select(AddressBookEmail)).scalars() if r.contact_email == "alice@upload.test"]) == 1


def test_an_address_without_a_name_is_skipped(client, dbsession):
    res = _upload(client, "/upload/contacts", _cards(["EMAIL;INTERNET:nobody@upload.test"]))
    assert "Successfully uploaded 0 contacts" in res.text
    assert not [r for r in dbsession.execute(select(AddressBookEmail)).scalars() if r.contact_email == "nobody@upload.test"]


def test_a_file_that_is_not_a_vcard_is_refused(client, dbsession):
    res = _upload(client, "/upload/contacts", b"just some text, no card in here\n")
    assert "vCard file problem" in res.text and "Successfully uploaded" not in res.text


# --- address book ----------------------------------------------------------------------------------------------------------------

def test_a_fax_card_makes_a_company_with_its_number_person_and_category(client, dbsession):
    res = _upload(client, "/upload/faxcontacts", _cards(["FN:Wayne Boss", "ORG:Wayne Enterprises;", "TEL;WORK;FAX:+15550144"]),
                  catid="1")
    assert "Successfully uploaded 1 contacts" in res.text
    company = _companies(dbsession)["Wayne Enterprises"]
    number = dbsession.execute(select(AddressBookFAX).where(AddressBookFAX.abook_id == company.abook_id)).scalar_one()
    assert (number.faxnumber, number.to_person, number.faxcatid) == ("+15550144", "Wayne Boss", 1)


def test_a_card_without_an_organisation_uses_the_person_as_company(client, dbsession):
    _upload(client, "/upload/faxcontacts", _cards(["FN:Solo Person", "TEL;FAX:+15550145"]))
    assert "Solo Person" in _companies(dbsession)


def test_the_organisation_of_one_card_does_not_leak_into_the_next(client, dbsession):
    _upload(client, "/upload/faxcontacts", _cards(
        ["FN:First", "ORG:Acme Upload", "TEL;FAX:+15550150"],
        ["FN:Second Person", "TEL;FAX:+15550151"]))
    companies = _companies(dbsession)
    assert "Second Person" in companies
    numbers = {n.faxnumber for n in dbsession.execute(select(AddressBookFAX).where(
        AddressBookFAX.abook_id == companies["Acme Upload"].abook_id)).scalars()}
    assert numbers == {"+15550150"}


def test_a_card_with_neither_name_nor_organisation_is_skipped(client, dbsession):
    before = set(_companies(dbsession))
    res = _upload(client, "/upload/faxcontacts", _cards(["TEL;FAX:+15550160"]))
    assert "Successfully uploaded 0 contacts" in res.text and set(_companies(dbsession)) == before


def test_email_lines_in_a_fax_upload_go_to_the_email_book_without_being_counted(client, dbsession):
    res = _upload(client, "/upload/faxcontacts", _cards(
        ["FN:Mail Person", "ORG:Mail Org", "EMAIL;INTERNET:mail@upload.test", "TEL;FAX:+15550170"]))
    assert "Successfully uploaded 1 contacts" in res.text
    assert [r.contact_name for r in dbsession.execute(select(AddressBookEmail)).scalars() if r.contact_email == "mail@upload.test"] == ["Mail Person"]


def test_the_fax_upload_refuses_a_file_that_is_not_a_vcard(client):
    assert "vCard file problem" in _upload(client, "/upload/faxcontacts", b"hello").text


def test_posting_without_a_file_reports_nothing_uploaded(client):
    res = client.post("/upload/faxcontacts", {"_submit_check": "1"})
    assert res.status_int == 200 and "Successfully uploaded 0 contacts" in res.text


# --- the forms are reachable ----------------------------------------------------------------------------------------------------

def test_the_new_company_page_offers_the_upload(client):
    page = client.get("/addressbook/edit")
    assert 'action="/upload/faxcontacts"' in page.text and 'enctype="multipart/form-data"' in page.text and 'name="upload"' in page.text


def test_the_new_email_contact_page_offers_the_upload(client):
    page = client.get("/emailbook/edit")
    assert 'action="/upload/contacts"' in page.text and 'enctype="multipart/form-data"' in page.text and 'name="upload"' in page.text


def test_editing_an_existing_entry_does_not_offer_the_upload(client, dbsession):
    existing = dbsession.execute(select(AddressBookEmail)).scalars().first()
    assert existing is not None
    assert "/upload/contacts" not in client.get(f"/emailbook/edit?abookemail_id={existing.abookemail_id}").text
