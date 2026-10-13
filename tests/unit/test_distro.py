import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from sqlsession import empty_session, seeded_session
from namifax.services.distro import DistributionList, DistributionListService


class TestDistributionList(unittest.TestCase):
    def setUp(self):
        self.engine = empty_session()

        self.service = DistributionList(db=self.engine)

    def tearDown(self):
        self.engine.disconnect()

    def test_empty_lists(self):
        lists = self.service.get_distrolists()
        self.assertEqual(lists, [])

    def test_create_valid(self):
        self.service.set_moduser(42)
        ok = self.service.create("VIP Clients")
        self.assertTrue(ok)
        self.assertIsNotNone(self.service.get_dl_id())
        self.assertEqual(self.service.get_listname(), "VIP Clients")

    def test_create_invalid_args(self):
        ok = self.service.create("")
        self.assertFalse(ok)
        self.assertEqual(self.service.get_error(), "Please enter a list name")

    def test_create_duplicate(self):
        self.assertTrue(self.service.create("Employees"))
        ok = self.service.create("Employees")
        self.assertFalse(ok)
        self.assertEqual(self.service.get_error(), "A distribution list by that name already exists")

    def test_get_distrolists_ordered(self):
        self.service.create("Zebra Group")
        self.service.create("Alpha Group")
        self.service.create("Beta Group")

        res = self.service.get_distrolists()
        names = [r["listname"] for r in res]
        self.assertEqual(names, ["Alpha Group", "Beta Group", "Zebra Group"])

    def test_load_and_modify_listname(self):
        self.service.create("Old Group")
        lid = self.service.get_dl_id()

        loader = DistributionList(db=self.engine)
        self.assertTrue(loader.load_list(lid))
        self.assertEqual(loader.get_listname(), "Old Group")

        ok = loader.set_listname("New Group")
        self.assertTrue(ok)

        # Check DB
        reloader = DistributionList(db=self.engine)
        self.assertTrue(reloader.load_list(lid))
        self.assertEqual(reloader.get_listname(), "New Group")

    def test_entries_add_and_remove(self):
        self.service.create("Branch Offices")
        lid = self.service.get_dl_id()

        loader = DistributionList(db=self.engine)
        self.assertTrue(loader.load_list(lid))

        # Initially empty entries
        self.assertEqual(loader.list_entries(), [])

        # Add entries
        ok = loader.add_entries(["0212345678", "0298765432"])
        self.assertTrue(ok)
        self.assertEqual(loader.list_entries(), ["0212345678", "0298765432"])

        # Add more with overlap (no duplicates)
        loader.add_entries(["0212345678", "0311112222"])
        self.assertEqual(loader.list_entries(), ["0212345678", "0298765432", "0311112222"])

        # Remove entry
        ok_rm = loader.remove_entries(["0298765432"])
        self.assertTrue(ok_rm)
        self.assertEqual(loader.list_entries(), ["0212345678", "0311112222"])

        # Verify persisted in DB
        reloader = DistributionList(db=self.engine)
        self.assertTrue(reloader.load_list(lid))
        self.assertEqual(reloader.list_entries(), ["0212345678", "0311112222"])

    def test_operations_without_load(self):
        unloaded = DistributionList(db=self.engine)
        self.assertFalse(unloaded.set_listname("Name"))
        self.assertEqual(unloaded.get_error(), "No list loaded")
        self.assertEqual(unloaded.list_entries(), [])
        self.assertFalse(unloaded.add_entries(["123"]))
        self.assertFalse(unloaded.remove_entries(["123"]))

    def test_delete_list(self):
        self.service.create("Temporary List")
        lid = self.service.get_dl_id()

        ok = self.service.delete_list(lid)
        self.assertTrue(ok)

        reloader = DistributionList(db=self.engine)
        self.assertFalse(reloader.load_list(lid))


if __name__ == "__main__":
    unittest.main()
