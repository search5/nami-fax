import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from sqlsession import empty_session, seeded_session
from namifax.services.archive_base import FaxPDFArchive


class TestFaxPDFArchive(unittest.TestCase):
    def setUp(self):
        self.engine = empty_session()


        self.temp_dir = tempfile.mkdtemp()
        self.archive = FaxPDFArchive(db=self.engine, installdir=self.temp_dir)

    def tearDown(self):
        self.engine.disconnect()
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_create_and_load_fax(self):
        rel_path = "/faxes/2026/09/29/fax1"
        abs_path = os.path.join(self.temp_dir, rel_path.lstrip("/"))
        os.makedirs(abs_path, exist_ok=True)

        ok = self.archive.create_fax(
            path=abs_path,
            faxnid=10,
            faxnumber="010-1234-5678",
            pages=2,
            date="2026-09-29 10:00:00",
            didr_id=5,
        )
        self.assertTrue(ok)
        fid = self.archive.get_fid()
        self.assertIsNotNone(fid)
        self.assertEqual(self.archive.get_origfaxnum(), "01012345678")
        self.assertEqual(self.archive.get_pages(), 2)
        self.assertEqual(self.archive.get_didr_id(), 5)
        self.assertTrue(self.archive.get_pdfpath().endswith("fax.pdf"))

        # Load into another instance
        reader = FaxPDFArchive(db=self.engine, installdir=self.temp_dir)
        self.assertTrue(reader.load_fax(fid))
        self.assertEqual(reader.get_fid(), fid)
        self.assertEqual(reader.get_origfaxnum(), "01012345678")

    def test_user_has_rights(self):
        abs_path = os.path.join(self.temp_dir, "fax_rights")
        os.makedirs(abs_path, exist_ok=True)
        self.archive.create_fax(
            path=abs_path,
            faxnid=1,
            faxnumber="1234",
            pages=1,
            date="2026-09-29 10:00:00",
            didr_id=10,
        )
        fid = self.archive.get_fid()
        # Update row with modemdev, userid, faxcatid
        self.engine.query(
            "UPDATE FaxArchive SET userid = 100, modemdev = 'ttyS0', faxcatid = 7 WHERE fid = :fid",
            {"fid": fid},
        )
        self.archive.load_fax(fid)

        # 1. User owns it
        self.assertTrue(self.archive.user_has_rights(userid=100, modems=[], routes=[], faxcat=[]))
        # 2. Modem matches
        self.assertTrue(self.archive.user_has_rights(userid=999, modems=["ttyS0"], routes=[], faxcat=[]))
        # 3. Route matches
        self.assertTrue(self.archive.user_has_rights(userid=999, modems=[], routes=[10], faxcat=[]))
        # 4. Fax category matches
        self.assertTrue(self.archive.user_has_rights(userid=999, modems=[], routes=[], faxcat=[7]))
        # 5. No match
        self.assertFalse(self.archive.user_has_rights(userid=999, modems=["ttyS1"], routes=[20], faxcat=[8]))

    def test_get_num_faxes_and_inbox_nav(self):
        for i in range(1, 4):
            path = os.path.join(self.temp_dir, f"fax_{i}")
            os.makedirs(path, exist_ok=True)
            self.archive.create_fax(path, i, f"100{i}", 1, f"2026-09-29 1{i}:00:00")
            fid = self.archive.get_fid()
            self.engine.query(
                "UPDATE FaxArchive SET inbox = 1, modemdev = 'ttyS0', faxcatid = 1 WHERE fid = :fid",
                {"fid": fid},
            )

        num = self.archive.get_num_faxes(devices=["ttyS0"], faxcats=[1])
        self.assertEqual(num, 3)

        # Test prev/next navigation
        self.archive.load_fax(2)
        self.archive.viewable_devices(devices=["ttyS0"], faxcats=[1])
        # In descending order (3, 2, 1): prev of 2 is 3, next of 2 is 1
        self.assertEqual(self.archive.get_fid_prev(), 3)
        self.assertEqual(self.archive.get_fid_next(), 1)

    def test_notes_and_categories(self):
        path = os.path.join(self.temp_dir, "fax_note")
        os.makedirs(path, exist_ok=True)
        self.archive.create_fax(path, 1, "1234", 1)
        fid = self.archive.get_fid()

        self.archive.set_note("Confidential fax", 3, 50)
        self.assertEqual(self.archive.get_description(), "Confidential fax")
        self.assertEqual(self.archive.get_faxcatid(), 3)
        self.assertEqual(self.archive.get_lastmoduser(), 50)

        self.archive.set_faxcontent("Extracted OCR text")
        self.engine.query("SELECT faxcontent FROM FaxArchive WHERE fid = :fid", {"fid": fid})
        records = self.engine.get_records()
        self.assertEqual(records[0]["faxcontent"], "Extracted OCR text")

        self.archive.remove_category(3)
        self.engine.query("SELECT faxcatid FROM FaxArchive WHERE fid = :fid", {"fid": fid})
        records = self.engine.get_records()
        self.assertIsNone(records[0]["faxcatid"])

    def test_delete_and_prune(self):
        rel = "faxes/del_test"
        path = os.path.join(self.temp_dir, rel)
        os.makedirs(path, exist_ok=True)
        pdf_file = os.path.join(path, "fax.pdf")
        with open(pdf_file, "w") as f:
            f.write("pdf data")

        self.archive.create_fax(path, 1, "1234", 1, date="2020-01-01 00:00:00")
        fid = self.archive.get_fid()
        self.assertTrue(os.path.exists(pdf_file))

        # Test delete_fax
        self.archive.delete_fax(fid)
        self.assertFalse(os.path.exists(pdf_file))
        self.engine.query("SELECT * FROM FaxArchive WHERE fid = :fid", {"fid": fid})
        self.assertEqual(len(self.engine.get_records()), 0)

        # Test prune_archive
        path2 = os.path.join(self.temp_dir, "faxes/prune_test")
        os.makedirs(path2, exist_ok=True)
        self.archive.create_fax(path2, 2, "5678", 1, date="2020-01-01 00:00:00")
        pruned = self.archive.prune_archive(30)
        self.assertEqual(pruned, 1)

    def test_reassign_and_company(self):
        path = os.path.join(self.temp_dir, "fax_comp")
        os.makedirs(path, exist_ok=True)
        self.archive.create_fax(path, 1, "1234", 1)
        fid = self.archive.get_fid()

        ok = self.archive.set_companyid(10)
        self.assertTrue(ok)
        self.assertEqual(self.archive.get_companyid(), 10)

        ok_re = self.archive.reassign(oldcid=10, newcid=20)
        self.assertTrue(ok_re)

        self.archive.load_fax(fid)
        self.assertEqual(self.archive.get_companyid(), 20)

    def test_search_archive_and_list_inbox(self):
        # Create inbox and archived faxes
        path_in = os.path.join(self.temp_dir, "fax_in")
        os.makedirs(path_in, exist_ok=True)
        self.archive.create_fax(path_in, 1, "02-111-2222", 1)
        fid_in = self.archive.get_fid()
        self.engine.query(
            "UPDATE FaxArchive SET inbox = 1, modemdev = 'ttyS0', faxcatid = 1 WHERE fid = :fid",
            {"fid": fid_in},
        )

        path_arch = os.path.join(self.temp_dir, "fax_arch")
        os.makedirs(path_arch, exist_ok=True)
        self.archive.create_fax(path_arch, 2, "02-333-4444", 2, date="2026-05-10 12:00:00")
        fid_arch = self.archive.get_fid()
        self.engine.query(
            "UPDATE FaxArchive SET inbox = 0, modemdev = NULL, description = 'Urgent Invoice', userid = 42 WHERE fid = :fid",
            {"fid": fid_arch},
        )

        # 1. list_inbox
        inbox_items = self.archive.list_inbox(devices=["ttyS0"], index=0, limit=10, faxcats=[1])
        self.assertEqual(len(inbox_items), 1)
        self.assertEqual(inbox_items[0]["fid"], fid_in)

        # 2. search_archive - sent faxes by userid
        crit_sent = {"sentrecvd": "s", "userid": 42, "pagelimit": 10, "pageindex": 0}
        cnt = self.archive.search_archive(crit_sent)
        self.assertEqual(cnt, 1)
        next_fid = self.archive.next_archive_entry()
        self.assertEqual(next_fid, fid_arch)
        self.assertIsNone(self.archive.next_archive_entry())

        # 3. search_archive - keywords (as superuser)
        crit_kw = {"keywords": "Urgent", "superuser": True, "pagelimit": 10, "pageindex": 0}
        cnt_kw = self.archive.search_archive(crit_kw)
        self.assertEqual(cnt_kw, 1)


if __name__ == "__main__":
    unittest.main()
