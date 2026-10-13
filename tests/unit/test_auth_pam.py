"""Unit tests for avantfax.auth.pam (PAMAuth layer)."""

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from namifax.auth.pam import PAMAuthBackend


class TestPAMAuth(unittest.TestCase):
    def test_pam_empty_credentials(self):
        """Test PAM rejecting empty credentials."""
        backend = PAMAuthBackend()
        self.assertFalse(backend.login("", "password"))
        self.assertIn("cannot be empty", backend.last_error)

        self.assertFalse(backend.login("admin", ""))
        self.assertIn("cannot be empty", backend.last_error)

    def test_pam_custom_driver_success(self):
        """Test PAM authentication with injected successful driver."""
        mock_driver = MagicMock(return_value=(True, None))
        backend = PAMAuthBackend(pam_driver=mock_driver)

        self.assertTrue(backend.login("testuser", "correct_pwd", service="avantfax"))
        mock_driver.assert_called_once_with("testuser", "correct_pwd", "avantfax")
        self.assertIsNone(backend.last_error)

    def test_pam_custom_driver_failure(self):
        """Test PAM authentication with injected failing driver."""
        mock_driver = MagicMock(return_value=(False, "Authentication failure"))
        backend = PAMAuthBackend(pam_driver=mock_driver)

        self.assertFalse(backend.login("testuser", "wrong_pwd"))
        self.assertEqual(backend.last_error, "Authentication failure")

    def test_pam_unavailable_fallback(self):
        """Test PAM graceful handling when PAM is not installed/supported."""
        backend = PAMAuthBackend(pam_driver=None)
        # Force ctypes and pam import to fail
        backend._pam_available = False
        self.assertFalse(backend.login("testuser", "pwd"))
        self.assertIn("PAM is not supported", backend.last_error)


if __name__ == "__main__":
    unittest.main()
