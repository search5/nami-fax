"""SQL injection through the address book search box (ajax auto-suggest)."""

from __future__ import annotations

import pytest

from namifax.services.addressbook import NFAddressBook

PAYLOADS = [
    "x'OR(1=1)--",
    "x'/**/OR/**/1=1--",
    "zzz' UNION SELECT uid, password, username, email, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL FROM UserAccount --",
    "' OR ''='",
    "x\\' OR 1=1 --",
]


@pytest.fixture
def ab(seeded_db):
    return NFAddressBook(db=seeded_db)


def test_a_normal_search_still_works(ab):
    assert [r["company"] for r in ab.search_companies("acme")] == ["Acme Corp"]
    assert [r["company"] for r in ab.search_companies("ACME")] == ["Acme Corp"]
    assert ab.search_companies("nothing-like-this") == []


def test_several_words_match_in_order_like_the_legacy_search(ab):
    assert [r["company"] for r in ab.search_companies("acm corp")] == ["Acme Corp"]
    assert ab.search_companies("corp acm") == []


@pytest.mark.parametrize("payload", PAYLOADS)
def test_injection_payloads_are_only_text(ab, payload):
    assert ab.search_companies(payload) == []


def test_user_data_cannot_be_read_through_the_search(ab, seeded_db):
    seeded_db.query("SELECT password FROM UserAccount WHERE username = 'admin'")
    admin_hash = seeded_db.get_records()[0]["password"]
    for payload in PAYLOADS:
        assert admin_hash not in str(ab.search_companies(payload))


def test_wildcards_typed_by_the_user_are_literal(ab, seeded_db):
    seeded_db.query("INSERT INTO AddressBook (company) VALUES ('100% Fax Ltd')")
    seeded_db.query("INSERT INTO AddressBook (company) VALUES ('100 Fax Ltd')")
    assert [r["company"] for r in ab.search_companies("100%")] == ["100% Fax Ltd"]
    assert [r["company"] for r in ab.search_companies("100_f")] == []


def test_the_search_sql_is_not_built_from_user_text():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[2] / "src/namifax/services/addressbook.py").read_text()
    assert "LIKE '%{" not in src
