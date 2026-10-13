import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from sqlsession import empty_session, seeded_session
from namifax.services.addressbook import NFAddressBook, AddressBookService, clean_faxnum


class TestAFAddressBook(unittest.TestCase):
    def setUp(self):
        self.engine = empty_session()

        # Create AddressBook, AddressBookFAX, AddressBookEmail tables
        self.service = NFAddressBook(db=self.engine)

    def tearDown(self):
        self.engine.disconnect()

    def test_clean_faxnum(self):
        self.assertEqual(clean_faxnum("+1 (555) 123-4567"), "+15551234567")
        self.assertEqual(clean_faxnum("02-1234-5678"), "0212345678")

    def test_company_lifecycle(self):
        # Create
        self.assertTrue(self.service.create("Acme Corp"))
        cid = self.service.get_companyid()
        self.assertIsNotNone(cid)
        self.assertEqual(self.service.get_company(), "Acme Corp")

        # Duplicate
        self.assertFalse(self.service.create("Acme Corp"))
        self.assertEqual(self.service.get_error(), "Company already exists")

        # Load
        loader = NFAddressBook(db=self.engine)
        self.assertTrue(loader.loadbycid(cid))
        self.assertEqual(loader.get_company(), "Acme Corp")

        # Set company
        self.assertTrue(loader.set_company("Acme Global"))
        self.assertEqual(loader.get_company(), "Acme Global")

        # Search
        res = self.service.search_companies("Global")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["company"], "Acme Global")

        # Delete
        self.assertTrue(self.service.delete_cid(cid))
        self.assertFalse(loader.loadbycid(cid))

    def test_fax_lifecycle(self):
        self.service.create("Beta Industries")
        cid = self.service.get_companyid()

        # Add fax number
        self.assertTrue(self.service.create_faxnumid("+1-555-0199"))
        fax_id = self.service.get_faxnumid()
        self.assertIsNotNone(fax_id)
        self.assertEqual(self.service.get_faxnumber(), "+15550199")

        # Save settings
        self.assertTrue(
            self.service.save_settings(
                {
                    "description": "HQ Fax",
                    "email": "fax@beta.com",
                    "to_person": "Jane Doe",
                    "printer": "PRN1",
                    "faxcatid": 2,
                }
            )
        )
        self.assertEqual(self.service.get_description(), "HQ Fax")
        self.assertEqual(self.service.get_email(), "fax@beta.com")
        self.assertEqual(self.service.get_to_person(), "Jane Doe")
        self.assertTrue(self.service.has_fax2email())

        # Counters
        self.assertTrue(self.service.inc_faxfrom())
        self.assertEqual(self.service.get_faxfrom(), 1)
        self.assertTrue(self.service.inc_faxto())
        self.assertEqual(self.service.get_faxto(), 1)

        # Lookup by fax number
        finder = NFAddressBook(db=self.engine)
        ok, mult = finder.loadbyfaxnum("+1 555 0199")
        self.assertTrue(ok)
        self.assertFalse(mult)
        self.assertEqual(finder.get_company(), "Beta Industries")

        # Reassign to new company
        other = NFAddressBook(db=self.engine)
        other.create("Gamma LLC")
        new_cid = other.get_companyid()

        self.assertTrue(finder.reassign(new_cid))
        # Old company deleted, fax reassigned to Gamma LLC
        self.assertFalse(self.service.loadbycid(cid))

        rechecked = NFAddressBook(db=self.engine)
        ok, _ = rechecked.loadbyfaxnum("+15550199")
        self.assertTrue(ok)
        self.assertEqual(rechecked.get_company(), "Gamma LLC")

    def test_contacts_lifecycle(self):
        # Create single contact
        ok = self.service.create_contact("Alice Smith", "alice@example.com")
        self.assertTrue(ok)

        # Duplicate email
        self.assertFalse(self.service.create_contact("Alice 2", "alice@example.com"))

        # Batch creation string
        self.service.create_contacts("Bob Jones <bob@example.com>; Charlie <charlie@example.com>")

        contacts_map = self.service.get_contacts()
        self.assertIsNotNone(contacts_map)
        self.assertEqual(len(contacts_map), 3)

        # Load and update
        cid = list(contacts_map.keys())[0]
        loader = NFAddressBook(db=self.engine)
        self.assertTrue(loader.load_contact_by_id(cid))
        self.assertTrue(loader.update_contact("Alice Updated", "alice_new@example.com"))
        self.assertEqual(loader.get_contact_name(), "Alice Updated")

        # Remove contact
        self.assertTrue(self.service.remove_contact(cid))
        self.assertFalse(loader.load_contact_by_id(cid))


if __name__ == "__main__":
    unittest.main()
