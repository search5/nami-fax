import os
import shutil
import tempfile
import unittest
from sqlsession import empty_session, seeded_session
from src.namifax.services.cover_studio import CoverStudioService


class TestCoverStudio(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.covers_dir = os.path.join(self.temp_dir, "covers")
        os.makedirs(self.covers_dir, exist_ok=True)

        self.db = seeded_session()
        self.service = CoverStudioService(db=self.db, covers_dir=self.covers_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_template_valid_formats(self):
        # 1. PostScript
        res_ps = self.service.save_template(
            filename="standard.ps",
            content=b"%!PS-Adobe-3.0\n%%Title: Standard Cover\n",
            title="Standard PS Cover",
        )
        self.assertTrue(res_ps["success"])
        self.assertIsNotNone(res_ps["cover_id"])
        self.assertTrue(os.path.exists(os.path.join(self.covers_dir, "standard.ps")))

        # 2. HTML
        res_html = self.service.save_template(
            filename="modern.html",
            content=b"<html><body><h1>{{ regarding }}</h1><p>{{ comments }}</p></body></html>",
            title="Modern HTML Cover",
        )
        self.assertTrue(res_html["success"])
        self.assertIsNotNone(res_html["cover_id"])

        # 3. PDF
        res_pdf = self.service.save_template(
            filename="corporate.pdf",
            content=b"%PDF-1.4\n%%EOF",
            title="Corporate PDF Cover",
        )
        self.assertTrue(res_pdf["success"])

    def test_save_template_invalid_format(self):
        res = self.service.save_template(
            filename="malicious.exe",
            content=b"MZ\x90\x00",
            title="Bad Executable",
        )
        self.assertFalse(res["success"])
        self.assertIn("Unsupported", res["message"])

    def test_render_template_html(self):
        res = self.service.save_template(
            filename="contract.html",
            content=b"<h1>Fax to {{ to_person }} at {{ to_company }}</h1><p>Subject: {{ regarding }}</p>",
            title="Contract Cover",
        )
        cover_id = res["cover_id"]

        rendered = self.service.render_template(
            cover_id=cover_id,
            context={
                "to_person": "Jane Doe",
                "to_company": "Acme Corp",
                "regarding": "Project Alpha",
            },
        )
        self.assertIn(b"Jane Doe", rendered)
        self.assertIn(b"Acme Corp", rendered)
        self.assertIn(b"Project Alpha", rendered)

    def test_get_supported_tags(self):
        tags = self.service.get_supported_tags()
        self.assertIsInstance(tags, list)
        keys = [t["tag"] for t in tags]
        self.assertIn("to_person", keys)
        self.assertIn("regarding", keys)
        self.assertIn("comments", keys)


if __name__ == "__main__":
    unittest.main()
