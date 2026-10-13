import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from sqlsession import empty_session, seeded_session
from namifax.services.dynconf import DynamicConfig, DynamicConfigService


class TestDynamicConfig(unittest.TestCase):
    def setUp(self):
        self.engine = empty_session()

        self.service = DynamicConfig(db=self.engine)

    def tearDown(self):
        self.engine.disconnect()

    def test_empty_rules(self):
        rules = self.service.list_rules()
        self.assertEqual(rules, [])

    def test_create_and_lookup_specific_device(self):
        ok = self.service.create("ttyS0", "12345")
        self.assertTrue(ok)
        self.assertIsNotNone(self.service.get_dynconf_id())

        # Match specific device
        self.assertTrue(self.service.lookup("ttyS0", "12345"))

        # Different device should not match
        self.assertFalse(self.service.lookup("ttyS1", "12345"))

        # Different callid should not match
        self.assertFalse(self.service.lookup("ttyS0", "99999"))

    def test_create_and_lookup_global_device(self):
        # Global rule (device = None or "")
        ok = self.service.create(None, "spam_number")
        self.assertTrue(ok)

        # Matches any device
        self.assertTrue(self.service.lookup("ttyS0", "spam_number"))
        self.assertTrue(self.service.lookup("ttyS1", "spam_number"))
        self.assertTrue(self.service.lookup(None, "spam_number"))

    def test_create_duplicate(self):
        self.assertTrue(self.service.create("ttyS0", "dup_callid"))
        ok = self.service.create("ttyS0", "dup_callid")
        self.assertFalse(ok)
        self.assertEqual(self.service.get_error(), "Rule already exists")

    def test_list_rules_ordered_by_callid(self):
        self.service.create("ttyS0", "999")
        self.service.create("ttyS0", "111")
        self.service.create("ttyS0", "555")

        rules = self.service.list_rules()
        callids = [r["callid"] for r in rules]
        self.assertEqual(callids, ["111", "555", "999"])

    def test_load_and_save_rule(self):
        self.service.create("ttyS0", "original_callid")
        rule_id = self.service.get_dynconf_id()

        loader = DynamicConfig(db=self.engine)
        self.assertTrue(loader.load_rule(rule_id))
        self.assertEqual(loader.get_device(), "ttyS0")
        self.assertEqual(loader.get_callid(), "original_callid")

        # Save modifications
        ok = loader.save_rule("ttyS1", "updated_callid")
        self.assertTrue(ok)

        # Verify updated in DB
        reloader = DynamicConfig(db=self.engine)
        self.assertTrue(reloader.load_rule(rule_id))
        self.assertEqual(reloader.get_device(), "ttyS1")
        self.assertEqual(reloader.get_callid(), "updated_callid")

    def test_load_nonexistent_rule(self):
        loader = DynamicConfig(db=self.engine)
        self.assertFalse(loader.load_rule(99999))
        self.assertIn("99999", loader.get_error())

    def test_save_rule_without_load(self):
        unloaded = DynamicConfig(db=self.engine)
        self.assertFalse(unloaded.save_rule("ttyS0", "callid"))
        self.assertEqual(unloaded.get_error(), "DynConf not loaded")

    def test_remove_rule(self):
        self.service.create("ttyS0", "to_delete")
        rule_id = self.service.get_dynconf_id()

        ok = self.service.remove(rule_id)
        self.assertTrue(ok)

        self.assertFalse(self.service.lookup("ttyS0", "to_delete"))


if __name__ == "__main__":
    unittest.main()
