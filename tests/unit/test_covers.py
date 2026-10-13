import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from sqlsession import empty_session, seeded_session
from namifax.services.covers import Covers, CoverService


class TestCovers(unittest.TestCase):
    def setUp(self):
        self.engine = empty_session()

        self.covers = Covers(db=self.engine)

    def tearDown(self):
        self.engine.disconnect()

    def test_empty_covers(self):
        res = self.covers.get_covers()
        self.assertIsNone(res)
        self.assertEqual(self.covers.error, "No cover pages configured")

    def test_create_valid(self):
        ok = self.covers.create("Standard Cover", "standard.ps")
        self.assertTrue(ok)
        self.assertIsNotNone(self.covers.get_cover_id())
        self.assertEqual(self.covers.get_title(), "Standard Cover")
        self.assertEqual(self.covers.get_file(), "standard.ps")

    def test_create_invalid_input(self):
        ok1 = self.covers.create("", "standard.ps")
        self.assertFalse(ok1)
        self.assertEqual(self.covers.error, "Cover page could not be created")

        ok2 = self.covers.create("Standard", "")
        self.assertFalse(ok2)
        self.assertEqual(self.covers.error, "Cover page could not be created")

    def test_create_duplicate(self):
        self.assertTrue(self.covers.create("Cover 1", "test.ps"))
        ok = self.covers.create("Cover 2", "test.ps")
        self.assertFalse(ok)
        self.assertEqual(self.covers.error, "Cover page already exists")

    def test_get_covers_ordered_by_file(self):
        self.covers.create("Zeta Cover", "z_cover.ps")
        self.covers.create("Alpha Cover", "a_cover.ps")
        self.covers.create("Beta Cover", "m_cover.ps")

        covers_list = self.covers.get_covers()
        self.assertEqual(covers_list, ["a_cover.ps", "m_cover.ps", "z_cover.ps"])

    def test_list_covers_ordered_by_title(self):
        self.covers.create("Zeta Cover", "z_cover.ps")
        self.covers.create("Alpha Cover", "a_cover.ps")
        self.covers.create("Beta Cover", "m_cover.ps")

        items = self.covers.list_all()
        titles = [item["title"] for item in items]
        self.assertEqual(titles, ["Alpha Cover", "Beta Cover", "Zeta Cover"])

        # Iterator / step emulation for list_covers(&$title, &$file)
        self.covers.reset_list()
        res1 = self.covers.list_covers_step()
        self.assertIsNotNone(res1)
        self.assertEqual(res1[0], "Alpha Cover")
        self.assertEqual(res1[1], "a_cover.ps")

        res2 = self.covers.list_covers_step()
        self.assertIsNotNone(res2)
        self.assertEqual(res2[0], "Beta Cover")
        self.assertEqual(res2[1], "m_cover.ps")

        res3 = self.covers.list_covers_step()
        self.assertIsNotNone(res3)
        self.assertEqual(res3[0], "Zeta Cover")
        self.assertEqual(res3[1], "z_cover.ps")

        res4 = self.covers.list_covers_step()
        self.assertIsNone(res4)
        self.assertEqual(self.covers.error, "No cover pages configured")

    def test_load_cover(self):
        self.covers.create("Standard Cover", "standard.ps")

        loader = Covers(db=self.engine)
        ok = loader.load_cover("standard.ps")
        self.assertTrue(ok)
        self.assertEqual(loader.get_title(), "Standard Cover")
        self.assertEqual(loader.get_file(), "standard.ps")
        self.assertIsNotNone(loader.get_cover_id())

        fail_ok = loader.load_cover("nonexistent.ps")
        self.assertFalse(fail_ok)
        self.assertIn("nonexistent.ps", loader.error)

    def test_load_by_id(self):
        self.covers.create("ID Test", "id_test.ps")
        cid = self.covers.get_cover_id()

        loader = Covers(db=self.engine)
        self.assertTrue(loader.load_by_id(cid))
        self.assertEqual(loader.get_title(), "ID Test")

        self.assertFalse(loader.load_by_id(999999))

    def test_update_title_and_file(self):
        self.covers.create("Old Title", "old.ps")
        cover_id = self.covers.get_cover_id()

        ok_title = self.covers.set_title("New Title")
        self.assertTrue(ok_title)
        self.assertEqual(self.covers.get_title(), "New Title")

        ok_file = self.covers.set_file("new.ps")
        self.assertTrue(ok_file)
        self.assertEqual(self.covers.get_file(), "new.ps")

        reloader = Covers(db=self.engine)
        self.assertTrue(reloader.load_cover("new.ps"))
        self.assertEqual(reloader.get_cover_id(), cover_id)
        self.assertEqual(reloader.get_title(), "New Title")

    def test_update_without_load(self):
        unloaded = Covers(db=self.engine)
        self.assertFalse(unloaded.set_title("Title"))
        self.assertEqual(unloaded.error, "No cover page loaded")

        self.assertFalse(unloaded.set_file("File.ps"))
        self.assertEqual(unloaded.error, "No cover page loaded")

    def test_delete_cover(self):
        self.covers.create("To Delete", "delete.ps")
        cid = self.covers.get_cover_id()

        del_ok = self.covers.delete_cover(cid)
        self.assertTrue(del_ok)

        reloader = Covers(db=self.engine)
        self.assertFalse(reloader.load_cover("delete.ps"))


if __name__ == "__main__":
    unittest.main()
