import unittest
import pyotp
from sqlsession import empty_session, seeded_session
from src.namifax.services.totp import TotpService


class TestTotpService(unittest.TestCase):
    def setUp(self):
        self.db = seeded_session()
        self.service = TotpService(self.db)

        # Create sample user
        self.db.query("INSERT INTO UserAccount (username, password, email) VALUES ('alice', 'pass123', 'alice@test.com')")
        self.uid = self.db.get_insert_id()

    def test_generate_secret_and_uri(self):
        secret = self.service.generate_secret()
        self.assertIsInstance(secret, str)
        self.assertGreaterEqual(len(secret), 16)

        uri = self.service.get_provisioning_uri("alice", secret)
        self.assertTrue(uri.startswith("otpauth://totp/NamiFAX:alice?secret="))

    def test_verify_code(self):
        secret = self.service.generate_secret()
        totp = pyotp.TOTP(secret)
        current_code = totp.now()

        # Valid code
        self.assertTrue(self.service.verify_code(secret, current_code))
        # Invalid code
        self.assertFalse(self.service.verify_code(secret, "000000"))

    def test_enable_and_verify_user_totp(self):
        secret = self.service.generate_secret()
        totp = pyotp.TOTP(secret)
        code = totp.now()

        res = self.service.enable_totp(self.uid, secret, code)
        self.assertTrue(res["success"])
        self.assertEqual(len(res["backup_codes"]), 8)
        self.assertTrue(self.service.is_totp_enabled(self.uid))

        # Verify using current TOTP code
        self.assertTrue(self.service.verify_user_login(self.uid, totp.now()))

        # Verify using one of the backup codes
        backup_code = res["backup_codes"][0]
        self.assertTrue(self.service.verify_user_login(self.uid, backup_code))

        # Re-using the same backup code must fail (single-use)
        self.assertFalse(self.service.verify_user_login(self.uid, backup_code))

    def test_disable_totp(self):
        secret = self.service.generate_secret()
        totp = pyotp.TOTP(secret)
        self.service.enable_totp(self.uid, secret, totp.now())
        self.assertTrue(self.service.is_totp_enabled(self.uid))

        ok = self.service.disable_totp(self.uid)
        self.assertTrue(ok)
        self.assertFalse(self.service.is_totp_enabled(self.uid))


if __name__ == "__main__":
    unittest.main()
