#!/usr/bin/env python3
"""Functional integration tests for Pyramid authorization, SecurityPolicy, and view permissions."""

import os
import sys
import unittest
from webtest import TestApp

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from namifax import create_app as pyramid_app_factory
from namifax.security import NamiFaxSecurityPolicy
from namifax.sessions import SessionManager


class TestPyramidAuthorization(unittest.TestCase):
    """Test suite verifying Pyramid security policy and view-level authorization."""

    @classmethod
    def setUpClass(cls):
        settings = {
            "pyramid.reload_templates": False,
            "pyramid.debug_authorization": False,
            "pyramid.default_locale_name": "en",
            "sqlalchemy.url": "sqlite:///:memory:",
        }
        wsgi_app = pyramid_app_factory(None, **settings)
        cls.app = TestApp(wsgi_app)
        cls.session_mgr = getattr(wsgi_app.registry, "namifax_policy", None).session_manager

    def test_public_home_accessible_anonymously(self):
        res = self.app.get("/", status=200)
        self.assertIn("namifax", res.text.lower())

    def test_anonymous_access_to_protected_views(self):
        # /inbox requires permission='view' -> 401
        res = self.app.get("/inbox", status=401)
        self.assertEqual(res.json["code"], 401)

        # /admin requires permission='admin' -> 401
        res = self.app.get("/admin", status=401)
        self.assertEqual(res.json["code"], 401)

    def test_regular_user_access(self):
        # Create regular user session
        sess = self.session_mgr.create_session(user_id=10, username="regular_user", is_admin=False)
        headers = {"Authorization": f"Bearer {sess.token}"}

        # /inbox (permission='view') should succeed
        res = self.app.get("/inbox", headers=headers, status=200)
        self.assertIn("items", res.json)

        # /admin (permission='admin') should be 403 Forbidden
        res_admin = self.app.get("/admin", headers=headers, status=403)
        self.assertEqual(res_admin.json["code"], 403)

    def test_admin_user_access(self):
        # Create admin user session
        sess = self.session_mgr.create_session(user_id=1, username="admin_user", is_admin=True)
        headers = {"Authorization": f"Bearer {sess.token}"}

        # Both /inbox and /admin should succeed
        self.app.get("/inbox", headers=headers, status=200)
        res_admin = self.app.get("/admin", headers=headers, status=200)
        self.assertIn("modems", res_admin.json)
        self.assertIn("users", res_admin.json)

    def test_browser_unauthenticated_redirect_to_login(self):
        # Browser navigating to protected page should be redirected to /login with 302
        headers = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
        res = self.app.get("/inbox", headers=headers, status=302)
        self.assertIn("/login", res.headers.get("Location", ""))

    def test_browser_unauthorized_admin_redirect_to_inbox(self):
        # Regular user accessing /admin in browser should be redirected to /inbox
        sess = self.session_mgr.create_session(user_id=10, username="regular_user", is_admin=False)
        headers = {
            "Authorization": f"Bearer {sess.token}",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        res = self.app.get("/admin", headers=headers, status=302)
        self.assertIn("/inbox", res.headers.get("Location", ""))


if __name__ == "__main__":
    unittest.main()
