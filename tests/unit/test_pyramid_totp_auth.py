import unittest
from unittest.mock import patch, MagicMock
from pyramid import testing
from pyramid.httpexceptions import HTTPFound
from linked_db import close_linked, linked_db
from namifax.services.totp import TotpService
from namifax.views.auth import login_post_view, login_totp_view


class TestPyramidTotpAuth(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()
        self.db, self.session = linked_db()

        # Create user
        self.db.query("INSERT INTO UserAccount (username, password, email, is_admin, last_login) VALUES ('bob', 'hashedpw', 'bob@test.com', 1, '2026-01-01 10:00:00')")
        self.uid = self.db.get_insert_id()

        # Enable 2FA for bob
        self.totp_service = TotpService(self.db)
        self.secret = self.totp_service.generate_secret()
        with patch.object(self.totp_service, "verify_code", return_value=True):
            self.totp_service.enable_totp(self.uid, self.secret, "123456")

    def tearDown(self):
        testing.tearDown()
        close_linked(self.db, self.session)

    @patch("namifax.views.auth.NFUserAccount")
    def test_login_redirects_to_totp_if_enabled(self, mock_account_cls):
        mock_account = MagicMock()
        mock_account.load_user.return_value = True
        mock_account.verify_password.return_value = True
        mock_account.get_uid.return_value = self.uid
        mock_account.get_username.return_value = "bob"
        mock_account.is_expired.return_value = False
        mock_account_cls.return_value = mock_account

        req = testing.DummyRequest(post={"username": "bob", "password": "password"})
        req.method = "POST"
        req.db = self.db
        req.dbsession = self.session

        res = login_post_view(req)
        self.assertIsInstance(res, HTTPFound)
        self.assertIn("/login/totp", res.location)
        self.assertEqual(req.session.get("2fa_pending_uid"), self.uid)

    def test_login_totp_view_success(self):
        req = testing.DummyRequest(post={"code": "123456"})
        req.method = "POST"
        req.session["2fa_pending_uid"] = self.uid
        req.db = self.db
        req.dbsession = self.session

        with patch.object(TotpService, "verify_user_login", return_value=True):
            res = login_totp_view(req)
            self.assertIsInstance(res, HTTPFound)
            self.assertEqual(res.location, "/inbox")
            self.assertNotIn("2fa_pending_uid", req.session)
            self.assertEqual(req.session.get("user_id"), self.uid)

    def test_login_totp_view_invalid_code(self):
        req = testing.DummyRequest(post={"code": "000000"})
        req.method = "POST"
        req.session["2fa_pending_uid"] = self.uid
        req.db = self.db
        req.dbsession = self.session

        with patch.object(TotpService, "verify_user_login", return_value=False):
            res = login_totp_view(req)
            self.assertIn("error", res)
            self.assertIn("Invalid", res["error"])


if __name__ == "__main__":
    unittest.main()
