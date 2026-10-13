import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from namifax.cli.phb import generate_phonebook_content, run_phb
from sqlsession import empty_session, seeded_session
from namifax.services.addressbook import NFAddressBook


class TestCliPhb(unittest.TestCase):
    def setUp(self):
        self.engine = empty_session()
        self.abook = NFAddressBook(db=self.engine)

    def tearDown(self):
        self.engine.disconnect()

    def test_generate_phonebook_empty(self):
        content = generate_phonebook_content(self.abook)
        self.assertEqual(content, "PBOOK1.1")

    def test_generate_phonebook_entries(self):
        # Add Company 1
        self.abook.create("Acme Corp")
        self.abook.create_faxnumid("111-222-3333")
        self.abook.create_faxnumid("444-555-6666")

        # Add Company 2
        self.abook.create("Globex")
        self.abook.create_faxnumid("777-888-9999")

        content = generate_phonebook_content(self.abook)
        expected = "PBOOK1.1Acme Corp|1112223333;4445556666|||||||Globex|7778889999|||||||"
        self.assertEqual(content, expected)

    def test_run_phb_file_writing(self):
        self.abook.create("Omega")
        self.abook.create_faxnumid("12345")

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            code = run_phb(["phb.py", "-o", tmp_path], addressbook=self.abook)
            self.assertEqual(code, 0)

            with open(tmp_path, "r", encoding="utf-8") as f:
                saved = f.read()
            self.assertEqual(saved, "PBOOK1.1Omega|12345|||||||")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
