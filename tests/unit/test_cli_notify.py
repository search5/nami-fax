#!/usr/bin/env python3
"""Unit tests for avantfax.cli.notify module."""

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from namifax.cli.notify import run_notify


class TestCLINotify(unittest.TestCase):
    """Test suite for notify CLI script."""

    def test_usage_no_args(self):
        f = io.StringIO()
        with redirect_stdout(f):
            code = run_notify(["notify.py"])
        self.assertEqual(code, 0)
        self.assertEqual(f.getvalue(), "Usage: notify.php qfile why jobtime [nextTry]\n")

    def test_usage_missing_why(self):
        f = io.StringIO()
        with redirect_stdout(f):
            code = run_notify(["notify.py", "qfile1"])
        self.assertEqual(code, 0)
        self.assertEqual(f.getvalue(), "Usage: notify.php qfile why jobtime [nextTry]\n")

    def test_nonexistent_qfile(self):
        f = io.StringIO()
        with redirect_stdout(f):
            code = run_notify(["notify.py", "/tmp/nonexistent_qfile_12345", "done", "00:01:23"])
        self.assertEqual(code, 0)
        self.assertEqual(f.getvalue(), "/tmp/nonexistent_qfile_12345 doesn't exist\n")

    def test_qfile_parsing_done(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
            tf.write(
                "totpages:2\n"
                "status:Normal\n"
                "external:12345678\n"
                "jobid:999\n"
                "mailaddr:test@example.com\n"
                "owner:admin\n"
                "company:Acme Corp\n"
                "regarding:Important Docs\n"
                "postscript:0:0:/tmp/doc.ps\n"
            )
            qpath = tf.name

        try:
            f = io.StringIO()
            with redirect_stdout(f), \
                 patch("namifax.cli.notify.NFAddressBook") as mock_ab, \
                 patch("namifax.cli.notify.NFUserAccount") as mock_user, \
                 patch("namifax.cli.notify.ArchiveOut") as mock_out, \
                 patch("namifax.cli.notify.send_mail") as mock_send, \
                 patch("namifax.cli.notify.convert2pdf", return_value=True), \
                 patch("namifax.cli.notify.pdf_preview"):
                
                # Mock address book
                ab_inst = MagicMock()
                ab_inst.find_or_create_number.return_value = (1, 10, "created")
                ab_inst.create.return_value = True
                ab_inst.create_faxnumid.return_value = True
                ab_inst.get_companyid.return_value = 10
                ab_inst.get_company.return_value = "Acme Corp"
                ab_inst.get_description.return_value = ""
                mock_ab.return_value = ab_inst

                # Mock user account
                user_inst = MagicMock()
                user_inst.load_username.return_value = True
                user_inst.email = "admin@example.com"
                user_inst.get_uid.return_value = 1
                user_inst.language = "en"
                mock_user.return_value = user_inst

                # Mock ArchiveOut
                out_inst = MagicMock()
                out_inst.create.return_value = True
                out_inst.get_fid.return_value = 42
                mock_out.return_value = out_inst

                code = run_notify(["notify.py", qpath, "done", "00:01:23"])
                self.assertEqual(code, 0)
                out_str = f.getvalue()
                self.assertIn("totpages: 2", out_str)
                self.assertIn("status: Normal", out_str)
                self.assertIn("external: 12345678", out_str)
                self.assertIn("Done\n", out_str)

        finally:
            if os.path.exists(qpath):
                os.remove(qpath)


if __name__ == "__main__":
    unittest.main()
