import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from sqlsession import empty_session, seeded_session
from namifax.services.modem import FaxModem, FaxModemService, parse_faxstat_output


class TestFaxModem(unittest.TestCase):
    def setUp(self):
        self.engine = empty_session()

        self.service = FaxModem(db=self.engine)

    def tearDown(self):
        self.engine.disconnect()

    def test_empty_modems(self):
        modems = self.service.get_modems()
        self.assertIsNone(modems)
        self.assertEqual(self.service.get_error(), "No modems configured")

    def test_create_valid(self):
        ok = self.service.create(
            device="ttyS0",
            alias="Primary Line",
            contact="ops@example.com",
            printer="MAIN_PRN",
            faxcatid=1,
        )
        self.assertTrue(ok)
        self.assertIsNotNone(self.service.get_devid())
        self.assertEqual(self.service.get_device(), "ttyS0")
        self.assertEqual(self.service.get_alias(), "Primary Line")
        self.assertEqual(self.service.get_contact(), "ops@example.com")
        self.assertEqual(self.service.get_printer(), "MAIN_PRN")
        self.assertEqual(self.service.get_faxcatid(), 1)

    def test_create_invalid_args(self):
        self.assertFalse(self.service.create("", "Alias"))
        self.assertEqual(self.service.get_error(), "Modem could not be created")

        self.assertFalse(self.service.create("ttyS0", ""))
        self.assertEqual(self.service.get_error(), "Modem could not be created")

    def test_create_duplicate(self):
        self.assertTrue(self.service.create("ttyS0", "Line 1"))
        ok = self.service.create("ttyS0", "Line 1 Dup")
        self.assertFalse(ok)
        self.assertEqual(self.service.get_error(), "Modem already exists")

    def test_get_modems_and_list_step(self):
        self.service.create("ttyS1", "B Line")
        self.service.create("ttyS0", "A Line")

        # get_modems orders by alias: "A Line" (ttyS0) then "B Line" (ttyS1)
        modems = self.service.get_modems()
        self.assertEqual(modems, ["ttyS0", "ttyS1"])

        # list_modems_step orders by device: "ttyS0" then "ttyS1"
        self.service.reset_list()
        step1 = self.service.list_modems_step()
        self.assertIsNotNone(step1)
        self.assertEqual(step1[2], "ttyS0")

        step2 = self.service.list_modems_step()
        self.assertIsNotNone(step2)
        self.assertEqual(step2[2], "ttyS1")

        step3 = self.service.list_modems_step()
        self.assertIsNone(step3)

    def test_load_device_and_loadbyid(self):
        self.service.create("ttyS0", "Main", contact="main@example.com")
        devid = self.service.get_devid()

        loader1 = FaxModem(db=self.engine)
        self.assertTrue(loader1.load_device("ttyS0"))
        self.assertEqual(loader1.get_alias(), "Main")
        self.assertEqual(loader1.get_devid(), devid)

        loader2 = FaxModem(db=self.engine)
        self.assertTrue(loader2.loadbyid(devid))
        self.assertEqual(loader2.get_device(), "ttyS0")

        self.assertFalse(loader1.load_device("nonexistent"))
        self.assertFalse(loader2.loadbyid(99999))

    def test_setters(self):
        self.service.create("ttyS0", "Old Alias")
        devid = self.service.get_devid()

        self.assertTrue(self.service.set_alias("New Alias"))
        self.assertTrue(self.service.set_contact("new@example.com"))
        self.assertTrue(self.service.set_printer("NEW_PRN"))
        self.assertTrue(self.service.set_faxcatid(7))

        reloader = FaxModem(db=self.engine)
        self.assertTrue(reloader.loadbyid(devid))
        self.assertEqual(reloader.get_alias(), "New Alias")
        self.assertEqual(reloader.get_contact(), "new@example.com")
        self.assertEqual(reloader.get_printer(), "NEW_PRN")
        self.assertEqual(reloader.get_faxcatid(), 7)

    def test_setters_without_load(self):
        unloaded = FaxModem(db=self.engine)
        self.assertFalse(unloaded.set_alias("Alias"))
        self.assertEqual(unloaded.get_error(), "No modem loaded")
        self.assertFalse(unloaded.set_contact("test@test.com"))
        self.assertFalse(unloaded.set_printer("PRN"))
        self.assertFalse(unloaded.set_faxcatid(1))

    def test_faxstat_status_parsing(self):
        sample_output = """
HylaFAX scheduler on avantfax.local: Running
Modem ttyS0 (+1.234.567.8900): Running and idle
Modem ttyS1 (+1.234.567.8901): Sending job 1234
Modem ttyS2 (+1.234.567.8902): Receiving from "0123456789"
"""
        status_map = parse_faxstat_output(sample_output)
        self.assertIn("ttyS0", status_map)
        self.assertEqual(status_map["ttyS0"]["class"], "modem-free")

        self.assertIn("ttyS1", status_map)
        self.assertEqual(status_map["ttyS1"]["class"], "modem-send")

        self.assertIn("ttyS2", status_map)
        self.assertEqual(status_map["ttyS2"]["class"], "modem-recv")

        # Test through service instance
        self.service.create("ttyS0", "Line 0")
        self.service.load_device("ttyS0")
        st = self.service.get_status(raw_output=sample_output)
        self.assertEqual(st["class"], "modem-free")

    def test_delete_device(self):
        self.service.create("ttyS0", "To Delete")
        devid = self.service.get_devid()

        ok = self.service.delete_device(devid)
        self.assertTrue(ok)

        reloader = FaxModem(db=self.engine)
        self.assertFalse(reloader.loadbyid(devid))


if __name__ == "__main__":
    unittest.main()
