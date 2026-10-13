#!/usr/bin/env python3
"""Unit tests for namifax.security SecurityPolicy and Authorization."""

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from namifax.security import NamiFaxSecurityPolicy, RootContext
from namifax.sessions import SessionManager


class MockRequest:
    """Mock Pyramid Request for security policy testing."""

    def __init__(self, headers=None, cookies=None):
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.response = MagicMock()


class TestSecurityPolicy(unittest.TestCase):
    """Test suite for NamiFaxSecurityPolicy."""

    def setUp(self):
        self.session_mgr = SessionManager()
        self.policy = NamiFaxSecurityPolicy(session_manager=self.session_mgr)

    def test_anonymous_access(self):
        req = MockRequest()
        ctx = RootContext(req)

        self.assertIsNone(self.policy.identity(req))
        self.assertIsNone(self.policy.authenticated_userid(req))

        # Permissions check
        self.assertTrue(self.policy.permits(req, ctx, "public"))
        self.assertFalse(self.policy.permits(req, ctx, "view"))
        self.assertFalse(self.policy.permits(req, ctx, "admin"))

    def test_authenticated_user_access(self):
        sess = self.session_mgr.create_session(user_id=10, username="alice", is_admin=False)
        req = MockRequest(headers={"Authorization": f"Bearer {sess.token}"})
        ctx = RootContext(req)

        ident = self.policy.identity(req)
        self.assertIsNotNone(ident)
        self.assertEqual(ident["username"], "alice")
        self.assertEqual(self.policy.authenticated_userid(req), "alice")

        # Permissions check
        self.assertTrue(self.policy.permits(req, ctx, "public"))
        self.assertTrue(self.policy.permits(req, ctx, "view"))
        self.assertTrue(self.policy.permits(req, ctx, "send_fax"))
        self.assertFalse(self.policy.permits(req, ctx, "admin"))

    def test_admin_user_access(self):
        sess = self.session_mgr.create_session(user_id=1, username="admin", is_admin=True)
        req = MockRequest(cookies={"namifax_session": sess.token})
        ctx = RootContext(req)

        ident = self.policy.identity(req)
        self.assertIsNotNone(ident)
        self.assertTrue(ident["is_admin"])

        # Admin permission
        self.assertTrue(self.policy.permits(req, ctx, "public"))
        self.assertTrue(self.policy.permits(req, ctx, "view"))
        self.assertTrue(self.policy.permits(req, ctx, "send_fax"))
        self.assertTrue(self.policy.permits(req, ctx, "admin"))

    def test_remember_and_forget(self):
        req = MockRequest()
        rem_headers = self.policy.remember(req, "bob", token="test_token_123")
        self.assertTrue(any("namifax_session=test_token_123" in h[1] for h in rem_headers))

        req_auth = MockRequest(cookies={"namifax_session": "test_token_123"})
        forget_headers = self.policy.forget(req_auth)
        self.assertTrue(any("Max-Age=0" in h[1] for h in forget_headers))


if __name__ == "__main__":
    unittest.main()
