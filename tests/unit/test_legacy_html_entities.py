"""Text written by the original AvantFAX is stored as HTML entities (``M&uuml;ller``, ``&amp;``, ``&#039;``): the original ran every
form value through htmlentities(ENT_QUOTES, "UTF-8") and let the browser draw the letters. NamiFAX shows the letters: the entities
are undone when the text is read, the database is left as it is, and what NamiFAX writes is plain UTF-8, which the original also
shows correctly. Searches find the entity form of a word as well."""

from __future__ import annotations

import re
from urllib.parse import quote

import pytest
from sqlalchemy import text

from namifax.models import AddressBook, AddressBookEmail, AddressBookFAX, FaxArchive, FaxCategory, Modems
from namifax.models.types import LegacyHtmlString, LegacyHtmlText, legacy_decode, legacy_encode

STORED_COMPANY = "M&uuml;ller &amp; S&ouml;hne GmbH"
SHOWN_COMPANY = "Müller & Söhne GmbH"


# --- the two directions ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("stored,shown", [
    (STORED_COMPANY, SHOWN_COMPANY),
    ("Soporte L&iacute;nea 2", "Soporte Línea 2"),
    ("O&#039;Brien &quot;Bob&quot; &lt;b&gt;", "O'Brien \"Bob\" <b>"),
    ("&#44608;&#44600;&#46041;", "김길동"),
    ("&euro;100 &ndash; &Ntilde;and&uacute;", "€100 – Ñandú"),
    ("Schäfer 한글 plain UTF-8", "Schäfer 한글 plain UTF-8"),
    ("Smith & Sons", "Smith & Sons"),
    ("AT&T Q&A", "AT&T Q&A"),
    ("&notanentity; &#xZZ; &notice &copy", "&notanentity; &#xZZ; &notice &copy"),
    ("&#xFC;ber &#9731; &#0; &#55296;", "über ☃ &#0; &#55296;"),
    ("", ""),
])
def test_stored_entities_are_undone(stored, shown):
    assert legacy_decode(stored) == shown


def test_nothing_is_done_to_a_value_that_is_not_text():
    assert legacy_decode(None) is None


def test_the_original_encoding_is_reproduced_for_searching():
    assert legacy_encode("Müller & Söhne 'x' \"y\" <b> 한글 €") == \
        "M&uuml;ller &amp; S&ouml;hne &#039;x&#039; &quot;y&quot; &lt;b&gt; 한글 &euro;"


@pytest.mark.parametrize("text_", ["Müller & Söhne", "O'Brien \"Bob\"", "한글 plain", "&amp; already", "x"])
def test_decoding_what_the_original_wrote_gives_back_the_text(text_):
    assert legacy_decode(legacy_encode(text_)) == text_


@pytest.mark.parametrize("dialect", ["sqlite", "mysql", "postgresql"])
@pytest.mark.parametrize("column_type", [LegacyHtmlString(255), LegacyHtmlText()])
def test_every_database_dialect_keeps_the_decoding(dialect, column_type):
    """A dialect with its own string type (PostgreSQL's psycopg one) must not replace the type and lose the decoding."""
    from sqlalchemy.dialects import mysql, postgresql, sqlite

    chosen = {"sqlite": sqlite.dialect(), "mysql": mysql.dialect(), "postgresql": postgresql.psycopg.dialect()}[dialect]
    process = column_type.dialect_impl(chosen).result_processor(chosen, None)
    assert process("M&uuml;ller &amp; S&ouml;hne") == "Müller & Söhne"


# --- the screens -------------------------------------------------------------------------------------------------------------

@pytest.fixture
def client(testapp, dbsession):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    book = AddressBook(company=STORED_COMPANY)
    dbsession.add(book)
    dbsession.flush()
    dbsession.add(AddressBookFAX(abook_id=book.abook_id, faxnumber="+49305550101", description="Buchhaltung f&uuml;r M&auml;rz",
                                 to_person="Hans M&uuml;ller"))
    dbsession.add(AddressBookEmail(contact_name="Hans M&uuml;ller", contact_email="hans@mueller.example"))
    dbsession.add(FaxCategory(name="Vertrieb M&uuml;ller"))
    dbsession.add(Modems(device="ttyS9", alias="Soporte L&iacute;nea 2"))
    dbsession.flush()
    testapp.book_id = book.abook_id
    return testapp


def _shown(client, path):
    html = client.get(path).text
    assert not re.search(r"&amp;(?:[A-Za-z]+|#\d+);", html), f"{path} still shows an entity as text"
    return html


def test_the_address_book_shows_the_letters(client):
    assert "Müller &amp; Söhne GmbH" in _shown(client, "/addressbook")


def test_the_e_mail_book_shows_the_letters(client):
    assert "Hans Müller" in _shown(client, "/emailbook")


def test_the_category_and_modem_lists_show_the_letters(client):
    assert "Vertrieb Müller" in _shown(client, "/admin/categories")
    assert "Soporte Línea 2" in _shown(client, "/admin/modems")


def test_the_company_edit_page_has_the_letters_in_its_fields(client):
    html = _shown(client, f"/addressbook/edit?abook_id={client.book_id}")
    assert 'value="Müller &amp; Söhne GmbH"' in html
    assert "Buchhaltung für März" in html and "Hans Müller" in html


def test_the_suggestion_list_gives_the_letters(client):
    xml = client.get("/ajax/book?q=" + quote("Mü")).text
    assert "Müller &amp; Söhne GmbH (Buchhaltung für März) - +49305550101" in xml


# --- searching ---------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("query", ["Müller", "müller", "söhne", "Müller & Söhne", "Mül", "muller"])
def test_a_search_finds_a_word_the_original_stored_as_entities(client, query):
    found = "Müller" in client.get("/ajax/book?q=" + quote(query)).text
    assert found is (query != "muller"), query            # "muller" is another word than "müller"


def test_a_plain_search_still_works(client):
    assert "Müller" in client.get("/ajax/book?q=GmbH").text


def test_the_archive_keyword_search_finds_entities_in_a_note(client, dbsession, tmp_path):
    folder = tmp_path / "f1"
    folder.mkdir()
    (folder / "fax.pdf").write_bytes(b"%PDF-1.4 x")
    dbsession.add(FaxArchive(faxpath=str(folder), pages=1, inbox=0, archstamp="2026-03-01 10:00:00", modemdev="ttyS9",
                             description="Rechnung f&uuml;r M&auml;rz"))
    dbsession.flush()
    page = client.get("/archive?kw=f%C3%BCr+M%C3%A4rz&opensearch=1&sentrecvd=r").text
    assert "Rechnung für März" in page and "&amp;uuml;" not in page


# --- what NamiFAX writes -----------------------------------------------------------------------------------------------------

def _raw_company(dbsession, book_id):
    return dbsession.execute(text("SELECT company FROM AddressBook WHERE abook_id = :i"), {"i": book_id}).scalar()


def test_a_changed_company_is_stored_as_plain_utf8(client, dbsession):
    res = client.post("/addressbook/edit", {"_submit_check": "1", "abook_id": str(client.book_id), "company": SHOWN_COMPANY + " AG",
                                            "save": "Save"}, expect_errors=True)
    assert res.status_int in (200, 302)
    assert _raw_company(dbsession, client.book_id) == SHOWN_COMPANY + " AG"
    assert "Müller &amp; Söhne GmbH AG" in _shown(client, "/addressbook")


def test_a_company_that_was_not_changed_is_left_as_the_original_wrote_it(client, dbsession):
    client.post("/addressbook/edit", {"_submit_check": "1", "abook_id": str(client.book_id), "company": SHOWN_COMPANY, "save": "Save"},
                expect_errors=True)
    assert _raw_company(dbsession, client.book_id) == STORED_COMPANY


def test_a_new_company_with_an_ampersand_is_stored_and_shown_as_typed(client, dbsession):
    client.post("/addressbook/edit", {"_submit_check": "1", "company": "Smith & Sons <Ltd>", "faxnumber": "5550123"})
    raw = dbsession.execute(text("SELECT company FROM AddressBook WHERE company LIKE 'Smith%'")).scalar()
    assert raw == "Smith & Sons <Ltd>"
    assert "Smith &amp; Sons &lt;Ltd&gt;" in client.get("/addressbook").text


def test_a_value_is_never_trusted_as_html(client, dbsession):
    dbsession.add(AddressBook(company="&lt;script&gt;alert(1)&lt;/script&gt;"))
    dbsession.flush()
    html = client.get("/addressbook").text
    assert "<script>alert(1)" not in html and "&lt;script&gt;alert(1)&lt;/script&gt;" in html
