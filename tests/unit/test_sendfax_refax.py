"""Send Fax > "Reply to fax" (sendfax?refax=<fid>), the original refax.php.

The fax is looked up (and the user's right to it checked) before anything is shown; the sender's number is filled in unless
it is empty or the reserved one; the original PDF travels with the new fax. Without the right, or for a fax that does not
exist, the user lands on the plain Send Fax page (as in the original).
"""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest

from namifax.models import AddressBook, AddressBookFAX
from test_fax_access_control import _fax, _login, _user, world  # noqa: F401  (same users and faxes)


@pytest.fixture
def sent(world):
    """Captures what the page would hand to HylaFAX instead of running it."""
    calls = []

    def fake(send, sender):
        calls.append(send)
        return {"success": True}

    with patch("namifax.views.sendfax.dispatch_sendfax", fake):
        yield calls


def _number(world, fax_key, faxnumber, company="Acme"):
    ab = AddressBook(company=company)
    world.db.add(ab)
    world.db.flush()
    num = AddressBookFAX(abook_id=ab.abook_id, faxnumber=faxnumber)
    world.db.add(num)
    world.db.flush()
    from namifax.models import FaxArchive
    fax = world.db.get(FaxArchive, world.fax[fax_key])
    fax.faxnumid, fax.companyid, fax.origfaxnum = num.abookfax_id, ab.abook_id, "ignored"
    world.db.flush()


def _field(page, name):
    form = page.forms[0] if page.forms else None
    return form[name].value if form and name in form.fields else None


def test_the_sender_number_from_the_address_book_is_filled_in(world):
    _number(world, "A", "+1-555-0100")
    page = _login(world, "alice").get(f"/sendfax?refax={world.fax['A']}")
    assert re.search(r'name="faxnumber"[^>]*value="\+1-555-0100"', page.text)


def test_without_an_address_book_entry_the_received_number_is_used(world):
    from namifax.models import FaxArchive
    world.db.get(FaxArchive, world.fax["A"]).origfaxnum = "5550123"
    world.db.flush()
    assert 'value="5550123"' in _login(world, "alice").get(f"/sendfax?refax={world.fax['A']}").text


@pytest.mark.parametrize("number", ["", "unknown", "XXXXXXX"])
def test_a_number_without_digits_or_the_reserved_one_is_left_blank(world, number):
    from namifax.models import FaxArchive
    world.db.get(FaxArchive, world.fax["A"]).origfaxnum = number
    world.db.flush()
    page = _login(world, "alice").get(f"/sendfax?refax={world.fax['A']}")
    assert number == "" or number not in page.text.split('name="faxnumber"', 1)[1].split(">", 1)[0]


def test_the_page_shows_the_original_and_keeps_its_id_in_the_form(world):
    page = _login(world, "alice").get(f"/sendfax?refax={world.fax['A']}")
    assert f'name="refax" value="{world.fax["A"]}"' in page.text
    assert f"/faxes/download/{world.fax['A']}?format=pdf" in page.text


@pytest.mark.parametrize("user", ["bob", "carl"])
def test_a_fax_without_the_right_is_not_offered(world, user):
    res = _login(world, user).get(f"/sendfax?refax={world.fax['A']}")
    assert res.status_int == 302 and res.headers["Location"].endswith("/sendfax")


def test_an_unknown_fax_goes_back_to_the_plain_page(world):
    res = _login(world, "alice").get("/sendfax?refax=99999")
    assert res.status_int == 302 and res.headers["Location"].endswith("/sendfax")


def test_a_superuser_may_reply_to_any_fax(world):
    assert _login(world, "root").get(f"/sendfax?refax={world.fax['B']}").status_int == 200


def test_sending_attaches_the_original_pdf(world, sent):
    res = _login(world, "alice").post("/sendfax", {"_submit_check": "1", "faxnumber": "5550100", "refax": str(world.fax["A"])})
    assert res.status_int == 302
    assert len(sent) == 1 and sent[0].files[0].endswith("/A/fax.pdf")


def test_sending_without_the_right_does_not_attach_or_send(world, sent):
    res = _login(world, "bob").post("/sendfax", {"_submit_check": "1", "faxnumber": "5550100", "refax": str(world.fax["A"])})
    assert res.status_int == 302 and res.headers["Location"].endswith("/sendfax") and sent == []


def test_a_plain_send_still_works_without_refax(world, sent):
    _login(world, "alice").post("/sendfax", {"_submit_check": "1", "faxnumber": "5550100"})
    assert len(sent) == 1 and sent[0].files == []


# --- the outbox must not feed job numbers into the fax-reply parameter ---------------------------------------------------------

def test_the_outbox_retry_link_does_not_use_the_fax_reply_parameter(testapp):
    from namifax.services.faxqueue import FaxQueue  # noqa: F401
    template = open("src/namifax/templates/outbox.jinja2", encoding="utf-8").read()
    assert "refax=" not in template and "/ajax/faxalter?jid={{ j.jid }}&r=1&owner={{ j.owner|urlencode }}" in template


def test_the_job_dialog_carries_the_job_it_was_opened_for(world):
    page = _login(world, "alice").get("/ajax/faxalter?jid=42&r=1")
    assert 'name="jid" value="42"' in page.text


def test_the_job_dialog_does_not_echo_markup_in_the_job_id(world):
    page = _login(world, "alice").get('/ajax/faxalter?jid="><script>x</script>')
    assert "<script>x" not in page.text


# --- the original address refax.php?fid=N keeps working -----------------------------------------------------------------------

def test_the_old_refax_address_leads_to_the_reply_page(world):
    res = _login(world, "alice").get(f"/refax?fid={world.fax['A']}")
    assert res.status_int == 302 and res.headers["Location"].endswith(f"/sendfax?refax={world.fax['A']}")


def test_the_old_refax_address_without_a_fax_leads_to_the_plain_page(world):
    res = _login(world, "alice").get("/refax")
    assert res.status_int == 302 and res.headers["Location"].endswith("/sendfax")


def test_the_old_refax_address_needs_a_login(testapp):
    assert testapp.get("/refax?fid=1", expect_errors=True).status_int in (302, 401, 403)
