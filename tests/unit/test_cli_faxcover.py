#!/usr/bin/env python3
"""Unit tests for avantfax.cli.faxcover module."""

import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from namifax.cli.faxcover import USAGE, run_faxcover


class TestCLIFaxcover(unittest.TestCase):
    """Test suite for faxcover CLI script."""

    def test_usage_no_args(self):
        f = io.StringIO()
        with redirect_stdout(f):
            code = run_faxcover(["faxcover.py"])
        self.assertEqual(code, 0)
        self.assertEqual(f.getvalue(), USAGE)

    def test_usage_missing_number(self):
        f = io.StringIO()
        with redirect_stdout(f):
            code = run_faxcover(["faxcover.py", "-f", "Sender"])
        self.assertEqual(code, 0)
        self.assertEqual(f.getvalue(), USAGE)

    def test_usage_missing_from(self):
        f = io.StringIO()
        with redirect_stdout(f):
            code = run_faxcover(["faxcover.py", "-n", "123456"])
        self.assertEqual(code, 0)
        self.assertEqual(f.getvalue(), USAGE)

    def test_valid_options_render(self):
        f = io.StringIO()
        with redirect_stdout(f):
            # Inject a DB with no matching user so no real database is opened
            db_inst = MagicMock()
            db_inst.query.return_value.executed = True
            db_inst.get_records.return_value = []

            code = run_faxcover(["faxcover.py", "-f", "Sender", "-n", "123456", "-r", "Subject"], db=db_inst)
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
