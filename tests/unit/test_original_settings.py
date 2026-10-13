"""Settings under the names the original used, with the original's defaults: HylaFAX paths (HYLASPOOL, HYLAFAX_PREFIX, BINARYDIR),
the date formats, PAPERSIZE/DPI and preview sizes, and the hook switches that are on in the original."""

from __future__ import annotations

import importlib

import pytest

from namifax.common import settings


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in ("HYLASPOOL", "HYLAFAX_PREFIX", "BINARYDIR", "EMAIL_DATE_FORMAT", "FAXCOVER_DATE_FORMAT", "PAPERSIZE", "DPI",
                 "PREV_TN", "PREV_SP", "AVANTFAX_ARCHIVE", "ARCHIVE_SENT", "PHONEBOOK"):
        monkeypatch.delenv(name, raising=False)


def test_the_spool_follows_hylaspool(monkeypatch):
    assert settings.hylaspool() == "/var/spool/hylafax"
    monkeypatch.setenv("HYLASPOOL", "/srv/fax")
    assert settings.hylaspool() == "/srv/fax"
    assert settings.archive_dir() == "/srv/fax/archive" and settings.sent_dir() == "/srv/fax/sent"
    assert settings.phonebook_path() == "/srv/fax/etc/phonebook"


def test_a_folder_can_be_named_on_its_own(monkeypatch):
    monkeypatch.setenv("AVANTFAX_ARCHIVE", "/data/in")
    monkeypatch.setenv("ARCHIVE_SENT", "/data/out")
    assert (settings.archive_dir(), settings.sent_dir()) == ("/data/in", "/data/out")


def test_binaries_are_found_in_binarydir_first(monkeypatch, tmp_path):
    tool = tmp_path / "sendfax"
    tool.write_text("#!/bin/sh\n")
    tool.chmod(0o755)
    monkeypatch.setenv("BINARYDIR", str(tmp_path))
    assert settings.binary("sendfax") == str(tool)


def test_a_binary_can_be_named_directly(monkeypatch, tmp_path):
    tool = tmp_path / "mygs"
    tool.write_text("#!/bin/sh\n")
    tool.chmod(0o755)
    monkeypatch.setenv("GS", str(tool))
    assert settings.binary("gs") == str(tool)


def test_a_missing_binary_is_none(monkeypatch, tmp_path):
    monkeypatch.setenv("BINARYDIR", str(tmp_path))
    monkeypatch.setenv("PATH", str(tmp_path))
    assert settings.binary("nonexistent-tool") is None


def test_date_formats_default_to_the_originals(monkeypatch):
    assert settings.email_date_format() == "%d.%m.%Y %H:%M" and settings.faxcover_date_format() == "%d.%m.%Y %H:%M"
    monkeypatch.setenv("EMAIL_DATE_FORMAT", "%Y/%m/%d")
    assert settings.email_date_format() == "%Y/%m/%d"


def test_paper_and_resolution_defaults(monkeypatch):
    assert (settings.papersize(), settings.dpi()) == ("a4", 200)
    monkeypatch.setenv("PAPERSIZE", "letter")
    monkeypatch.setenv("DPI", "300")
    assert (settings.papersize(), settings.dpi()) == ("letter", 300)


def test_the_hook_switches_default_like_the_original():
    from namifax.cli import faxrcvd

    importlib.reload(faxrcvd)
    assert faxrcvd.ARCHIVEFAX2EMAIL is True and faxrcvd.FAXRCVD_INCLUDE_PDF is True and faxrcvd.AUTOCONFDID is True


def test_the_preview_sizes_follow_the_settings(monkeypatch, tmp_path):
    from PIL import Image

    from namifax.services import fax_images

    Image.new("1", (1728, 2200), 1).save(tmp_path / "fax.tif", format="TIFF", compression="group4")
    monkeypatch.setenv("PREV_TN", "40")
    monkeypatch.setenv("PREV_SP", "500")
    fax_images.render_previews(str(tmp_path))
    assert Image.open(tmp_path / "thumb.png").width == 40 and Image.open(tmp_path / "page0.png").width == 500


# --- dynconf writes the system log like the original -----------------------------------------------------------------------

def test_dynconf_logs_what_it_checks_and_rejects(dbsession, capsys):
    from namifax.cli.dynconf import run_dynconf
    from namifax.services.dynconf import DynamicConfig
    from namifax.services.syslog import SysLogService

    dc = DynamicConfig(db=dbsession)
    dc.create("5550100", "ttyS0") if hasattr(dc, "create") else None
    run_dynconf(["dynconf", "ttyS0", "5550100"], db=dbsession)
    texts = [r["logtext"] for r in SysLogService(dbsession).search(kw="dynconf>")]
    assert any("checking CallID1 5550100 on device ttyS0" in t for t in texts)


# --- the vCard upload has the same size limit as the fax upload ------------------------------------------------------------

def test_an_oversized_vcard_is_refused(testapp, monkeypatch):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    monkeypatch.setenv("NAMIFAX_MAX_UPLOAD_BYTES", "100")
    card = b"BEGIN:VCARD\nFN:A\nTEL;FAX:555\nEND:VCARD\n" * 20
    res = testapp.post("/upload/faxcontacts", {"catid": "1"}, upload_files=[("upload", "c.vcf", card)])
    assert "File size is over the limit" in res.text and "Successfully uploaded" not in res.text
