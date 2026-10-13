import os
import socket
import unittest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

import namifax.models  # noqa: F401  (registers every model)
from namifax.db.provider import create_sa_engine
from namifax.models.meta import Base
from namifax.services.printer import (
    NetworkPrinter,
    NetworkPrinterService,
    extract_fax_tags,
    process_inbound_print_job,
)


class TestNetworkPrinter(unittest.TestCase):
    def setUp(self):
        self.engine = create_sa_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.service = NetworkPrinterService(self.session)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def test_printer_crud(self):
        pid = self.service.create_printer(
            name="Office HP LaserJet",
            protocol="RAW",
            host="192.168.1.100",
            port=9100,
            description="2nd floor printer",
        )
        self.assertIsNotNone(pid)

        printers = self.service.list_printers()
        self.assertEqual(len(printers), 1)
        self.assertEqual(printers[0].name, "Office HP LaserJet")
        self.assertEqual(printers[0].host, "192.168.1.100")
        self.assertEqual(printers[0].port, 9100)

        # Delete
        ok = self.service.delete_printer(pid)
        self.assertTrue(ok)
        self.assertEqual(len(self.service.list_printers()), 0)

    @patch("socket.create_connection")
    def test_print_raw_socket_success(self, mock_create_connection):
        mock_sock = MagicMock()
        mock_create_connection.return_value.__enter__.return_value = mock_sock

        data = b"%PDF-1.4 sample stream\n"
        res = self.service.send_raw_print("192.168.1.100", 9100, data)
        self.assertTrue(res["success"])
        mock_sock.sendall.assert_called_once_with(data)

    @patch("socket.create_connection")
    def test_test_print_page(self, mock_create_connection):
        mock_sock = MagicMock()
        mock_create_connection.return_value.__enter__.return_value = mock_sock

        res = self.service.test_print("192.168.1.100", 9100, "RAW")
        self.assertTrue(res["success"])
        self.assertIn("Test print page dispatched", res["message"])

    def test_extract_fax_tags(self):
        doc_text = (
            "Invoice #12345\n"
            "Recipient Info:\n"
            "[[FAX: 02-1234-5678]]\n"
            "Please expedite delivery."
        )
        numbers = extract_fax_tags(doc_text)
        self.assertEqual(numbers, ["02-1234-5678"])

        # Multiple tags
        multi_text = "[[FAX: +1-800-555-0199]] and [[FAX:031-987-6543]]"
        numbers2 = extract_fax_tags(multi_text)
        self.assertEqual(numbers2, ["+1-800-555-0199", "031-987-6543"])

        # No tags
        no_tag_text = "Standard text with no fax number."
        self.assertEqual(extract_fax_tags(no_tag_text), [])

    @patch("src.namifax.services.printer.extract_fax_tags")
    def test_process_inbound_print_job_with_tag(self, mock_extract):
        mock_extract.return_value = ["02-555-1234"]
        job_result = process_inbound_print_job(
            print_data=b"Document with [[FAX: 02-555-1234]]",
            sender_user="erp_system",
            db=self.session,
            dispatcher=lambda send, sender: {"success": True, "jobid": "77"},
        )
        self.assertTrue(job_result["dispatched"])
        self.assertEqual(job_result["destination"], "02-555-1234")
        self.assertEqual(job_result["job_id"], "77")

    def test_the_print_job_is_really_handed_to_sendfax_and_the_spool_file_goes(self):
        seen = {}

        def dispatcher(send, sender):
            seen["send"], seen["sender"] = send, sender
            seen["exists"] = os.path.exists(send.files[0])
            return {"success": True, "jobid": "12"}

        out = process_inbound_print_job(b"%PDF-1.4 [[FAX: 031-111-2222]]", sender_user="erp", db=self.session, dispatcher=dispatcher)
        self.assertEqual(seen["send"].destinations, "031-111-2222")
        self.assertEqual(seen["sender"].username, "erp")
        self.assertTrue(seen["exists"] and seen["send"].files[0].endswith(".pdf"))
        self.assertTrue(out["dispatched"] and out["status"] == "QUEUED")
        self.assertFalse(os.path.exists(out["file_path"]))                     # sent: nothing left in the spool

    def test_a_failed_dispatch_is_not_reported_as_queued(self):
        out = process_inbound_print_job(b"x [[FAX: 02-1]]", sender_user="erp", db=self.session,
                                        dispatcher=lambda send, sender: {"success": False, "error": "sendfax is not installed"})
        self.assertFalse(out["dispatched"])
        self.assertEqual(out["status"], "FAILED")
        self.assertIn("sendfax is not installed", out["message"])
        self.assertTrue(os.path.exists(out["file_path"]))                      # kept, so that it can be sent again

    def test_a_dispatcher_that_raises_is_a_failure_too(self):
        def boom(send, sender):
            raise OSError("no sendfax")

        out = process_inbound_print_job(b"x [[FAX: 02-1]]", sender_user="erp", db=self.session, dispatcher=boom)
        self.assertFalse(out["dispatched"]) and self.assertEqual(out["status"], "FAILED")

    @patch("src.namifax.services.printer.extract_fax_tags")
    def test_process_inbound_print_job_without_tag(self, mock_extract):
        mock_extract.return_value = []
        job_result = process_inbound_print_job(
            print_data=b"Document without any fax tag",
            sender_user="office_pc",
            db=self.session,
        )
        self.assertFalse(job_result["dispatched"])
        self.assertEqual(job_result["status"], "DRAFT")


if __name__ == "__main__":
    unittest.main()
