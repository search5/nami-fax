import io
import unittest
from unittest.mock import patch
from src.namifax.cli.print_in import main


class TestCliPrintIn(unittest.TestCase):
    @patch("src.namifax.cli.print_in.process_inbound_print_job")
    def test_print_in_from_stdin_with_tag(self, mock_process):
        mock_process.return_value = {
            "dispatched": True,
            "destination": "02-123-4567",
        }
        fake_stdin = io.BytesIO(b"Data with [[FAX: 02-123-4567]]")

        with patch("sys.stdin.isatty", return_value=False), patch("sys.stdin.buffer.read", return_value=fake_stdin.getvalue()):
            ret = main(["print_in.py", "1", "alice", "Test Doc", "1", ""])
            self.assertEqual(ret, 0)
            mock_process.assert_called_once()

    @patch("src.namifax.cli.print_in.process_inbound_print_job")
    def test_a_failed_dispatch_makes_the_backend_fail(self, mock_process):
        mock_process.return_value = {"dispatched": False, "status": "FAILED", "message": "sendfax is not installed"}
        with patch("sys.stdin.isatty", return_value=False), patch("sys.stdin.buffer.read", return_value=b"x [[FAX: 02-1]]"):
            self.assertEqual(main(["print_in.py", "1", "alice", "Doc", "1", ""]), 1)

    def test_print_in_empty_input(self):
        with patch("sys.stdin.isatty", return_value=True):
            ret = main(["print_in.py"])
            self.assertEqual(ret, 0)


if __name__ == "__main__":
    unittest.main()
