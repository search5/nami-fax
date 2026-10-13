import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from sqlsession import empty_session, seeded_session
from namifax.services.archive_in import ArchiveIn


class TestArchiveIn(unittest.TestCase):
    def setUp(self):
        self.engine = empty_session()
        self.temp_dir = tempfile.mkdtemp()
        self.archive_in = ArchiveIn(db=self.engine, installdir=self.temp_dir)

    def tearDown(self):
        self.engine.disconnect()
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_create_inbox_fax(self):
        fax_dir = os.path.join(self.temp_dir, "faxes/inbox/fax100")
        os.makedirs(fax_dir, exist_ok=True)

        ok = self.archive_in.create(
            path=fax_dir,
            faxnid=1,
            faxnumber="01012345678",
            modem="ttyS0",
            pages=3,
            date="2026-09-29 12:00:00",
            didr_id=7,
        )
        self.assertTrue(ok)
        fid = self.archive_in.get_fid()
        self.assertIsNotNone(fid)
        self.assertEqual(self.archive_in.get_inbox(), 1)
        self.assertEqual(self.archive_in.get_modemdev(), "ttyS0")
        self.assertEqual(self.archive_in.get_pages(), 3)
        self.assertEqual(self.archive_in.get_didr_id(), 7)

    def test_set_archivebox(self):
        fax_dir = os.path.join(self.temp_dir, "faxes/inbox/fax101")
        os.makedirs(fax_dir, exist_ok=True)

        self.archive_in.create(
            path=fax_dir,
            faxnid=1,
            faxnumber="01012345678",
            modem="ttyS0",
            pages=1,
        )
        fid = self.archive_in.get_fid()

        # Archive it
        ok = self.archive_in.set_archivebox(fid)
        self.assertTrue(ok)
        self.assertEqual(self.archive_in.get_inbox(), 0)

        # Check DB
        self.engine.query("SELECT inbox FROM FaxArchive WHERE fid = :fid", {"fid": fid})
        rec = self.engine.get_records()[0]
        self.assertEqual(rec["inbox"], 0)

    def test_prune_inbox(self):
        old_date = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d 10:00:00")
        recent_date = datetime.now().strftime("%Y-%m-%d 10:00:00")

        # Create 2 old inbox faxes and 1 recent inbox fax
        for i in range(1, 3):
            path = os.path.join(self.temp_dir, f"fax_old_{i}")
            os.makedirs(path, exist_ok=True)
            self.archive_in.create(path, i, f"100{i}", "ttyS0", 1, date=old_date)

        path_rec = os.path.join(self.temp_dir, "fax_recent")
        os.makedirs(path_rec, exist_ok=True)
        self.archive_in.create(path_rec, 99, "9999", "ttyS0", 1, date=recent_date)

        # Prune inbox for faxes older than 30 days
        archived_count = self.archive_in.prune_inbox(30)
        self.assertEqual(archived_count, 2)

        # Check in DB that old ones are inbox=0 and recent is still inbox=1
        self.engine.query("SELECT count(*) as cnt FROM FaxArchive WHERE inbox = 1")
        rec = self.engine.get_records()[0]
        self.assertEqual(rec["cnt"], 1)

    def test_rotate_fax_error_cases(self):
        # 1. No fid loaded
        empty_svc = ArchiveIn(db=self.engine, installdir=self.temp_dir)
        self.assertFalse(empty_svc.rotate_fax())
        self.assertEqual(empty_svc.get_error(), "No fid loaded")

        # 2. Not in inbox
        fax_dir = os.path.join(self.temp_dir, "fax_archived")
        os.makedirs(fax_dir, exist_ok=True)
        self.archive_in.create(fax_dir, 1, "1234", "ttyS0", 1)
        fid = self.archive_in.get_fid()
        self.archive_in.set_archivebox(fid)

        self.assertFalse(self.archive_in.rotate_fax())
        self.assertEqual(self.archive_in.get_error(), "Not in inbox")


if __name__ == "__main__":
    unittest.main()
