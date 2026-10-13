import io
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from namifax.cli.cron import USAGE, run_cron


class TestCliCron(unittest.TestCase):
    def test_cron_no_args(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = run_cron(["cron.py"])
        self.assertEqual(code, 0)
        self.assertEqual(buf.getvalue(), USAGE)

    def test_cron_invalid_opt(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = run_cron(["cron.py", "-z"])
        self.assertEqual(code, 0)
        self.assertEqual(buf.getvalue(), USAGE)

    def test_cron_execution(self):
        mock_inbox = MagicMock()
        mock_archive = MagicMock()

        tmp_dir = tempfile.mkdtemp()
        try:
            # Create old temp file
            old_file = os.path.join(tmp_dir, "old_temp.txt")
            with open(old_file, "w") as f:
                f.write("old data")

            # Set mtime to 5 days ago
            past_time = time.time() - (5 * 86400)
            os.utime(old_file, (past_time, past_time))

            code = run_cron(
                ["cron.py", "-t", "2", "-i", "30", "-d", "60"],
                archive_in=mock_inbox,
                archive_base=mock_archive,
                tmp_dir=tmp_dir,
            )
            self.assertEqual(code, 0)
            mock_inbox.prune_inbox.assert_called_with(30)
            mock_archive.prune_archive.assert_called_with(60)
            self.assertFalse(os.path.exists(old_file))
        finally:
            if os.path.exists(tmp_dir):
                import shutil
                shutil.rmtree(tmp_dir)


if __name__ == "__main__":
    unittest.main()
