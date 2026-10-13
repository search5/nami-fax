import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from sqlsession import empty_session, seeded_session
from namifax.services.categories import FaxPDFCategory, CategoryService


class TestFaxPDFCategory(unittest.TestCase):
    def setUp(self):
        self.engine = empty_session()

        self.service = FaxPDFCategory(db=self.engine)

    def tearDown(self):
        self.engine.disconnect()

    def test_empty_categories(self):
        cats = self.service.get_categories()
        self.assertTrue(cats is None or cats == [])

    def test_create_category(self):
        ok = self.service.create("Invoices")
        self.assertTrue(ok)
        self.assertIsNone(self.service.get_error())

    def test_create_duplicate(self):
        self.assertTrue(self.service.create("Contracts"))
        ok = self.service.create("Contracts")
        self.assertFalse(ok)
        self.assertIn("Contracts", self.service.get_error())

    def test_get_name(self):
        self.service.create("Support")
        cats = self.service.get_categories()
        self.assertIsNotNone(cats)
        catid = cats[0]["catid"]

        name = self.service.get_name(catid)
        self.assertEqual(name, "Support")

        # Invalid or missing catid
        self.assertIsNone(self.service.get_name(None))
        self.assertEqual(self.service.get_error(), "No catid sent")

        self.assertIsNone(self.service.get_name(9999))

    def test_set_name(self):
        self.service.create("OldName")
        cats = self.service.get_categories()
        catid = cats[0]["catid"]

        ok = self.service.set_name("NewName", catid)
        self.assertTrue(ok)
        self.assertEqual(self.service.get_name(catid), "NewName")

        # Missing params
        self.assertFalse(self.service.set_name("", catid))
        self.assertEqual(self.service.get_error(), "No name or catid to set")
        self.assertFalse(self.service.set_name("Name", None))

    def test_get_categories_ordered(self):
        self.service.create("Zebra")
        self.service.create("Apple")
        self.service.create("Mango")

        cats = self.service.get_categories()
        names = [c["name"] for c in cats]
        self.assertEqual(names, ["Apple", "Mango", "Zebra"])

    def test_get_list_step(self):
        self.service.create("Zebra")
        self.service.create("Apple")

        self.service.reset_list()
        step1 = self.service.get_list_step()
        self.assertIsNotNone(step1)
        self.assertEqual(step1[1], "Apple")

        step2 = self.service.get_list_step()
        self.assertIsNotNone(step2)
        self.assertEqual(step2[1], "Zebra")

        step3 = self.service.get_list_step()
        self.assertIsNone(step3)

    def test_delete_category(self):
        self.service.create("Temporary")
        cats = self.service.get_categories()
        catid = cats[0]["catid"]

        ok = self.service.delete_category(catid)
        self.assertTrue(ok)
        self.assertIsNone(self.service.get_name(catid))

        # Missing catid
        self.assertFalse(self.service.delete_category(None))
        self.assertEqual(self.service.get_error(), "No catid sent")


if __name__ == "__main__":
    unittest.main()
