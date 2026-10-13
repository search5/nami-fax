"""Unit tests for avantfax.common.upload (FileUpload layer)."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from namifax.common.upload import (
    FU_INVALIDMIME,
    FU_NO_FILE,
    FU_OVER_SIZE,
    FileUpload,
)


class TestFileUpload(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

        # Create dummy upload source file
        self.sample_file = self.tmp_path / "sample.pdf"
        self.sample_file.write_bytes(b"%PDF-1.4 dummy content for avantfax")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_sanitize_filename(self):
        """Verify filename sanitization replacing forbidden characters."""
        fu = FileUpload()
        clean = fu.sanitize_filename("../../danger file (1).PDF")
        self.assertNotIn("..", clean)
        self.assertNotIn("/", clean)
        self.assertNotIn(" ", clean)
        self.assertEqual(clean, "danger_file__1_.PDF")

    def test_size_limit_exceeded(self):
        """Verify rejecting file when size limit is exceeded."""
        fu = FileUpload()
        fu.limit_size(10)  # 10 bytes limit

        file_payload = {
            "name": "large.pdf",
            "tmp_name": str(self.sample_file),
            "size": len(self.sample_file.read_bytes()),
            "type": "application/pdf",
            "error": 0,
        }

        self.assertFalse(fu.load_file(file_payload))
        self.assertEqual(fu.get_error(), FU_OVER_SIZE)

    def test_mimetype_whitelist(self):
        """Verify mime type filtering."""
        fu = FileUpload()
        fu.limit_mimetype(["image/tiff", "image/jpeg"])

        file_payload = {
            "name": "sample.pdf",
            "tmp_name": str(self.sample_file),
            "size": len(self.sample_file.read_bytes()),
            "type": "application/pdf",
            "error": 0,
        }

        self.assertFalse(fu.load_file(file_payload))
        self.assertEqual(fu.get_error(), FU_INVALIDMIME)

    def test_successful_load_and_movefile(self):
        """Verify successful load, randname generation, and moving file."""
        fu = FileUpload()
        fu.limit_mimetype(["application/pdf"])
        fu.limit_size(1024 * 1024)

        file_payload = {
            "name": "document.pdf",
            "tmp_name": str(self.sample_file),
            "size": len(self.sample_file.read_bytes()),
            "type": "application/pdf",
            "error": 0,
        }

        self.assertTrue(fu.load_file(file_payload))
        self.assertEqual(fu.get_name(), "document.pdf")
        self.assertEqual(fu.get_mimetype(), "application/pdf")
        self.assertGreater(fu.get_filesize(), 0)

        # Set randname
        rand_name = fu.set_randname(n=8)
        self.assertTrue(rand_name.endswith("document.pdf"))
        self.assertEqual(len(rand_name), 8 + len("document.pdf"))

        # Move to destination directory
        dest_dir = self.tmp_path / "uploads"
        self.assertTrue(fu.movefile(dest_dir))
        self.assertTrue((dest_dir / rand_name).exists())
        self.assertEqual((dest_dir / rand_name).read_bytes(), b"%PDF-1.4 dummy content for avantfax")


if __name__ == "__main__":
    unittest.main()
