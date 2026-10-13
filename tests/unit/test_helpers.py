import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from namifax.common.helpers import (
    clean_faxnum,
    fupload_error_code,
    get_company_details,
    invalid_email,
    mime_by_suffix,
    phone_lookup,
    process_template,
    rem_nl,
    split_emails,
    strip_sipinfo,
    unaccent,
)
from sqlsession import empty_session, seeded_session
from namifax.services.addressbook import NFAddressBook


class TestCommonHelpers(unittest.TestCase):
    def setUp(self):
        self.engine = empty_session()
        self.abook = NFAddressBook(db=self.engine)

    def tearDown(self):
        self.engine.disconnect()

    def test_string_utilities(self):
        self.assertEqual(clean_faxnum("+1 (800) 555-0199"), "+18005550199")
        self.assertEqual(rem_nl("Line 1\r\nLine 2\nLine 3"), "Line 1Line 2Line 3")
        self.assertEqual(unaccent("Hélène déjà vu"), "Helene deja vu")
        self.assertEqual(strip_sipinfo("sip:alice@sip.provider.net"), "sip:alice")

    def test_email_helpers(self):
        self.assertFalse(invalid_email("user@example.com"))
        self.assertTrue(invalid_email("not-an-email"))

        emails = split_emails("a@a.com, b@b.com; c@c.com   d@d.com")
        self.assertEqual(emails, ["a@a.com", "b@b.com", "c@c.com", "d@d.com"])

    def test_process_template(self):
        tpl = "Hello %s, your code is %s."
        res = process_template(tpl, "%s", ["Alice", "9988"])
        self.assertEqual(res, "Hello Alice, your code is 9988.")

    def test_mime_and_filetype(self):
        self.assertEqual(mime_by_suffix("document.pdf"), "application/pdf")
        self.assertEqual(mime_by_suffix("image.tif"), "image/tiff")
        self.assertEqual(mime_by_suffix("image.tiff"), "image/tiff")
        self.assertEqual(mime_by_suffix("photo.png"), "image/png")
        self.assertEqual(mime_by_suffix("unknown.xyz"), "application/octet-stream")

        self.assertIn("exceeds", fupload_error_code(1))
        self.assertIn("No file", fupload_error_code(4))

    def test_phone_lookup_and_company_details(self):
        self.abook.create("MegaCorp")
        cid = self.abook.abook_id
        self.abook.create_faxnumid("18005550199")

        # Test phone_lookup
        found = phone_lookup("18005550199", db=self.engine)
        self.assertIsNotNone(found)
        self.assertEqual(found["company"], "MegaCorp")

        # Test get_company_details
        details = get_company_details(abookfax_id=None, orig_faxnum="18005550199", companyid=cid, db=self.engine)
        self.assertEqual(details["company"], "MegaCorp")


if __name__ == "__main__":
    unittest.main()
