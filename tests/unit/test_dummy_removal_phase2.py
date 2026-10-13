"""Unit tests for Phase 2 legacy divergence fixes (AUDIT-04, AUDIT-05, AUDIT-06)."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from pyramid import testing
from pyramid.httpexceptions import HTTPNotFound

from namifax.common.helpers import convert2pdf, pdf_preview, static_preview, tiff2pdf
from sqlsession import bare_session, empty_session, seeded_session
from namifax.views.ajax import ajax_archivebook_view
from namifax.views.inbox import fax_download_view


class TestDummyRemovalPhase2(unittest.TestCase):
    """Test suite covering Phase 2 refactoring (AUDIT-04, AUDIT-05, AUDIT-06)."""

    def setUp(self):
        self.config = testing.setUp()
        self.test_dir = tempfile.mkdtemp()
        self.db = seeded_session()
        self.session = self.db

    def tearDown(self):
        testing.tearDown()
        self.db.disconnect()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    # =========================================================================
    # AUDIT-04: Fax Download 404 for Missing Faxes & Real Serving for fid=1
    # =========================================================================
    def test_fax_download_nonexistent_raises_404(self):
        """Verify that requesting a non-existent fax ID raises HTTPNotFound (404)."""
        req = testing.DummyRequest()
        req.matchdict = {"fid": "99999"}
        req.params = {"format": "pdf"}

        with self.assertRaises(HTTPNotFound):
            fax_download_view(req)

    def test_fax_download_real_fid_1_serves_actual_pdf(self):
        """Verify that requesting fid=1 serves the real disk file with 200 OK."""
        req = testing.DummyRequest()
        req.db = self.db
        req.dbsession = self.session
        req.matchdict = {"fid": "1"}
        req.params = {"format": "pdf"}

        from namifax.services.fax_access import FaxAccess

        with patch.object(FaxAccess, "for_request", classmethod(lambda cls, r: cls(uid=1, username="admin", superuser=True))):
            res = fax_download_view(req)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, "application/pdf")
        # Ensure it does NOT contain the legacy synthetic stub marker
        self.assertNotIn(b"synthetic PDF binary stream", res.body)
        self.assertTrue(len(res.body) > 0)

    # =========================================================================
    # AUDIT-05: Conversion Helper Failure Handling (No Dummy/Stub Files)
    # =========================================================================
    def test_convert2pdf_failure_returns_false_and_creates_no_file(self):
        """Verify convert2pdf returns False and creates no fake PDF on missing/empty images."""
        out_pdf = os.path.join(self.test_dir, "fax.pdf")

        # 1. Empty image list
        res_empty = convert2pdf(self.test_dir, [])
        self.assertFalse(res_empty)
        self.assertFalse(os.path.exists(out_pdf))

        # 2. Non-existent images
        res_nonexistent = convert2pdf(self.test_dir, [os.path.join(self.test_dir, "ghost.png")])
        self.assertFalse(res_nonexistent)
        self.assertFalse(os.path.exists(out_pdf))

    def test_tiff2pdf_failure_returns_false_and_creates_no_file(self):
        """Verify tiff2pdf returns False and does not create stub PDF on invalid input."""
        bad_tiff = os.path.join(self.test_dir, "bad.tif")
        out_pdf = os.path.join(self.test_dir, "bad_out.pdf")

        # 1. Non-existent tiff file
        res_missing = tiff2pdf(bad_tiff, out_pdf)
        self.assertFalse(res_missing)
        self.assertFalse(os.path.exists(out_pdf))

        # 2. Corrupt/Invalid tiff file
        with open(bad_tiff, "wb") as f:
            f.write(b"not a valid tiff image content")

        res_corrupt = tiff2pdf(bad_tiff, out_pdf)
        self.assertFalse(res_corrupt)
        self.assertFalse(os.path.exists(out_pdf))

    def test_static_preview_failure_returns_false_and_creates_no_empty_file(self):
        """Verify static_preview returns False and avoids creating empty thumb.png when tiffile is missing."""
        empty_folder = os.path.join(self.test_dir, "empty_fax_dir")
        os.makedirs(empty_folder, exist_ok=True)

        res = static_preview(empty_folder, pages=1)
        self.assertFalse(res)
        thumb_path = os.path.join(empty_folder, "thumb.png")
        self.assertFalse(os.path.exists(thumb_path))

    def test_pdf_preview_failure_returns_false_and_creates_no_empty_file(self):
        """Verify pdf_preview returns False when no fax.pdf or fax.tif exists."""
        empty_folder = os.path.join(self.test_dir, "empty_preview_dir")
        os.makedirs(empty_folder, exist_ok=True)

        res = pdf_preview(empty_folder)
        self.assertFalse(res)
        thumb_path = os.path.join(empty_folder, "thumb.png")
        self.assertFalse(os.path.exists(thumb_path))

    # =========================================================================
    # AUDIT-06: Address Book AJAX Auto-Suggest Stub Removal
    # =========================================================================
    def test_ajax_archivebook_nonexistent_returns_empty_xml(self):
        """Verify ajax_archivebook returns empty <response></response> without hardcoded Acme Corp."""
        req = testing.DummyRequest()
        req.db = self.db
        req.dbsession = self.session
        req.params = {"q": "NonExistentCompanyXYZ"}

        res = ajax_archivebook_view(req)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, "text/xml")
        self.assertNotIn("Acme Corp", res.text)
        self.assertIn("<response></response>", res.text.replace(" ", "").replace("\n", ""))

    def test_ajax_archivebook_match_returns_matched_records(self):
        """Verify ajax_archivebook returns actual matched company from database."""
        req = testing.DummyRequest()
        req.db = self.db
        req.dbsession = self.session
        req.params = {"q": "Acme"}

        res = ajax_archivebook_view(req)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Acme Corp", res.text)
        self.assertIn("<cid>", res.text)
