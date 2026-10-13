"""E-mail a fax as a PDF (the original email.php): defaults, recipients, CC/BCC, file name, category, archive after sending."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from bs4 import BeautifulSoup
from sqlalchemy import select

from namifax.models import AddressBook, AddressBookEmail, AddressBookFAX, FaxArchive, FaxCategory, UserAccount
from test_fax_access_control import _login, world  # noqa: F401  (alice: ttyS0 + category 1; bob: ttyS1; root: superuser)


@pytest.fixture
def sent():
    calls = []

    def fake(to, from_addr, subject, text, **kw):
        calls.append({"to": to, "from": from_addr, "subject": subject, "text": text, **kw})
        return fake.result

    fake.result = True
    with patch("namifax.views.modals.send_mail", fake):
        yield calls, fake


@pytest.fixture
def categories(world):
    """The categories of the test database (the demo ones), in id order; alice's account lists category 1."""
    rows = list(world.db.execute(select(FaxCategory).order_by(FaxCategory.catid)).scalars())
    assert len(rows) >= 2 and rows[0].catid == 1
    return rows


def _company(world, key="A", name="Acme Corp"):
    book = AddressBook(company=name)
    world.db.add(book)
    world.db.flush()
    number = AddressBookFAX(abook_id=book.abook_id, faxnumber="5550100")
    world.db.add(number)
    world.db.flush()
    world.db.get(FaxArchive, world.fax[key]).faxnumid = number.abookfax_id
    world.db.flush()


def _form(page):
    return next(f for f in page.forms.values() if "emails" in f.fields)


def _field(page, name):
    return BeautifulSoup(page.text, "html.parser").find(["input", "textarea", "select"], {"name": name})


# --- the form ---------------------------------------------------------------------------------------------------------------

def test_the_defaults_are_the_original_ones(world):
    _company(world)
    alice = world.db.execute(select(UserAccount).where(UserAccount.username == "alice")).scalar_one()
    alice.email_sig = "-- Alice"
    world.db.flush()
    page = _login(world, "alice").get(f"/email?fid={world.fax['A']}")
    form = _form(page)
    assert form["subject"].value == "Acme Corp" and form["filename"].value == "fax-Acme-Corp.pdf"
    assert form["msg"].value.replace("\r", "").endswith("\n\n-- Alice")        # (a browser drops the first newline of a textarea)
    assert "Alice &lt;alice@corp.test&gt;" in page.text and form["fid"].value == str(world.fax["A"])


def test_without_an_address_book_entry_the_number_names_the_fax(world):
    world.db.get(FaxArchive, world.fax["A"]).origfaxnum = "555:0199"
    world.db.flush()
    form = _form(_login(world, "alice").get(f"/email?fid={world.fax['A']}"))
    assert form["subject"].value == "555:0199" and form["filename"].value == "fax-5550199.pdf"       # ':' and ' ' are not kept


def test_the_form_has_cc_bcc_and_a_subject_limit(world):
    page = _login(world, "alice").get(f"/email?fid={world.fax['A']}")
    for name in ("emails", "cc_emails", "bcc_emails", "subject", "filename", "msg", "fid", "url"):
        assert _field(page, name) is not None, name
    assert _field(page, "subject")["maxlength"] == "45"


def test_an_inbox_fax_offers_the_users_categories_and_archiving(world, categories):
    page = _login(world, "alice").get(f"/email?fid={world.fax['A']}")
    options = {o["value"]: o.get_text(strip=True) for o in _field(page, "category").find_all("option")}
    assert options == {"": "", str(categories[0].catid): categories[0].name}                    # alice may use category 1 only
    assert _field(page, "archive").has_attr("checked")


def test_a_superuser_is_offered_every_category(world, categories):
    page = _login(world, "root").get(f"/email?fid={world.fax['A']}")
    assert {o["value"] for o in _field(page, "category").find_all("option")} == {"", *(str(c.catid) for c in categories)}


def test_an_archived_fax_has_no_category_or_archive_choice(world):
    world.db.get(FaxArchive, world.fax["A"]).inbox = 0
    world.db.flush()
    page = _login(world, "alice").get(f"/email?fid={world.fax['A']}")
    assert _field(page, "category") is None and _field(page, "archive") is None


@pytest.mark.parametrize("user,fid", [("bob", "A"), ("carl", "A")])
def test_without_the_right_to_the_fax_the_user_goes_to_the_inbox(world, user, fid):
    res = _login(world, user).get(f"/email?fid={world.fax[fid]}")
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox")


def test_an_unknown_fax_goes_to_the_inbox(world):
    res = _login(world, "alice").get("/email?fid=99999")
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox")


# --- sending ----------------------------------------------------------------------------------------------------------------

def _submit(world, user="alice", key="A", **fields):
    client = _login(world, user)
    form = _form(client.get(f"/email?fid={world.fax[key]}", headers={"Referer": "http://example.com/inbox"}))
    for name, value in fields.items():
        form[name] = value
    return form.submit()


def test_sending_hands_everything_to_send_mail(world, sent, categories):
    calls, _ = sent
    _company(world)
    res = _submit(world, emails="x@client.test", cc_emails="cc@client.test", bcc_emails="bcc@client.test", subject="Hello",
                  msg="Please see attached", filename="contract.pdf")
    (call,) = calls
    assert call["to"] == "x@client.test" and call["cc"] == "cc@client.test" and call["bcc"] == "bcc@client.test"
    assert call["from"] == '"Alice" <alice@corp.test>' and call["subject"] == "Hello" and call["text"] == "Please see attached"
    assert call["file"].endswith("/A/fax.pdf") and call["altname"] == "contract.pdf" and call["embedd"].endswith("thumb.png")
    assert call["session"] is not None                                        # mail settings come from the database
    assert res.status_int == 200 and "sent" in res.text.lower() and "http://example.com/inbox" in res.text


def test_a_sent_fax_is_archived_and_given_the_category_when_asked(world, sent, categories):
    _submit(world, emails="x@client.test", category=str(categories[0].catid))
    world.db.expire_all()
    fax = world.db.get(FaxArchive, world.fax["A"])
    assert fax.inbox == 0 and fax.faxcatid == categories[0].catid


def test_unchecking_archive_leaves_the_fax_in_the_inbox(world, sent):
    client = _login(world, "alice")
    form = _form(client.get(f"/email?fid={world.fax['A']}"))
    form["emails"], form["archive"] = "x@client.test", False
    form.submit()
    world.db.expire_all()
    assert world.db.get(FaxArchive, world.fax["A"]).inbox == 1


def test_new_recipients_are_added_to_the_email_book(world, sent):
    _submit(world, emails="fresh@client.test")
    assert world.db.execute(select(AddressBookEmail).where(AddressBookEmail.contact_email == "fresh@client.test")).first() is not None


def test_no_recipient_is_an_error_and_nothing_is_sent(world, sent):
    calls, _ = sent
    res = _submit(world, emails="  ")
    assert calls == [] and "valid e-mail address" in res.text


def test_a_malformed_recipient_is_an_error_and_nothing_is_sent(world, sent):
    calls, _ = sent
    res = _submit(world, emails="x@client.test, not-an-address")
    assert calls == [] and "not-an-address" in res.text


def test_a_failed_send_reports_it_and_changes_nothing(world, sent):
    calls, fake = sent
    fake.result = False
    res = _submit(world, emails="x@client.test")
    assert "failed" in res.text.lower()
    world.db.expire_all()
    assert world.db.get(FaxArchive, world.fax["A"]).inbox == 1


def test_a_fax_without_its_pdf_is_not_mailed_without_an_attachment(world, sent):
    calls, _ = sent
    import os
    os.remove(world.db.get(FaxArchive, world.fax["A"]).faxpath + "/fax.pdf")
    res = _submit(world, emails="x@client.test")
    assert calls == [] and res.status_int == 200 and "not found" in res.text.lower()


def test_a_user_without_the_right_cannot_send_it(world, sent):
    calls, _ = sent
    client = _login(world, "bob")
    res = client.post("/email", {"fid": str(world.fax["A"]), "emails": "x@client.test", "_submit_check": "1"}, expect_errors=True)
    assert calls == [] and res.status_int in (302, 403)
