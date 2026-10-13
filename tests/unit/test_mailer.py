"""Unit tests for avantfax.services.mailer (Mailer layer)."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from namifax.services.mailer import MailerService


class TestMailerService(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

        # Create dummy PDF for attachment
        self.sample_pdf = self.tmp_path / "fax_123.pdf"
        self.sample_pdf.write_bytes(b"%PDF-dummy-fax-content")

        # Create dummy Image for embed
        self.sample_img = self.tmp_path / "logo.png"
        self.sample_img.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRdummy")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_message_assembly(self):
        """Verify message plaintext and HTML generation with signatures."""
        mailer = MailerService(
            admin_email="faxadmin@test.com",
            email_sig_text="-- \nAvantFAX Fax Server",
            email_sig_html="<hr><b>AvantFAX</b>",
            spool_mode=True,
        )

        mailer.set_message("Fax received from 123456\nPages: 2", subject="New Fax")
        self.assertTrue(mailer.sendmail("user@example.com"))

        spooled = mailer.get_spooled_messages()
        self.assertEqual(len(spooled), 1)
        msg = spooled[0]

        self.assertEqual(msg["To"], "user@example.com")
        self.assertEqual(msg["From"], "NamiFAX <faxadmin@test.com>")
        self.assertEqual(msg["Subject"], "New Fax")

        # Verify multipart content
        body = msg.get_body(("plain",)).get_content() + msg.get_body(("html",)).get_content()    # (bodies are Base64 by default)
        self.assertIn("Fax received from 123456", body)
        self.assertIn("AvantFAX Fax Server", body)
        self.assertIn("<br />", body)

    def test_attach_file(self):
        """Verify attaching a file."""
        mailer = MailerService(spool_mode=True)
        mailer.set_message("Please find fax attached.")
        self.assertTrue(mailer.attach_file(self.sample_pdf, alt_name="received_fax.pdf"))

        self.assertTrue(mailer.sendmail("recipient@test.com", subject="Fax Attachment"))
        spooled = mailer.get_spooled_messages()
        msg = spooled[0]

        # Verify attachment header in payload
        payload_str = str(msg)
        self.assertIn("received_fax.pdf", payload_str)
        self.assertIn("application/pdf", payload_str)

    @patch("smtplib.SMTP")
    def test_smtp_dispatch(self, mock_smtp_class):
        """Verify actual SMTP client dispatch."""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        mailer = MailerService(
            smtp_server="smtp.example.com",
            smtp_port=587,
            smtp_user="user",
            smtp_password="pwd",
            use_tls=True,
            spool_mode=False,
        )
        mailer.set_message("Test SMTP dispatch")
        success = mailer.sendmail("target@example.com", subject="Test Subject")

        self.assertTrue(success)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "pwd")
        mock_server.send_message.assert_called_once()


if __name__ == "__main__":
    unittest.main()
