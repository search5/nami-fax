import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from sqlsession import empty_session, seeded_session
from namifax.services.did import DIDRouting, DIDRoutingService


class TestDIDRouting(unittest.TestCase):
    def setUp(self):
        self.engine = empty_session()

        self.service = DIDRouting(db=self.engine)

    def tearDown(self):
        self.engine.disconnect()

    def test_empty_routes(self):
        routes = self.service.get_routes()
        self.assertIsNone(routes)
        self.assertEqual(self.service.get_error(), "No DID routes configured")

    def test_create_valid(self):
        ok = self.service.create(
            route="8001",
            alias="Support Line",
            contact="support@example.com",
            printer="PRN_SUPPORT",
            faxcatid=3,
        )
        self.assertTrue(ok)
        self.assertIsNotNone(self.service.get_didr_id())
        self.assertEqual(self.service.get_route(), "8001")
        self.assertEqual(self.service.get_alias(), "Support Line")
        self.assertEqual(self.service.get_contact(), "support@example.com")
        self.assertEqual(self.service.get_printer(), "PRN_SUPPORT")
        self.assertEqual(self.service.get_faxcatid(), 3)

    def test_create_invalid_email(self):
        ok = self.service.create("8002", "Invalid", contact="bad-email")
        self.assertFalse(ok)
        self.assertEqual(self.service.get_error(), "Please enter a valid e-mail address.")

    def test_create_invalid_args(self):
        self.assertFalse(self.service.create("", "Alias"))
        self.assertEqual(self.service.get_error(), "Route could not be created")

        self.assertFalse(self.service.create("<NONE>", "Alias"))
        self.assertEqual(self.service.get_error(), "Route could not be created")

        self.assertFalse(self.service.create("8003", ""))
        self.assertEqual(self.service.get_error(), "Route could not be created")

    def test_create_duplicate(self):
        self.assertTrue(self.service.create("8004", "Original"))
        ok = self.service.create("8004", "Duplicate")
        self.assertFalse(ok)
        self.assertEqual(self.service.get_error(), "DID route already exists")

    def test_get_routes_and_list_step(self):
        self.service.create("8002", "B Line")
        self.service.create("8001", "A Line")

        routes = self.service.get_routes()
        self.assertIsNotNone(routes)
        self.assertEqual(routes[0], 0)
        self.assertEqual(len(routes), 3)

        self.service.reset_list()
        step1 = self.service.list_routes_step()
        self.assertIsNotNone(step1)
        self.assertEqual(step1[1], "A Line")
        self.assertEqual(step1[2], "8001")

        step2 = self.service.list_routes_step()
        self.assertIsNotNone(step2)
        self.assertEqual(step2[1], "B Line")
        self.assertEqual(step2[2], "8002")

        step3 = self.service.list_routes_step()
        self.assertIsNone(step3)

    def test_load_route_and_loadbyid(self):
        self.service.create("8005", "Load Test", contact="load@example.com")
        rid = self.service.get_didr_id()

        loader1 = DIDRouting(db=self.engine)
        self.assertTrue(loader1.load_route("8005"))
        self.assertEqual(loader1.get_alias(), "Load Test")
        self.assertEqual(loader1.get_didr_id(), rid)

        loader2 = DIDRouting(db=self.engine)
        self.assertTrue(loader2.loadbyid(rid))
        self.assertEqual(loader2.get_route(), "8005")

        self.assertFalse(loader1.load_route("NONEXISTENT"))
        self.assertFalse(loader2.loadbyid(99999))

    def test_setters(self):
        self.service.create("8006", "Old Alias")
        rid = self.service.get_didr_id()

        self.assertTrue(self.service.set_alias("New Alias"))
        self.assertTrue(self.service.set_routecode("8007"))
        self.assertTrue(self.service.set_contact("new@example.com"))
        self.assertTrue(self.service.set_printer("NEW_PRINTER"))
        self.assertTrue(self.service.set_faxcatid(4))

        # Check in DB
        reloader = DIDRouting(db=self.engine)
        self.assertTrue(reloader.loadbyid(rid))
        self.assertEqual(reloader.get_alias(), "New Alias")
        self.assertEqual(reloader.get_route(), "8007")
        self.assertEqual(reloader.get_contact(), "new@example.com")
        self.assertEqual(reloader.get_printer(), "NEW_PRINTER")
        self.assertEqual(reloader.get_faxcatid(), 4)

    def test_setters_without_load(self):
        unloaded = DIDRouting(db=self.engine)
        self.assertFalse(unloaded.set_alias("Alias"))
        self.assertEqual(unloaded.get_error(), "No entry loaded")
        self.assertFalse(unloaded.set_routecode("8000"))
        self.assertFalse(unloaded.set_contact("test@test.com"))
        self.assertFalse(unloaded.set_printer("PRN"))
        self.assertFalse(unloaded.set_faxcatid(1))

    def test_delete_route(self):
        self.service.create("8008", "To Delete")
        rid = self.service.get_didr_id()

        ok = self.service.delete_route(rid)
        self.assertTrue(ok)

        reloader = DIDRouting(db=self.engine)
        self.assertFalse(reloader.loadbyid(rid))


if __name__ == "__main__":
    unittest.main()
