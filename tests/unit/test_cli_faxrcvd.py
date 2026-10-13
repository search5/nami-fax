#!/usr/bin/env python3
"""Unit tests for avantfax.cli.faxrcvd module."""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from namifax.cli.faxrcvd import run_faxrcvd


class TestCLIFaxrcvd(unittest.TestCase):
    """Test suite for faxrcvd CLI script."""

    def test_usage_no_args(self):
        f = io.StringIO()
        with redirect_stdout(f):
            code = run_faxrcvd(["faxrcvd.py"])
        self.assertEqual(code, 0)
        self.assertEqual(f.getvalue(), "Usage: faxrcvd.php file devID commID error-msg [CIDNumber] [CIDName] [DIDnum]\n")

    def test_usage_missing_args(self):
        f = io.StringIO()
        with redirect_stdout(f):
            code = run_faxrcvd(["faxrcvd.py", "fax.tif"])
        self.assertEqual(code, 0)
        self.assertEqual(f.getvalue(), "Usage: faxrcvd.php file devID commID error-msg [CIDNumber] [CIDName] [DIDnum]\n")

    def test_nonexistent_file(self):
        f = io.StringIO()
        with redirect_stdout(f), patch("namifax.cli.faxrcvd.FaxModem"):
            code = run_faxrcvd(["faxrcvd.py", "/tmp/nonexistent_fax_9999.tif", "ttyS0", "comm01", "none"])
        self.assertEqual(code, 0)
        self.assertEqual(f.getvalue(), "")

    def test_valid_processing_flow(self):
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tf:
            tf.write(b"mock tiff data")
            tif_path = tf.name

        try:
            f = io.StringIO()
            with redirect_stdout(f), \
                 patch("namifax.cli.faxrcvd.FaxModem") as mock_modem, \
                 patch("namifax.cli.faxrcvd.NFAddressBook") as mock_ab, \
                 patch("namifax.cli.faxrcvd.ArchiveIn") as mock_in, \
                 patch("namifax.cli.faxrcvd.send_mail") as mock_send, \
                 patch("namifax.cli.faxrcvd.faxinfo") as mock_finfo, \
                 patch("namifax.cli.faxrcvd.tiff2pdf"), patch("namifax.cli.faxrcvd.copy_tiff", return_value=True), \
                 patch("namifax.cli.faxrcvd.static_preview"):

                # Mock modem
                m_inst = MagicMock()
                m_inst.load_device.return_value = True
                m_inst.get_contact.return_value = "admin@example.com"
                m_inst.get_printer.return_value = None
                m_inst.get_faxcatid.return_value = None
                mock_modem.return_value = m_inst

                # Mock faxinfo
                mock_finfo.return_value = {
                    "Sender": "12345678",
                    "Pages": 3,
                    "Received": "2026:09:29 12:00:00",
                }

                # Mock address book
                ab_inst = MagicMock()
                ab_inst.loadbyfaxnum.return_value = True
                ab_inst.get_faxnumid.return_value = 5
                ab_inst.get_company.return_value = "Sender Inc"
                ab_inst.get_description.return_value = ""
                ab_inst.get_category.return_value = None
                ab_inst.get_printer.return_value = None
                ab_inst.get_email.return_value = None
                ab_inst.find_or_create_number.return_value = (1, 1, "found")
                mock_ab.return_value = ab_inst

                # Mock ArchiveIn
                in_inst = MagicMock()
                in_inst.create.return_value = True
                in_inst.get_fid.return_value = 101
                mock_in.return_value = in_inst

                code = run_faxrcvd(["faxrcvd.py", tif_path, "ttyS0", "comm01", "none"])
                self.assertEqual(code, 0)
                out = f.getvalue()
                self.assertIn("Create PDF\n", out)
                self.assertIn("Create Thumbnails\n", out)

        finally:
            if os.path.exists(tif_path):
                os.remove(tif_path)


if __name__ == "__main__":
    unittest.main()
