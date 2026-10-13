"""The address book suggestion (the original's ajaxbook.php): one row per fax number, as "Company (description) - number", with the
company id (``cid``), the number (``faxnum``) and the id of that number (``fnid``). The placeholder company that keeps the faxes
of deleted companies, and companies without a number, are not offered."""

from __future__ import annotations

import re

import pytest

from namifax.models import AddressBook, AddressBookFAX
from namifax.services.addressbook import RESERVED_FAX_NUM


@pytest.fixture
def book(testapp, dbsession):
    ids = {}
    for company, numbers in (("Rows Co", [("111", "Head office"), ("222", None)]), ("Empty Co", []),
                             ("Amp & Co", [("333", "<main>")]), (RESERVED_FAX_NUM, [(RESERVED_FAX_NUM, None)])):
        ab = AddressBook(company=company)
        dbsession.add(ab)
        dbsession.flush()
        for number, description in numbers:
            row = AddressBookFAX(abook_id=ab.abook_id, faxnumber=number, description=description)
            dbsession.add(row)
            dbsession.flush()
            ids[(company, number)] = (ab.abook_id, row.abookfax_id)
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return ids


def _rows(testapp, query):
    xml = testapp.get(f"/ajax/book?q={query}").text
    return [dict(re.findall(r"<(\w+)>(.*?)</\1>", row)) for row in re.findall(r"<row>(.*?)</row>", xml, re.S)]


def test_every_number_of_a_company_is_a_row(testapp, book):
    rows = _rows(testapp, "Rows")
    assert [r["company"] for r in rows] == ["Rows Co (Head office) - 111", "Rows Co - 222"]
    assert [r["faxnum"] for r in rows] == ["111", "222"]


def test_a_row_carries_the_company_and_the_number_id(testapp, book):
    rows = _rows(testapp, "Rows")
    assert [(int(r["cid"]), int(r["fnid"])) for r in rows] == [book[("Rows Co", "111")], book[("Rows Co", "222")]]


def test_a_company_without_a_number_is_not_offered(testapp, book):
    assert _rows(testapp, "Empty") == []


def test_the_placeholder_company_is_not_offered(testapp, book):
    assert _rows(testapp, RESERVED_FAX_NUM) == []


def test_the_text_is_escaped_for_xml(testapp, book):
    assert [r["company"] for r in _rows(testapp, "Amp")] == ["Amp &amp; Co (&lt;main&gt;) - 333"]
