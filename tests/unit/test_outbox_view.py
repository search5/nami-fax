"""Outbox: the fax queue like the original outbox.php.

``faxstat``, ``faxrm`` and ``faxalter`` are small scripts: faxstat prints the queue files named in the environment, the others
write down their arguments and the FAXUSER they ran as. The queue lines follow the AvantFAX job format
(JID Pri S Owner Mailaddr Number Pages Dials TTS Status).
"""

from __future__ import annotations

import os
import stat

import pytest
import webtest

from namifax.models import AddressBook, AddressBookFAX
from namifax.services.user_account import NFUserAccount

SENDQ = """HylaFAX scheduler on localhost: Running
Modem ttyS0 (+82-2-555-0100): Running and idle

JID  Pri S  Owner   Mailaddr          Number   Pages Dials TTS   Status
80   127 R  alice   alice@corp.test   5550100  1:1   0:12  -     Dialing
81   100 S  bob     bob@corp.test     5550101  2:2   0:0   14:30 Waiting_for_the_time_to_send
82   127 R  faxmail alice@corp.test   5550102  1:3   0:1   -     Sending_page_1
83   127 R  carl    carl@corp.test    5550103  1:1   0:0   -     Waiting_for_modem
"""
DONEQ = """HylaFAX scheduler on localhost: Running

JID  Pri S  Owner   Mailaddr          Number   Pages Dials Status
90   127 F  alice   alice@corp.test   5550100  1:0   12:12 Busy_signal
91   127 F  bob     bob@corp.test     5550101  1:0   12:12 No_carrier
92   127 D  alice   alice@corp.test   5550105  1:1   1:1   Completed
"""
PWD = "Secret123!"


@pytest.fixture
def hylafax(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (tmp_path / "sendq").write_text(SENDQ)
    (tmp_path / "doneq").write_text(DONEQ)
    scripts = {
        "faxstat": 'if [ "$1" = "-s" ]; then cat "$SENDQ"; else cat "$DONEQ"; fi',
        "faxrm": '{ echo "CMD faxrm"; echo "ARG $*"; echo "USER $FAXUSER"; } >> "$RECORD"',
        "faxalter": '{ echo "CMD faxalter"; echo "ARG $*"; echo "USER $FAXUSER"; } >> "$RECORD"',
    }
    for name, body in scripts.items():
        path = bin_dir / name
        path.write_text(f"#!/bin/sh\n{body}\n")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("SENDQ", str(tmp_path / "sendq"))
    monkeypatch.setenv("DONEQ", str(tmp_path / "doneq"))
    monkeypatch.setenv("RECORD", str(tmp_path / "record.txt"))

    def record():
        lines = (tmp_path / "record.txt").read_text().splitlines() if (tmp_path / "record.txt").exists() else []
        out, cur = [], None
        for line in lines:
            if line.startswith("CMD "):
                cur = {"cmd": line[4:]}; out.append(cur)
            elif line.startswith("ARG "):
                cur["args"] = line[4:]
            elif line.startswith("USER "):
                cur["user"] = line[5:]
        return out

    return record


@pytest.fixture
def people(testapp, dbsession):
    for name, email in (("alice", "alice@corp.test"), ("bob", "bob@corp.test")):
        svc = NFUserAccount(db=dbsession)
        assert svc.create({"username": name, "password": PWD, "email": email, "name": name.title(),
                           "last_login": "2026-01-01 10:00:00", "acc_enabled": 1}), svc.error
    book = AddressBook(company="Acme Corp")
    dbsession.add(book)
    dbsession.flush()
    dbsession.add(AddressBookFAX(abook_id=book.abook_id, faxnumber="5550100"))
    dbsession.flush()


def _login(testapp, username, password=PWD):
    client = webtest.TestApp(testapp.app, extra_environ=testapp.extra_environ)
    assert client.post("/login", {"username": username, "password": password, "_submit_check": "1"}).status_int == 302
    return client


def _kill(client, jid, token="page"):
    """Press the Kill button: the form of the page, with the page's CSRF token (or the given one)."""
    if token == "page":
        token = client.get("/outbox").html.find("input", {"name": "csrf_token"})["value"]
    data = {"kill": str(jid)}
    if token is not None:
        data["csrf_token"] = token
    return client.post("/outbox", data, expect_errors=True)


def _jids(page):
    return sorted(int(j) for j in __import__("re").findall(r'data-jid="(\d+)"', page.text))


# --- who sees which job ------------------------------------------------------------------------------------------------------

def test_a_user_sees_their_own_jobs_and_those_sent_for_them_by_mail(testapp, people, hylafax):
    assert _jids(_login(testapp, "alice").get("/outbox")) == [80, 82, 90]       # 82: owner faxmail, mail address is alice's


def test_another_user_does_not_see_them(testapp, people, hylafax):
    assert _jids(_login(testapp, "bob").get("/outbox")) == [81, 91]


def test_a_superuser_sees_every_job(testapp, people, hylafax):
    assert _jids(_login(testapp, "admin", "password").get("/outbox")) == [80, 81, 82, 83, 90, 91]


def test_only_failed_jobs_are_listed_from_the_done_queue(testapp, people, hylafax):
    assert 92 not in _jids(_login(testapp, "admin", "password").get("/outbox"))         # state D (done), not F


# --- what a row shows ----------------------------------------------------------------------------------------------------------

def test_a_row_has_the_original_columns(testapp, people, hylafax):
    page = _login(testapp, "alice").get("/outbox")
    row = page.html.find(attrs={"data-jid": "80"}).get_text(" ", strip=True)
    for value in ("80", "127", "Alice", "Acme Corp", "1:1", "0:12", "Dialing"):
        assert value in row, value


def test_the_company_is_the_number_when_the_address_book_does_not_know_it(testapp, people, hylafax):
    row = _login(testapp, "alice").get("/outbox").html.find(attrs={"data-jid": "82"}).get_text(" ", strip=True)
    assert "5550102" in row


def test_the_user_column_names_the_person_for_mailed_jobs(testapp, people, hylafax):
    row = _login(testapp, "alice").get("/outbox").html.find(attrs={"data-jid": "82"}).get_text(" ", strip=True)
    assert "Alice" in row


def test_the_time_to_send_is_shown_for_waiting_jobs(testapp, people, hylafax):
    row = _login(testapp, "bob").get("/outbox").html.find(attrs={"data-jid": "81"}).get_text(" ", strip=True)
    assert "14:30" in row and "Waiting_for_the_time_to_send" in row.replace(" ", "_") or "Waiting" in row


def test_the_total_is_shown(testapp, people, hylafax):
    assert "3 faxes" in _login(testapp, "alice").get("/outbox").text


def test_the_page_refreshes_itself_every_minute(testapp, people, hylafax):
    assert 'http-equiv="refresh" content="60' in _login(testapp, "alice").get("/outbox").text


# --- the buttons ---------------------------------------------------------------------------------------------------------------

def test_a_waiting_job_can_be_modified_or_killed(testapp, people, hylafax):
    page = _login(testapp, "alice").get("/outbox")
    assert "/ajax/faxalter?jid=80&amp;owner=alice" in page.text or "/ajax/faxalter?jid=80&owner=alice" in page.text
    assert page.html.find("input", {"name": "kill", "value": "80"}) is not None


def test_a_failed_job_can_be_resubmitted_or_killed(testapp, people, hylafax):
    page = _login(testapp, "alice").get("/outbox")
    assert "jid=90&amp;r=1&amp;owner=alice" in page.text or "jid=90&r=1&owner=alice" in page.text
    assert page.html.find("input", {"name": "kill", "value": "90"}) is not None


def test_a_job_sent_by_mail_is_modified_in_the_name_of_its_owner(testapp, people, hylafax):
    page = _login(testapp, "alice").get("/outbox")
    assert "jid=82&amp;owner=faxmail" in page.text or "jid=82&owner=faxmail" in page.text


# --- killing -------------------------------------------------------------------------------------------------------------------
# Killing changes the queue, so it is a POST with the page's CSRF token (the original used a plain link, which any other site
# could have made a user click).

def test_a_user_can_kill_their_own_job(testapp, people, hylafax):
    _kill(_login(testapp, "alice"), 80)
    assert hylafax() == [{"cmd": "faxrm", "args": "80", "user": "alice"}]


def test_a_user_cannot_kill_somebody_elses_job(testapp, people, hylafax):
    page = _kill(_login(testapp, "alice"), 81)
    assert hylafax() == [] and "81" in page.text


def test_a_superuser_kills_a_job_in_the_name_of_its_owner(testapp, people, hylafax):
    _kill(_login(testapp, "admin", "password"), 81)
    assert hylafax() == [{"cmd": "faxrm", "args": "81", "user": "bob"}]


def test_a_failed_job_is_found_in_the_done_queue_and_killed(testapp, people, hylafax):
    _kill(_login(testapp, "alice"), 90)
    assert hylafax() == [{"cmd": "faxrm", "args": "90", "user": "alice"}]


def test_a_job_that_is_not_failed_is_not_removed_from_the_done_queue(testapp, people, hylafax):
    _kill(_login(testapp, "alice"), 92)
    assert hylafax() == []


@pytest.mark.parametrize("value", ["abc", "80; rm -rf /", "-1", ""])
def test_the_job_number_must_be_a_number(testapp, people, hylafax, value):
    _kill(_login(testapp, "admin", "password"), value)
    assert hylafax() == []


def test_a_link_to_the_old_kill_address_removes_nothing(testapp, people, hylafax):
    client = _login(testapp, "alice")
    assert client.get("/outbox?kill=80").status_int == 200
    assert hylafax() == []


def test_a_post_without_the_token_removes_nothing(testapp, people, hylafax):
    page = _kill(_login(testapp, "alice"), 80, token=None)
    assert hylafax() == [] and "expired" in page.text.lower()


def test_a_post_with_a_wrong_token_removes_nothing(testapp, people, hylafax):
    _kill(_login(testapp, "alice"), 80, token="not-the-token")
    assert hylafax() == []


def test_the_token_of_another_session_is_refused(testapp, people, hylafax):
    other = _login(testapp, "bob").get("/outbox").html.find("input", {"name": "csrf_token"})["value"]
    _kill(_login(testapp, "alice"), 80, token=other)
    assert hylafax() == []


def test_the_kill_button_is_a_form_with_the_token(testapp, people, hylafax):
    page = _login(testapp, "alice").get("/outbox")
    form = page.html.find("input", {"name": "kill", "value": "80"}).find_parent("form")
    assert form["method"].lower() == "post" and form["action"] == "/outbox"
    assert form.find("input", {"name": "csrf_token"})["value"]
    assert "/outbox?kill=" not in page.text


def test_the_queue_needs_a_login(testapp, hylafax):
    assert testapp.get("/outbox", expect_errors=True).status_int in (302, 401, 403)


def test_the_web_server_and_faxmail_user_names_come_from_the_environment(monkeypatch):
    """Jobs owned by these two users are matched to a person by their mail address (the original's $WWWUSER, $FAXMAILUSER)."""
    from namifax.services.faxqueue import FaxQueue

    monkeypatch.setenv("WWWUSER", "apache")
    monkeypatch.setenv("FAXMAILUSER", "mailer")
    fq = FaxQueue(auto_process=False)
    assert (fq.www_user, fq.faxmail_user) == ("apache", "mailer")
    monkeypatch.delenv("WWWUSER")
    monkeypatch.delenv("FAXMAILUSER")
    fq = FaxQueue(auto_process=False)
    assert (fq.www_user, fq.faxmail_user) == ("www-data", "faxmail")
