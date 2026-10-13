"""Unit tests for CLI batch administrative tools with real domain service integrations."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from namifax.cli.import_users import main as import_users_main
from namifax.cli.import_blacklist import main as import_blacklist_main
from namifax.cli.reroute import main as reroute_main
from namifax.cli.ocr_import import main as ocr_import_main
from namifax.cli.create_thumbnails import main as create_thumbnails_main


def test_import_users_with_file(tmp_path, capsys):
    """Verify batch user import parses tab-separated file and invokes NFUserAccount.create."""
    users_file = tmp_path / "users.txt"
    users_file.write_text("John Doe\tjohndoe\tpass123\tjohn@example.com\nJane Roe\tjaneroe\tpass456\tjane@example.com\n")

    with patch("namifax.cli.import_users.NFUserAccount") as mock_user_cls:
        inst = MagicMock()
        inst.create.return_value = True
        mock_user_cls.return_value = inst

        res = import_users_main([str(users_file)])
        assert res == 0
        assert inst.create.call_count == 2
        captured = capsys.readouterr()
        assert "user> John Doe" in captured.out
        assert "user> Jane Roe" in captured.out


def test_import_blacklist_with_file(tmp_path, capsys):
    """Verify blacklist import reads file and creates DynamicConfig rules."""
    bl_file = tmp_path / "blacklist.txt"
    bl_file.write_text("01011112222\n01033334444\n")

    with patch("namifax.cli.import_blacklist.DynamicConfig") as mock_dc_cls:
        inst = MagicMock()
        inst.create.return_value = True
        mock_dc_cls.return_value = inst

        res = import_blacklist_main([str(bl_file), "ttyS0"])
        assert res == 0
        assert inst.create.call_count == 2
        captured = capsys.readouterr()
        assert "Created Rule: 01011112222" in captured.out
        assert "Created 2 rules" in captured.out


def test_reroute_modem(capsys):
    """Verify reroute updates contact on FaxModem."""
    with patch("namifax.cli.reroute.FaxModem") as mock_modem_cls:
        inst = MagicMock()
        inst.load_device.return_value = True
        inst.set_contact.return_value = True
        mock_modem_cls.return_value = inst

        res = reroute_main(["ttyS0", "faxes@example.com"])
        assert res == 0
        inst.load_device.assert_called_with("ttyS0")
        inst.set_contact.assert_called_with("faxes@example.com")


def test_ocr_import_enabled(capsys):
    """Verify ocr_import iterates archive and executes OCR when enabled."""
    with patch("namifax.cli.ocr_import.ENABLE_OCR_SUPPORT", True), \
         patch("namifax.cli.ocr_import.FaxPDFArchive") as mock_arc_cls:
        inst = MagicMock()
        inst.search_archive.return_value = 1
        inst.next_archive_entry.side_effect = [42, None]
        inst.load_fax.return_value = True
        inst.get_tiffpath.return_value = "/tmp/fax.tif"
        mock_arc_cls.return_value = inst

        with patch("namifax.cli.ocr_import.ocr_faxcontent", return_value="Invoice #12345"):
            res = ocr_import_main([])
            assert res == 0
            captured = capsys.readouterr()
            assert "Processing faxid 42" in captured.out


def test_create_thumbnails_execution(capsys):
    """Verify create_thumbnails searches archive and runs preview creation."""
    with patch("namifax.cli.create_thumbnails.FaxPDFArchive") as mock_arc_cls, \
         patch("namifax.cli.create_thumbnails.pdf_preview") as mock_preview, \
         patch("os.path.isfile", return_value=False):
        inst = MagicMock()
        inst.search_archive.return_value = 1
        inst.next_archive_entry.side_effect = [101, None]
        inst.load_fax.return_value = True
        inst.get_thumbnail.return_value = "/tmp/thumb.png"
        mock_arc_cls.return_value = inst

        res = create_thumbnails_main([])
        assert res == 0
        mock_preview.assert_called()
        captured = capsys.readouterr()
        assert "Done" in captured.out
