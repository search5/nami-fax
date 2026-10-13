#!/usr/bin/env python3
"""Unit tests for namifax.services.scheduler module."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from namifax.services.scheduler import NamiFaxScheduler, get_scheduler


class TestScheduler(unittest.TestCase):
    """Test suite for APScheduler wrapper and background jobs."""

    def setUp(self):
        self.scheduler = NamiFaxScheduler()

    def tearDown(self):
        self.scheduler.stop()

    def test_singleton_getter(self):
        s1 = get_scheduler()
        s2 = get_scheduler()
        self.assertIs(s1, s2)

    def test_job_phonebook_sync(self):
        with patch("namifax.services.scheduler.export_phonebook_count", return_value=5) as mock_phb, \
                patch("namifax.services.scheduler.cli_session") as session:
            session.return_value.__enter__.return_value = MagicMock()
            with patch("namifax.services.scheduler.cfg") as config:
                config.JOBS = ("tmp", "inbox", "lifecycle", "phonebook")
                config.running_marker.return_value = None
                self.scheduler.job_phonebook_sync()
            mock_phb.assert_called_once()

    def test_start_and_stop_fallback(self):
        self.scheduler.start()
        self.assertTrue(self.scheduler.is_running)
        self.scheduler.stop()
        self.assertFalse(self.scheduler.is_running)


if __name__ == "__main__":
    unittest.main()
