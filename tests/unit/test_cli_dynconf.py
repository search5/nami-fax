import io
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from namifax.cli.dynconf import run_dynconf, strip_sipinfo
from sqlsession import empty_session, seeded_session
from namifax.services.dynconf import DynamicConfig


class TestCliDynconf(unittest.TestCase):
    def setUp(self):
        self.engine = empty_session()
        self.dc = DynamicConfig(db=self.engine)

    def tearDown(self):
        self.engine.disconnect()

    def test_strip_sipinfo(self):
        self.assertEqual(strip_sipinfo("sip:12345@domain.com"), "sip:12345")
        self.assertEqual(strip_sipinfo("01012345678"), "01012345678")
        self.assertEqual(strip_sipinfo("user@sip.server.net"), "user")

    def test_usage_no_args(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = run_dynconf(["dynconf.py"], dc=self.dc)
        self.assertEqual(code, 0)
        self.assertEqual(buf.getvalue().strip(), "dynconf.php device CallID1 CallIDn...")

    def test_empty_callid(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = run_dynconf(["dynconf.py", "ttyS0", ""], dc=self.dc)
        self.assertEqual(code, 0)
        self.assertEqual(buf.getvalue(), "")

    def test_reject_call(self):
        # Register spam number
        self.dc.create(device="ttyS0", callid="0211112222")

        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = run_dynconf(["dynconf.py", "ttyS0", "0211112222"], dc=self.dc)
        self.assertEqual(code, 0)
        self.assertEqual(buf.getvalue().strip(), "RejectCall: true")

    def test_allow_call(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = run_dynconf(["dynconf.py", "ttyS0", "01099998888"], dc=self.dc)
        self.assertEqual(code, 0)
        self.assertEqual(buf.getvalue(), "")

    def test_sip_rejection(self):
        self.dc.create(device="", callid="spammer")
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = run_dynconf(["dynconf.py", "ttyS0", "spammer@voip.provider.com"], dc=self.dc)
        self.assertEqual(code, 0)
        self.assertEqual(buf.getvalue().strip(), "RejectCall: true")


if __name__ == "__main__":
    unittest.main()
