import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from sqlsession import empty_session, seeded_session
from namifax.services.archive_out import ArchiveOut


class TestArchiveOut(unittest.TestCase):
    def setUp(self):
        self.engine = empty_session()
        self.temp_dir = tempfile.mkdtemp()
        self.archive_out = ArchiveOut(db=self.engine, installdir=self.temp_dir)

    def tearDown(self):
        self.engine.disconnect()
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_create_outbound_fax(self):
        fax_dir = os.path.join(self.temp_dir, "faxes/sent/fax500")
        os.makedirs(fax_dir, exist_ok=True)

        ok = self.archive_out.create(
            path=fax_dir,
            userid=42,
            cid=10,
            origfaxnum="010-9999-8888",
            pages=2,
        )
        self.assertTrue(ok)
        fid = self.archive_out.get_fid()
        self.assertIsNotNone(fid)
        self.assertEqual(self.archive_out.get_userid(), 42)
        self.assertEqual(self.archive_out.get_companyid(), 10)
        self.assertEqual(self.archive_out.get_origfaxnum(), "01099998888")
        self.assertEqual(self.archive_out.get_pages(), 2)
        self.assertEqual(self.archive_out.get_inbox(), 0)

        # Check in DB
        self.engine.query("SELECT * FROM FaxArchive WHERE fid = :fid", {"fid": fid})
        rec = self.engine.get_records()[0]
        self.assertEqual(rec["inbox"], 0)
        self.assertEqual(rec["userid"], 42)
        self.assertEqual(rec["companyid"], 10)

    def test_load_and_delete_outbound_fax(self):
        fax_dir = os.path.join(self.temp_dir, "faxes/sent/fax501")
        os.makedirs(fax_dir, exist_ok=True)
        pdf_file = os.path.join(fax_dir, "fax.pdf")
        with open(pdf_file, "w") as f:
            f.write("sent fax pdf content")

        self.archive_out.create(fax_dir, 7, 2, "02-123-4567", 1)
        fid = self.archive_out.get_fid()

        reader = ArchiveOut(db=self.engine, installdir=self.temp_dir)
        self.assertTrue(reader.load_fax(fid))
        self.assertEqual(reader.get_userid(), 7)

        # Delete fax
        self.assertTrue(reader.delete_fax())
        self.assertFalse(os.path.exists(pdf_file))
        self.engine.query("SELECT count(*) as cnt FROM FaxArchive WHERE fid = :fid", {"fid": fid})
        self.assertEqual(self.engine.get_records()[0]["cnt"], 0)


if __name__ == "__main__":
    unittest.main()
