"""Send Fax page: what is typed into the form reaches HylaFAX's sendfax/faxcover, like the original.

``sendfax`` and ``faxcover`` are replaced by small scripts that write down their arguments.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from sqlalchemy import select

from namifax.models import CoverPages, UserAccount

SCRIPT = """#!/bin/sh
{ echo "CMD $(basename "$0")"; for a in "$@"; do printf 'ARG %s\\n' "$a"; done; } >> "$RECORD"
BODY
"""


@pytest.fixture
def hylafax(tmp_path, monkeypatch):
    """Fake sendfax and faxcover on PATH; returns a function giving the recorded commands as {'cmd', 'args'} dicts."""
    bin_dir, record = tmp_path / "bin", tmp_path / "record.txt"
    bin_dir.mkdir()
    for name, body in (("sendfax", 'echo "request id is 80 (group id 80) for host localhost (1 file)"'),
                       ("faxcover", 'echo "%!PS-fake cover"')):
        path = bin_dir / name
        path.write_text(SCRIPT.replace("BODY", body))
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("NAMIFAX_FAXCOVER", str(bin_dir / "faxcover"))
    monkeypatch.setenv("NAMIFAX_QUEUE_SIMULATION", "0")
    monkeypatch.setenv("RECORD", str(record))
    monkeypatch.setenv("AVANTFAX_INSTALLDIR", str(tmp_path / "inst"))
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))

    def commands():
        out = []
        for line in (record.read_text().splitlines() if record.exists() else []):
            if line.startswith("CMD "):
                out.append({"cmd": line[4:], "args": []})
            elif line.startswith("ARG "):
                out[-1]["args"].append(line[4:])
        return out

    return commands


@pytest.fixture
def client(testapp, dbsession):
    admin = dbsession.execute(select(UserAccount).where(UserAccount.username == "admin")).scalar_one()
    admin.from_company, admin.from_location, admin.from_voicenumber, admin.from_faxnumber = "Corp Inc", "Seoul", "+82 2 555 0100", "+82 2 555 0101"
    admin.name = "Alice Sender"
    dbsession.flush()
    testapp.admin_email = admin.email
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


def _opt(args, flag):
    return args[args.index(flag) + 1]


FULL = {"_submit_check": "1", "faxnumber": "5550100", "to_person": "Bob Receiver", "to_company": "Acme Ltd",
        "regarding": "Invoice 42", "comments": "Hello there!", "modem": "ttyS0", "priority": "10", "numtries": "3",
        "killtime": "3", "killtime_unit": "days", "sendtime": "1", "sendtimeHour": "14", "sendtimeMin": "30",
        "user_tsi": "MY TSI", "notify_requeue": "1", "to_location": "Busan", "to_voicenumber": "051 555 0111"}


def test_every_option_of_the_form_reaches_sendfax(client, hylafax):
    res = client.post("/sendfax", FULL, upload_files=[("file", "doc.pdf", b"%PDF-1.4 x")])
    assert res.status_int == 302 and res.headers["Location"].endswith("/outbox")
    (cmd,) = hylafax()
    args = cmd["args"]
    assert cmd["cmd"] == "sendfax" and args[:2] == ["-R", "-n"]
    assert (_opt(args, "-o"), _opt(args, "-f"), _opt(args, "-X"), _opt(args, "-Y")) == ("admin", client.admin_email, "Corp Inc", "Seoul")
    assert (_opt(args, "-x"), _opt(args, "-r"), _opt(args, "-c"), _opt(args, "-y"), _opt(args, "-V")) == (
        "Acme Ltd", "Invoice 42", "Hello there&#33;", "Busan", "051 555 0111")
    assert (_opt(args, "-t"), _opt(args, "-k"), _opt(args, "-S"), _opt(args, "-P"), _opt(args, "-a")) == (
        "3", "now + 3 days", "MY TSI", "10", "14:30")
    assert (_opt(args, "-h"), _opt(args, "-d")) == ("ttyS0@localhost", "Bob Receiver@5550100")
    assert args[-1].endswith("doc.pdf")


def test_a_plain_send_uses_the_defaults(client, hylafax):
    client.post("/sendfax", {"_submit_check": "1", "faxnumber": "5550100", "priority": "*"},
                upload_files=[("file", "doc.pdf", b"%PDF")])
    (cmd,) = hylafax()
    assert cmd["args"][:2] == ["-D", "-n"] and "-P" not in cmd["args"] and "-a" not in cmd["args"]


def test_a_cover_page_alone_is_made_by_faxcover_and_sent(client, hylafax, dbsession, tmp_path):
    res = client.post("/sendfax", {"_submit_check": "1", "faxnumber": "5550100", "coverpage": "1", "whichcover": "cover.ps",
                                   "to_person": "Bob", "comments": "Please read"})
    assert res.status_int == 302
    cover, send = hylafax()
    assert cover["cmd"] == "faxcover" and _opt(cover["args"], "-C") == str(tmp_path / "inst" / "images" / "cover.ps")
    assert _opt(cover["args"], "-n") == "5550100" and _opt(cover["args"], "-t") == "Bob"
    assert send["cmd"] == "sendfax" and send["args"][-1].endswith(".ps")
    assert not Path(send["args"][-1]).exists()                      # the generated cover does not pile up in the temp dir


def test_several_destinations_are_sent_through_a_list_file(client, hylafax):
    client.post("/sendfax", {"_submit_check": "1", "faxnumber": "5550100;5550101"}, upload_files=[("file", "d.pdf", b"%PDF")])
    (cmd,) = hylafax()
    assert "-z" in cmd["args"] and "-d" not in cmd["args"]


def test_without_a_file_or_a_cover_page_nothing_is_sent(client, hylafax):
    res = client.post("/sendfax", {"_submit_check": "1", "faxnumber": "5550100"})
    assert res.status_int == 200 and "file" in res.text.lower() and hylafax() == []


def test_a_failing_sendfax_is_reported_on_the_page(client, hylafax, tmp_path):
    (tmp_path / "bin" / "sendfax").write_text("#!/bin/sh\necho 'sendfax: no such modem' >&2\nexit 1\n")
    res = client.post("/sendfax", {"_submit_check": "1", "faxnumber": "5550100"}, upload_files=[("file", "d.pdf", b"%PDF")])
    assert res.status_int == 200 and "no such modem" in res.text


# --- the form -----------------------------------------------------------------------------------------------------------------

def test_the_form_offers_the_covers_of_the_cover_table(client, dbsession):
    page = client.get("/sendfax")
    assert 'value="cover.ps"' in page.text and "Generic A4" in page.text and 'value="confidential"' not in page.text


def test_the_form_has_the_original_scheduling_and_recipient_fields(client):
    page = client.get("/sendfax")
    for name in ("killtime", "killtime_unit", "sendtime", "sendtimeHour", "sendtimeMin", "user_tsi", "to_location",
                 "to_voicenumber", "to_address", "to_zip", "to_city", "numtries", "priority", "notify_requeue"):
        assert f'name="{name}"' in page.text, name


def test_the_priority_list_is_the_original_one(client):
    page = client.get("/sendfax")
    form = next(f for f in page.forms.values() if "priority" in f.fields)         # (the first form is the header's sign-out)
    values = [v for v, _, _ in form["priority"].options]
    assert values == ["*"] + [str(n) for n in range(0, 255, 10)]
