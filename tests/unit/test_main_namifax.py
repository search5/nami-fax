#!/usr/bin/env python3
"""Unit tests for namifax.main unified CLI and entry points."""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from namifax.main import (
    cron_main,
    dynconf_main,
    faxcover_main,
    faxrcvd_main,
    main,
    notify_main,
    phb_main,
    serve_main,
)


class TestNamifaxMain(unittest.TestCase):
    """Test suite for namifax CLI and shortcut entry points."""

    def test_main_help(self):
        f = io.StringIO()
        with redirect_stdout(f):
            code = main([])
        self.assertEqual(code, 0)
        self.assertIn("NamiFAX Modernized Enterprise System CLI", f.getvalue())

    def test_main_subcommand_dynconf(self):
        with patch("namifax.main.run_dynconf", return_value=0) as mock_cmd:
            code = main(["dynconf", "ttyS0", "12345"])
            self.assertEqual(code, 0)
            mock_cmd.assert_called_once()

    def test_shortcut_dynconf(self):
        with patch("namifax.main.run_dynconf", return_value=0) as mock_cmd, \
             patch("sys.exit") as mock_exit:
            dynconf_main()
            mock_exit.assert_called_once_with(0)

    def test_shortcut_cron(self):
        with patch("namifax.main.run_cron", return_value=0) as mock_cmd, \
             patch("sys.exit") as mock_exit:
            cron_main()
            mock_exit.assert_called_once_with(0)


if __name__ == "__main__":
    unittest.main()
