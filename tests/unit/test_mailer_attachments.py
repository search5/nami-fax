"""send_mail with an attachment, an inline thumbnail, cc/bcc and a "Name <address>" sender (the original's send_mail())."""

from __future__ import annotations

import smtplib
from unittest.mock import patch

import pytest

from namifax.common import helpers
from namifax.services.mailer import MailerService

PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")


@pytest.fixture
def spool(monkeypatch):
    """A mailer that keeps what it would send; send_mail uses it."""
    mailer = MailerService(spool_mode=True, admin_email="gateway@corp.test")
    monkeypatch.setattr(helpers, "_active_mailer", lambda session=None: mailer)
    return mailer


def _sent(mailer):
    (message,) = mailer.get_spooled_messages()
    return message


def test_a_file_is_attached_under_the_given_name(spool, tmp_path):
    pdf = tmp_path / "fax.pdf"
    pdf.write_bytes(b"%PDF-1.4 body")
    assert helpers.send_mail("to@corp.test", "from@corp.test", "subject", "text", file=str(pdf), altname="fax-Acme.pdf")
    attachments = list(_sent(spool).iter_attachments())
    assert [a.get_filename() for a in attachments] == ["fax-Acme.pdf"]
    assert attachments[0].get_content_type() == "application/pdf" and attachments[0].get_payload(decode=True) == b"%PDF-1.4 body"


def test_without_a_name_the_file_name_is_used(spool, tmp_path):
    pdf = tmp_path / "fax.pdf"
    pdf.write_bytes(b"x")
    helpers.send_mail("to@corp.test", "from@corp.test", "s", "t", file=str(pdf))
    assert [a.get_filename() for a in _sent(spool).iter_attachments()] == ["fax.pdf"]


def test_a_missing_file_is_simply_not_attached(spool):
    assert helpers.send_mail("to@corp.test", "from@corp.test", "s", "t", file="/no/such/file.pdf")
    assert list(_sent(spool).iter_attachments()) == []


def test_the_thumbnail_is_shown_inline_in_the_html_part(spool, tmp_path):
    thumb = tmp_path / "thumb.png"
    thumb.write_bytes(PNG)
    helpers.send_mail("to@corp.test", "from@corp.test", "s", "text", embedd=str(thumb))
    message = _sent(spool)
    html = message.get_body(("html",))
    inline = [p for p in message.walk() if p.get_content_type() == "image/png"]
    assert len(inline) == 1 and inline[0]["Content-ID"] and inline[0].get_payload(decode=True) == PNG
    assert f"cid:{inline[0]['Content-ID'].strip('<>')}" in html.get_content()


def test_cc_is_a_header_and_bcc_is_not(spool):
    helpers.send_mail("to@corp.test", "from@corp.test", "s", "t", cc="a@corp.test; b@corp.test", bcc="hidden@corp.test")
    message = _sent(spool)
    assert "a@corp.test" in message["Cc"] and "b@corp.test" in message["Cc"]
    assert message["Bcc"] is None and "hidden@corp.test" not in message.as_string()


def test_everybody_is_in_the_envelope_but_bcc_stays_out_of_the_headers(monkeypatch):
    sent = {}

    class FakeSMTP:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def send_message(self, msg, from_addr=None, to_addrs=None):
            sent["to_addrs"], sent["bcc"] = to_addrs, msg["Bcc"]
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    mailer = MailerService(smtp_server="smtp.corp.test", admin_email="gateway@corp.test")
    monkeypatch.setattr(helpers, "_active_mailer", lambda session=None: mailer)
    assert helpers.send_mail("to@corp.test", "from@corp.test", "s", "t", cc="cc@corp.test", bcc="bcc@corp.test")
    assert sorted(sent["to_addrs"]) == ["bcc@corp.test", "cc@corp.test", "to@corp.test"] and sent["bcc"] is None


@pytest.mark.parametrize("sender,expected", [("from@corp.test", "from@corp.test"), ("Alice Sender <alice@corp.test>", "alice@corp.test")])
def test_the_sender_may_be_a_name_and_address(spool, sender, expected):
    helpers.send_mail("to@corp.test", sender, "s", "t")
    header = _sent(spool)["From"]
    assert expected in header and header.count("<") == header.count(">") <= 1


def test_a_failed_send_is_logged_and_reported(monkeypatch):
    mailer = MailerService(smtp_server="smtp.corp.test")
    monkeypatch.setattr(helpers, "_active_mailer", lambda session=None: mailer)
    logged = []
    monkeypatch.setattr(helpers, "avantfaxlog", lambda text, *a, **kw: logged.append(text))
    with patch("smtplib.SMTP", side_effect=OSError("connection refused")):
        assert helpers.send_mail("to@corp.test", "from@corp.test", "s", "t") is False
    assert any("MAIL ERROR" in line and "connection refused" in line for line in logged)
