"""Unit tests for avantfax.auth.password (PWAuth layer)."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from namifax.auth.password import (
    PasswordManager,
    PWAuthBackend,
    STATUS_BAD_PASSWORD,
    STATUS_NO_USER,
    STATUS_VALID,
)


class TestPWAuth(unittest.TestCase):
    def test_legacy_md5_hash_and_verify(self):
        """Test AvantFAX default admin password MD5 hash."""
        # 'password' hash in create_tables.sql line 176 is '5f4dcc3b5aa765d61d8327deb882cf99'
        hashed = PasswordManager.hash_password("password")
        self.assertEqual(hashed, "5f4dcc3b5aa765d61d8327deb882cf99")

        self.assertTrue(PasswordManager.verify_password("password", "5f4dcc3b5aa765d61d8327deb882cf99"))
        self.assertFalse(PasswordManager.verify_password("wrongpass", "5f4dcc3b5aa765d61d8327deb882cf99"))
        self.assertFalse(PasswordManager.verify_password("Password", "5f4dcc3b5aa765d61d8327deb882cf99"))

    @patch("subprocess.run")
    def test_pwauth_backend_success(self, mock_run):
        """Test pwauth backend success (exit code 0)."""
        mock_proc = MagicMock()
        mock_proc.returncode = STATUS_VALID
        mock_run.return_value = mock_proc

        backend = PWAuthBackend(binary_path="/usr/local/bin/pwauth")
        self.assertTrue(backend.login("admin", "secret123"))

        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        self.assertEqual(kwargs["input"], "admin\nsecret123\n")

    @patch("subprocess.run")
    def test_pwauth_backend_invalid_user(self, mock_run):
        """Test pwauth backend when user does not exist (exit code 1)."""
        mock_proc = MagicMock()
        mock_proc.returncode = STATUS_NO_USER
        mock_run.return_value = mock_proc

        backend = PWAuthBackend()
        self.assertFalse(backend.login("nobody", "secret123"))

    @patch("subprocess.run")
    def test_pwauth_backend_bad_password(self, mock_run):
        """Test pwauth backend when password is incorrect (exit code 2)."""
        mock_proc = MagicMock()
        mock_proc.returncode = STATUS_BAD_PASSWORD
        mock_run.return_value = mock_proc

        backend = PWAuthBackend()
        self.assertFalse(backend.login("admin", "wrong_secret"))

    @patch("subprocess.run", side_effect=FileNotFoundError("pwauth binary not found"))
    def test_pwauth_backend_binary_missing(self, mock_run):
        """Test pwauth backend when binary is missing."""
        backend = PWAuthBackend(binary_path="/invalid/path/pwauth")
        self.assertFalse(backend.login("admin", "secret123"))
        self.assertIn("not found", backend.last_error)


if __name__ == "__main__":
    unittest.main()
