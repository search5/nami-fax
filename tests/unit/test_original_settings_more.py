"""More of the original's settings: which CallID line is the caller number/name/DID (CALLIDn_*), barcode and OCR switches, commands and
language, and the e-mail encodings (EMAIL_ENCODING_TEXT/HTML/CHARSET, Base64 by default)."""

from __future__ import annotations

import email
import os
import stat
from email import policy
from unittest.mock import MagicMock, patch

import pytest

from namifax.common import helpers, settings


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in ("CALLIDN_CIDNUMBER", "CALLIDN_CIDNAME", "CALLIDN_DIDNUM", "ENABLE_BARDECODE_SUPPORT", "BARDECODE_BINARY",
                 "BARDECODE_COMMAND", "ENABLE_OCR_SUPPORT", "OCR_BINARY", "OCR_COMMAND", "OCR_LANGUAGE", "EMAIL_ENCODING_TEXT",
                 "EMAIL_ENCODING_HTML", "EMAIL_ENCODING_CHARSET", "HYLASPOOL"):
        monkeypatch.delenv(name, raising=False)


def _script(path, body):
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


# --- CallID order -----------------------------------------------------------------------------------------------------------

def test_call_id_lines_default_to_the_originals(monkeypatch):
    assert (settings.callid_index("CIDNumber"), settings.callid_index("CIDName"), settings.callid_index("DIDNum")) == (1, 2, 3)


def test_call_id_lines_can_be_reordered(monkeypatch):
    monkeypatch.setenv("CALLIDN_CIDNUMBER", "2")
    monkeypatch.setenv("CALLIDN_CIDNAME", "1")
    assert (settings.callid_index("CIDNumber"), settings.callid_index("CIDName")) == (2, 1)


def test_the_hook_reads_the_configured_lines(tmp_path, monkeypatch):
    from namifax.cli import faxrcvd as hook

    monkeypatch.setenv("CALLIDN_CIDNUMBER", "2")
    monkeypatch.setenv("CALLIDN_CIDNAME", "1")
    info = {"CallID1": "Acme Inc", "CallID2": "5551234", "CallID3": "<NONE>"}
    assert hook.caller_from(info, "", "", "") == ("5551234", "Acme Inc", "")


def test_a_value_given_on_the_command_line_wins_and_none_is_ignored():
    from namifax.cli import faxrcvd as hook

    assert hook.caller_from({"CallID1": "<NONE>", "CallID2": "x", "CallID3": "y"}, "111", "", "") == ("111", "x", "y")


# --- barcode ----------------------------------------------------------------------------------------------------------------

def test_barcode_decoding_is_off_unless_enabled(tmp_path):
    img = tmp_path / "f.tif"
    img.write_bytes(b"x")
    assert helpers.bardecode(str(img)) is None


def test_barcode_uses_the_configured_command(tmp_path, monkeypatch):
    img = tmp_path / "f.tif"
    img.write_bytes(b"x")
    tool = _script(tmp_path / "bc", 'echo "CODE-$2"\n')
    monkeypatch.setenv("ENABLE_BARDECODE_SUPPORT", "1")
    monkeypatch.setenv("BARDECODE_BINARY", tool)
    monkeypatch.setenv("BARDECODE_COMMAND", f"{tool} -t any -f %s")
    assert helpers.bardecode(str(img)).startswith("CODE-")


def test_the_barcode_file_name_is_never_run_as_shell(tmp_path, monkeypatch):
    evil = tmp_path / "f;touch pwned.tif"
    evil.write_bytes(b"x")
    tool = _script(tmp_path / "bc", "echo ok\n")
    monkeypatch.setenv("ENABLE_BARDECODE_SUPPORT", "1")
    monkeypatch.setenv("BARDECODE_BINARY", tool)
    monkeypatch.chdir(tmp_path)
    helpers.bardecode(str(evil))
    assert not (tmp_path / "pwned.tif").exists()


# --- OCR --------------------------------------------------------------------------------------------------------------------

def test_ocr_is_off_unless_enabled(tmp_path):
    img = tmp_path / "f.tif"
    img.write_bytes(b"x")
    assert helpers.ocr_faxcontent(str(img)) is None


def test_ocr_uses_the_configured_program_and_language(tmp_path, monkeypatch):
    img = tmp_path / "f.tif"
    img.write_bytes(b"x")
    tool = _script(tmp_path / "ocr", 'printf "text in $4 read from $(basename $1)" > "$2.txt"\n')
    monkeypatch.setenv("ENABLE_OCR_SUPPORT", "1")
    monkeypatch.setenv("OCR_BINARY", tool)
    monkeypatch.setenv("OCR_COMMAND", f"{tool} %s %s -l %s")
    monkeypatch.setenv("OCR_LANGUAGE", "kor")
    assert helpers.ocr_faxcontent(str(img)) == "text in kor read from f.tif"


def test_ocr_language_defaults_to_english():
    assert settings.ocr_language() == "eng"


def test_the_hook_does_not_index_when_ocr_is_off():
    from namifax.cli import faxrcvd as hook

    assert hook.ocr_wanted() is False


# --- e-mail encodings -------------------------------------------------------------------------------------------------------

def test_mail_encoding_defaults_are_the_originals():
    assert (settings.email_encoding("TEXT"), settings.email_encoding("HTML"), settings.email_charset()) == ("base64", "base64", "utf-8")


@pytest.mark.parametrize("name,cte", [("Base64Encoding", "base64"), ("QuotedPrintableEncoding", "quoted-printable"),
                                       ("8bit", "8bit"), ("7bit", "7bit"), ("nonsense", "base64")])
def test_encoding_names_of_the_original_are_understood(monkeypatch, name, cte):
    monkeypatch.setenv("EMAIL_ENCODING_TEXT", name)
    assert settings.email_encoding("TEXT") == cte


def test_the_message_bodies_are_encoded_as_configured(monkeypatch):
    from namifax.services.mailer import MailerService

    monkeypatch.setenv("EMAIL_ENCODING_TEXT", "QuotedPrintableEncoding")
    monkeypatch.setenv("EMAIL_ENCODING_HTML", "Base64Encoding")
    mailer = MailerService(spool_mode=True, admin_email="gw@corp.test")
    mailer.set_message("Grüße 한국어", "Subject")
    mailer.sendmail("b@x.test")
    (msg,) = mailer.get_spooled_messages()
    text, html = msg.get_body(("plain",)), msg.get_body(("html",))
    assert text["Content-Transfer-Encoding"] == "quoted-printable" and html["Content-Transfer-Encoding"] == "base64"
    assert "utf-8" in text["Content-Type"].lower() and "Grüße 한국어" in text.get_content()
