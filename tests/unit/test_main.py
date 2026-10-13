#!/usr/bin/env python3
"""Unit tests for avantfax.main entry point CLI."""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from namifax.main import USAGE, main


class TestMainCLI(unittest.TestCase):
    """Test suite for unified CLI entry point."""

    def test_help_no_args(self):
        f = io.StringIO()
        with redirect_stdout(f):
            code = main([])
        self.assertEqual(code, 0)
        self.assertEqual(f.getvalue().strip(), USAGE.strip())

    def test_unknown_command(self):
        f = io.StringIO()
        with redirect_stdout(f):
            code = main(["foobar"])
        self.assertEqual(code, 1)
        self.assertIn("Unknown command: foobar", f.getvalue())

    def test_subcommand_dispatch_dynconf(self):
        with patch("namifax.main.run_dynconf", return_value=0) as mock_dc:
            code = main(["dynconf", "ttyS0", "12345"])
            self.assertEqual(code, 0)
            mock_dc.assert_called_once()


if __name__ == "__main__":
    unittest.main()
