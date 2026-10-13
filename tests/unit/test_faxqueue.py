import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from namifax.services.faxqueue import FaxQueue, parse_queue_output, SENDQ_KEYS, DONEQ_KEYS

MOCK_SENDQ = """HylaFAX scheduler on myhost: Running
Modem ttyS0 (123-4567): Running and idle
Modem ttyS1 (123-4568): Running and idle

JID  Pri S  Owner MailAddr     Number Pages Dials     TTS Status
101  127 R  admin admin@me.com 123456   1:1   0:12  00:00 Sending job
102  127 W  bob   bob@me.com   987654   0:2   0:12  12:00 Waiting for modem
"""

MOCK_DONEQ = """HylaFAX scheduler on myhost: Running
Modem ttyS0 (123-4567): Running and idle

JID  Pri S  Owner MailAddr     Number Pages Dials Status
103  127 D  alice alice@me.com 111222   1:1   1:12 Done
104  127 F  bob   bob@me.com   333444   0:1   3:12 Busy signal detected
"""


class TestFaxQueue(unittest.TestCase):
    def test_parse_queue_output(self):
        items = parse_queue_output(MOCK_SENDQ.splitlines(), SENDQ_KEYS)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["jid"], "101")
        self.assertEqual(items[0]["s"], "R")
        self.assertEqual(items[0]["owner"], "admin")
        self.assertEqual(items[0]["mailaddr"], "admin@me.com")
        self.assertEqual(items[0]["number"], "123456")
        self.assertEqual(items[0]["pages"], "1:1")
        self.assertEqual(items[0]["status"], "Sending job")

        self.assertEqual(items[1]["jid"], "102")
        self.assertEqual(items[1]["status"], "Waiting for modem")

    def test_process_failed_queue(self):
        fq = FaxQueue(auto_process=False)
        failed = fq.process_failed_queue(raw_output=MOCK_DONEQ)
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["jid"], "104")
        self.assertEqual(failed[0]["s"], "F")
        self.assertEqual(failed[0]["status"], "Busy signal detected")

    def test_get_queue_and_list_owner(self):
        mock_user_svc = MagicMock()
        mock_user = MagicMock()
        mock_user.name = "Robert Smith"
        mock_user.username = "bob"

        def mock_load_username(u):
            return u == "bob"

        mock_user_svc.load_username.side_effect = mock_load_username
        mock_user_svc.name = "Robert Smith"

        fq = FaxQueue(user_account=mock_user_svc, auto_process=False)
        fq.process_queue(raw_output=MOCK_SENDQ)

        queue = fq.get_queue()
        self.assertEqual(len(queue), 2)
        # Check list_owner
        bob_jobs = fq.list_owner("bob")
        self.assertEqual(len(bob_jobs), 1)
        self.assertEqual(bob_jobs[0]["jid"], "102")

    def test_killjob_and_faxalter(self):
        fq = FaxQueue(auto_process=False)
        ok = MagicMock(returncode=0)

        # Commands run as argument lists with FAXUSER in the environment (no shell string, no injection)
        with patch("namifax.services.faxqueue.subprocess.run", return_value=ok) as run:
            self.assertTrue(fq.killjob("admin", 101))
            args, kwargs = run.call_args
            self.assertEqual(args[0], ["faxrm", "101"])
            self.assertEqual(kwargs["env"]["FAXUSER"], "admin")
            self.assertNotIn("shell", kwargs)

        # Test faxalter
        with patch("namifax.services.faxqueue.subprocess.run", return_value=ok) as run:
            ops = {"priority": 100, "tries": 5, "resubmit": True}
            self.assertTrue(fq.faxalter("bob", 102, ops))
            self.assertEqual(run.call_count, 2)  # faxalter + killjob for resubmit
            self.assertEqual(run.call_args_list[0].args[0][0], "faxalter")
            self.assertEqual(run.call_args_list[0].args[0][-1], "102")


if __name__ == "__main__":
    unittest.main()
