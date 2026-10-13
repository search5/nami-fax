"""Modify / resubmit a queued fax job: the original ajax/faxalter.php dialog and the operations it hands to faxalter.

The recorded form fields and the mapping to faxalter operations are from the original (faxalter.php, faxalter.tpl):
destination, priority (``*`` = unchanged), modem (only when the user has more than one), tries, expiry, "now" or a time.
"""

from __future__ import annotations

import pytest
import webtest

from namifax.services.user_account import NFUserAccount
from test_archive_search_legacy_parity import _configure

PWD = "Secret123!"


class FakeQueue:
    calls: list = []

    def __init__(self, *a, **kw):
        pass

    def faxalter(self, user, jid, operations):
        FakeQueue.calls.append((user, jid, dict(operations)))
        return True


@pytest.fixture(autouse=True)
def queue(monkeypatch):
    FakeQueue.calls = []
    monkeypatch.setattr("namifax.views.ajax.FaxQueue", FakeQueue)
    return FakeQueue


@pytest.fixture
def admin(testapp, dbsession):
    _configure(dbsession, modems=["ttyS0", "ttyS1"])
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


def _user(testapp, dbsession, name, modems):
    svc = NFUserAccount(db=dbsession)
    assert svc.create({"username": name, "password": PWD, "email": f"{name}@x.test", "name": name, "last_login": "2026-01-01 10:00:00",
                       "acc_enabled": 1, "modemdevs": modems}), svc.error
    dbsession.flush()
    client = webtest.TestApp(testapp.app, extra_environ=testapp.extra_environ)
    assert client.post("/login", {"username": name, "password": PWD, "_submit_check": "1"}).status_int == 302
    return client


FULL = {"_submit_check": "1", "jid": "42", "destination": "5550199", "priority": "10", "modem": "ttyS1", "numtries": "3",
        "killtime": "2", "killtime_unit": "days", "sendtime": "1", "sendtimeHour": "14", "sendtimeMin": "30"}


# --- the dialog -------------------------------------------------------------------------------------------------------------

def test_the_dialog_has_the_original_fields(admin):
    page = admin.get("/ajax/faxalter?jid=42")
    for name in ("destination", "priority", "modem", "numtries", "killtime", "killtime_unit", "sendnow", "sendtime",
                 "sendtimeHour", "sendtimeMin", "jid", "resubmit", "owner"):
        assert f'name="{name}"' in page.text, name
    assert 'name="jid" value="42"' in page.text


def test_the_priority_list_is_the_original_one(admin):
    form = admin.get("/ajax/faxalter?jid=42").forms["faxalter"]
    assert [v for v, _, _ in form["priority"].options] == ["*"] + [str(n) for n in range(0, 255, 10)]


def test_the_modem_choice_is_offered_when_the_user_has_a_modem(admin, dbsession):
    """The original's list starts with an empty entry and the choice shows when there is more than that."""
    assert 'name="modem"' in admin.get("/ajax/faxalter?jid=1").text
    assert 'name="modem"' in _user(admin, dbsession, "solo", "ttyS0").get("/ajax/faxalter?jid=1").text
    assert 'name="modem"' not in _user(admin, dbsession, "nomodem", None).get("/ajax/faxalter?jid=1").text


def test_a_resubmit_dialog_starts_with_an_expiry_of_three_hours(admin):
    form = admin.get("/ajax/faxalter?jid=7&r=1").forms["faxalter"]
    assert form["resubmit"].value == "1" and form["killtime"].value == "3" and form["killtime_unit"].value == "hours"


def test_a_plain_modify_dialog_has_no_default_expiry(admin):
    form = admin.get("/ajax/faxalter?jid=7").forms["faxalter"]
    assert form["resubmit"].value == "" and form["killtime"].value == ""


def test_markup_in_the_job_number_is_not_echoed(admin):
    assert "<script>x" not in admin.get('/ajax/faxalter?jid="><script>x</script>').text


# --- what is handed to faxalter -----------------------------------------------------------------------------------------------

def test_every_field_becomes_the_operation_the_original_made(admin, queue):
    res = admin.post("/ajax/faxalter", FULL, headers={"X-Requested-With": "XMLHttpRequest"})
    assert res.status_int == 200 and res.text == ""
    (user, jid, ops), = queue.calls
    assert (user, jid) == ("admin", 42)
    assert ops == {"destination": "5550199", "tries": "3", "device": "ttyS1", "priority": "10", "sendtime": "14:30",
                   "killtime": "now + 2 days"}
    assert list(ops) == ["destination", "tries", "device", "priority", "sendtime", "killtime"]       # the original's order


def test_send_now_replaces_the_scheduled_time(admin, queue):
    admin.post("/ajax/faxalter", {**FULL, "sendnow": "1"})
    assert queue.calls[0][2]["sendtime"] == "now"


def test_unchanged_priority_and_empty_fields_are_left_out(admin, queue):
    admin.post("/ajax/faxalter", {"_submit_check": "1", "jid": "42", "priority": "*", "destination": "", "numtries": ""})
    assert queue.calls[0][2] == {}


def test_a_scheduled_time_needs_the_checkbox(admin, queue):
    admin.post("/ajax/faxalter", {"_submit_check": "1", "jid": "42", "sendtimeHour": "14", "sendtimeMin": "30"})
    assert "sendtime" not in queue.calls[0][2]


def test_a_resubmit_is_asked_for(admin, queue):
    admin.post("/ajax/faxalter", {"_submit_check": "1", "jid": "7", "resubmit": "1", "killtime": "3", "killtime_unit": "hours"})
    assert queue.calls[0][2] == {"killtime": "now + 3 hours", "resubmit": True}


def test_a_page_post_goes_back_to_the_outbox_but_an_ajax_post_gets_an_empty_answer(admin, queue):
    res = admin.post("/ajax/faxalter", {"_submit_check": "1", "jid": "42"})
    assert res.status_int == 302 and res.headers["Location"].endswith("/outbox")


@pytest.mark.parametrize("field,value", [("jid", "abc"), ("jid", ""), ("killtime", "x"), ("numtries", "-1"), ("numtries", "x")])
def test_bad_numbers_are_refused_and_nothing_is_altered(admin, queue, field, value):
    res = admin.post("/ajax/faxalter", {**FULL, field: value}, expect_errors=True)
    assert res.status_int == 200 and "valid" in res.text.lower() and queue.calls == []


# --- whose job ----------------------------------------------------------------------------------------------------------------

def test_a_user_can_only_alter_jobs_in_their_own_name(admin, queue, dbsession):
    mallory = _user(admin, dbsession, "mallory", "ttyS0|ttyS1")
    mallory.post("/ajax/faxalter", {**FULL, "owner": "alice"})
    assert queue.calls[0][0] == "mallory"


def test_a_superuser_may_alter_a_job_for_its_owner(admin, queue):
    admin.post("/ajax/faxalter", {**FULL, "owner": "alice"})
    assert queue.calls[0][0] == "alice"


def test_without_a_login_nothing_is_altered(queue, testapp):
    testapp.post("/ajax/faxalter", FULL, expect_errors=True)
    assert queue.calls == []


def test_the_failed_job_list_links_each_job_with_its_owner():
    template = open("src/namifax/templates/outbox.jinja2", encoding="utf-8").read()
    assert "/ajax/faxalter?jid={{ j.jid }}&r=1&owner={{ j.owner" in template
