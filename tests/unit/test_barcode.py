import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from sqlsession import empty_session, seeded_session
from namifax.services.barcode import BarcodeRouting, BarcodeRoutingService


class TestBarcodeRouting(unittest.TestCase):
    def setUp(self):
        self.engine = empty_session()

        self.service = BarcodeRouting(db=self.engine)

    def tearDown(self):
        self.engine.disconnect()

    def test_empty_routes(self):
        routes = self.service.get_routes()
        self.assertIsNone(routes)
        self.assertEqual(self.service.get_error(), "No barcode routes configured")

    def test_create_valid(self):
        ok = self.service.create(
            barcode="BC1001",
            alias="Sales Dept",
            contact="sales@example.com",
            printer="PRINTER1",
            faxcatid=2,
        )
        self.assertTrue(ok)
        self.assertIsNotNone(self.service.get_barcode_id())
        self.assertEqual(self.service.get_barcode(), "BC1001")
        self.assertEqual(self.service.get_alias(), "Sales Dept")
        self.assertEqual(self.service.get_contact(), "sales@example.com")
        self.assertEqual(self.service.get_printer(), "PRINTER1")
        self.assertEqual(self.service.get_faxcatid(), 2)

    def test_create_invalid_email(self):
        ok = self.service.create("BC1002", "Support", contact="invalid_email")
        self.assertFalse(ok)
        self.assertEqual(self.service.get_error(), "Please enter a valid e-mail address.")

    def test_create_invalid_args(self):
        # Empty barcode
        self.assertFalse(self.service.create("", "Alias"))
        self.assertEqual(self.service.get_error(), "Route could not be created")

        # <NONE> barcode
        self.assertFalse(self.service.create("<NONE>", "Alias"))
        self.assertEqual(self.service.get_error(), "Route could not be created")

        # Empty alias
        self.assertFalse(self.service.create("BC1003", ""))
        self.assertEqual(self.service.get_error(), "Route could not be created")

    def test_create_duplicate(self):
        self.assertTrue(self.service.create("BC_DUP", "Original"))
        ok = self.service.create("BC_DUP", "Duplicate")
        self.assertFalse(ok)
        self.assertEqual(self.service.get_error(), "Barcode route already exists")

    def test_get_routes_and_list_step(self):
        self.service.create("BC002", "B Team")
        self.service.create("BC001", "A Team")

        routes = self.service.get_routes()
        self.assertIsNotNone(routes)
        self.assertEqual(routes[0], 0)
        self.assertEqual(len(routes), 3)

        self.service.reset_list()
        step1 = self.service.list_routes_step()
        self.assertIsNotNone(step1)
        self.assertEqual(step1[1], "A Team")
        self.assertEqual(step1[2], "BC001")

        step2 = self.service.list_routes_step()
        self.assertIsNotNone(step2)
        self.assertEqual(step2[1], "B Team")
        self.assertEqual(step2[2], "BC002")

        step3 = self.service.list_routes_step()
        self.assertIsNone(step3)

    def test_load_route_and_loadbyid(self):
        self.service.create("BC_LOAD", "Load Alias", contact="load@example.com")
        rid = self.service.get_barcode_id()

        loader1 = BarcodeRouting(db=self.engine)
        self.assertTrue(loader1.load_route("BC_LOAD"))
        self.assertEqual(loader1.get_alias(), "Load Alias")
        self.assertEqual(loader1.get_barcode_id(), rid)

        loader2 = BarcodeRouting(db=self.engine)
        self.assertTrue(loader2.loadbyid(rid))
        self.assertEqual(loader2.get_barcode(), "BC_LOAD")

        self.assertFalse(loader1.load_route("NONEXISTENT"))
        self.assertFalse(loader2.loadbyid(99999))

    def test_setters(self):
        self.service.create("BC_OLD", "Old Alias")
        rid = self.service.get_barcode_id()

        self.assertTrue(self.service.set_alias("New Alias"))
        self.assertTrue(self.service.set_barcode("BC_NEW"))
        self.assertTrue(self.service.set_contact("new@example.com"))
        self.assertTrue(self.service.set_printer("NEW_PRN"))
        self.assertTrue(self.service.set_faxcatid(5))

        # Check in DB
        reloader = BarcodeRouting(db=self.engine)
        self.assertTrue(reloader.loadbyid(rid))
        self.assertEqual(reloader.get_alias(), "New Alias")
        self.assertEqual(reloader.get_barcode(), "BC_NEW")
        self.assertEqual(reloader.get_contact(), "new@example.com")
        self.assertEqual(reloader.get_printer(), "NEW_PRN")
        self.assertEqual(reloader.get_faxcatid(), 5)

    def test_setters_without_load(self):
        unloaded = BarcodeRouting(db=self.engine)
        self.assertFalse(unloaded.set_alias("Alias"))
        self.assertEqual(unloaded.get_error(), "No entry loaded")
        self.assertFalse(unloaded.set_barcode("BC"))
        self.assertFalse(unloaded.set_contact("test@test.com"))
        self.assertFalse(unloaded.set_printer("PRN"))
        self.assertFalse(unloaded.set_faxcatid(1))

    def test_delete_route(self):
        self.service.create("BC_DEL", "To Delete")
        rid = self.service.get_barcode_id()

        ok = self.service.delete_route(rid)
        self.assertTrue(ok)

        reloader = BarcodeRouting(db=self.engine)
        self.assertFalse(reloader.loadbyid(rid))


if __name__ == "__main__":
    unittest.main()
