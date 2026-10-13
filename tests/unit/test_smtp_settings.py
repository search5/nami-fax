import unittest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

import namifax.models  # noqa: F401  (registers every model)
from namifax.db.provider import create_sa_engine
from namifax.models.meta import Base
from namifax.services.smtp_settings import SmtpSettingsService, SmtpConfig, SmtpTestResult
from namifax.services.mailer import MailerService


class TestSmtpSettingsService(unittest.TestCase):
    def setUp(self):
        self.engine = create_sa_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.service = SmtpSettingsService(self.session)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_default_settings(self):
        config = self.service.get_settings()
        self.assertIsInstance(config, SmtpConfig)
        self.assertEqual(config.smtp_host, "localhost")
        self.assertEqual(config.smtp_port, 25)
        self.assertEqual(config.smtp_security, "NONE")
        self.assertFalse(config.smtp_auth)

    def test_save_and_retrieve_settings(self):
        new_data = {
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_security": "STARTTLS",
            "smtp_auth": True,
            "smtp_username": "faxuser@example.com",
            "smtp_password": "secretpassword",
            "from_email": "noreply@example.com",
            "from_name": "Example NamiFAX",
            "email_sig_text": "Best regards,\nNamiFAX System",
            "email_sig_html": "<p>Best regards,<br>NamiFAX System</p>",
        }
        saved = self.service.save_settings(new_data)
        self.assertTrue(saved)

        config = self.service.get_settings()
        self.assertEqual(config.smtp_host, "smtp.example.com")
        self.assertEqual(config.smtp_port, 587)
        self.assertEqual(config.smtp_security, "STARTTLS")
        self.assertTrue(config.smtp_auth)
        self.assertEqual(config.smtp_username, "faxuser@example.com")
        self.assertEqual(config.smtp_password, "secretpassword")
        self.assertEqual(config.from_email, "noreply@example.com")
        self.assertEqual(config.from_name, "Example NamiFAX")

    def test_invalid_port_validation(self):
        with self.assertRaises(ValueError):
            self.service.save_settings({"smtp_port": 99999})
        with self.assertRaises(ValueError):
            self.service.save_settings({"smtp_port": -1})

    @patch("smtplib.SMTP")
    def test_test_connection_success(self, mock_smtp):
        mock_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_instance

        config = SmtpConfig(
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_security="STARTTLS",
            smtp_auth=True,
            smtp_username="user@example.com",
            smtp_password="pw",
            from_email="admin@example.com",
        )
        res = self.service.test_connection("recipient@example.com", config)
        self.assertTrue(res.success)
        mock_instance.starttls.assert_called_once()
        mock_instance.login.assert_called_once_with("user@example.com", "pw")
        mock_instance.send_message.assert_called_once()

    @patch("smtplib.SMTP")
    def test_test_connection_failure(self, mock_smtp):
        mock_smtp.side_effect = ConnectionRefusedError("Connection refused by host")

        config = SmtpConfig(
            smtp_host="invalid.host",
            smtp_port=25,
            from_email="admin@example.com",
        )
        res = self.service.test_connection("recipient@example.com", config)
        self.assertFalse(res.success)
        self.assertIn("Connection refused", res.message)

    def test_mailer_from_settings(self):
        new_data = {
            "smtp_host": "mail.corporate.com",
            "smtp_port": 465,
            "smtp_security": "SSL",
            "smtp_auth": True,
            "smtp_username": "fax@corporate.com",
            "smtp_password": "secret",
            "from_email": "fax@corporate.com",
        }
        self.service.save_settings(new_data)

        mailer = MailerService.from_settings(self.session)
        self.assertEqual(mailer.smtp_server, "mail.corporate.com")
        self.assertEqual(mailer.smtp_port, 465)
        self.assertTrue(mailer.use_ssl)
        self.assertFalse(mailer.use_tls)
        self.assertEqual(mailer.smtp_user, "fax@corporate.com")


if __name__ == "__main__":
    unittest.main()
