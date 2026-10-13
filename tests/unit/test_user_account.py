import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from sqlsession import empty_session, seeded_session
from namifax.services.user_account import NFUserAccount, UserAccountService
from namifax.services.user_passwords import NFUserPasswords


class TestAFUserAccount(unittest.TestCase):
    def setUp(self):
        self.engine = empty_session()


        self.passwords_svc = NFUserPasswords(db=self.engine)
        self.user_svc = NFUserAccount(db=self.engine, user_passwords=self.passwords_svc)

    def tearDown(self):
        self.engine.disconnect()

    def test_create_account(self):
        ok = self.user_svc.create({
            "name": "Alice Smith",
            "email": "alice@example.com",
            "username": "asmith",
            "password": "Password123",
            "pwdcycle": 0,
        })
        self.assertTrue(ok)
        uid = self.user_svc.get_uid()
        self.assertIsNotNone(uid)

        # Duplicate username
        dup_user = NFUserAccount(db=self.engine, user_passwords=self.passwords_svc)
        ok2 = dup_user.create({
            "name": "Alice 2",
            "email": "alice2@example.com",
            "username": "asmith",
            "password": "Password123",
        })
        self.assertFalse(ok2)
        self.assertIn("username", dup_user.get_error().lower())

        # Duplicate email
        dup_email = NFUserAccount(db=self.engine, user_passwords=self.passwords_svc)
        ok3 = dup_email.create({
            "name": "Alice 3",
            "email": "alice@example.com",
            "username": "asmith3",
            "password": "Password123",
        })
        self.assertFalse(ok3)

        # Invalid username characters
        bad_name = NFUserAccount(db=self.engine, user_passwords=self.passwords_svc)
        ok4 = bad_name.create({
            "name": "Bad User",
            "email": "bad@example.com",
            "username": "bad user!",
            "password": "Password123",
        })
        self.assertFalse(ok4)

    def test_login_and_roles(self):
        self.user_svc.create({
            "name": "Admin User",
            "email": "admin@example.com",
            "username": "admin",
            "password": "SecretPassword1",
            "is_admin": 1,
            "acc_enabled": 1,
        })

        client = NFUserAccount(db=self.engine, user_passwords=self.passwords_svc)

        # 1. Successful regular login
        ok = client.login("admin", "SecretPassword1")
        self.assertTrue(ok)
        self.assertTrue(client.check_login())
        self.assertTrue(client.check_admin_login())

        # 2. Failed password
        fail_client = NFUserAccount(db=self.engine, user_passwords=self.passwords_svc)
        self.assertFalse(fail_client.login("admin", "WrongPassword"))
        self.assertFalse(fail_client.check_login())

        # 3. Disabled account
        self.engine.query("UPDATE UserAccount SET acc_enabled = 0 WHERE username = 'admin'")
        dis_client = NFUserAccount(db=self.engine, user_passwords=self.passwords_svc)
        self.assertFalse(dis_client.login("admin", "SecretPassword1"))

    def test_change_password_and_history(self):
        self.user_svc.create({
            "name": "Bob",
            "email": "bob@example.com",
            "username": "bob",
            "password": "InitPassword1",
            "pwd_reuse": 0,
        })
        uid = self.user_svc.get_uid()
        self.passwords_svc.log_password("InitPassword1", uid)

        # 1. Too short
        self.assertFalse(self.user_svc.change_password("short"))

        # 2. Reuse old password
        self.assertFalse(self.user_svc.change_password("InitPassword1"))

        # 3. Valid new password
        self.assertTrue(self.user_svc.change_password("BrandNewPass1"))

        # 4. Verify login with new password
        tester = NFUserAccount(db=self.engine, user_passwords=self.passwords_svc)
        self.assertTrue(tester.login("bob", "BrandNewPass1"))

    def test_reset_password(self):
        self.user_svc.create({
            "name": "Charlie",
            "email": "charlie@example.com",
            "username": "charlie",
            "password": "CharliePassword1",
        })

        ok, newpwd = self.user_svc.reset_password("charlie@example.com")
        self.assertTrue(ok)
        self.assertIsNotNone(newpwd)

        tester = NFUserAccount(db=self.engine, user_passwords=self.passwords_svc)
        self.assertTrue(tester.login("charlie", newpwd))
        self.assertTrue(tester.is_expired())  # wasreset requires password change

    def test_remove_account(self):
        self.user_svc.create({
            "name": "Dave",
            "email": "dave@example.com",
            "username": "dave",
            "password": "DavePassword1",
        })
        uid = self.user_svc.get_uid()

        self.assertTrue(self.user_svc.remove(uid))

        self.engine.query("SELECT * FROM UserAccount WHERE uid = :uid", {"uid": uid})
        rec = self.engine.get_records()[0]
        self.assertEqual(rec["deleted"], 1)
        self.assertEqual(rec["acc_enabled"], 0)
        # username/email are NOT NULL: a unique placeholder frees the real name and address for reuse
        self.assertEqual(rec["username"], f"deleted.{uid}")
        self.assertEqual(rec["email"], f"deleted.{uid}@invalid.invalid")
        self.assertEqual(rec["password"], "")

    def test_devices_and_routes_serialization(self):
        self.user_svc.create({
            "name": "Eve",
            "email": "eve@example.com",
            "username": "eve",
            "password": "EvePassword1",
        })

        self.user_svc.set_modemdevs(["ttyS0", "ttyS1"])
        self.user_svc.set_faxcats([1, 2])
        self.user_svc.set_didrouting([10, 20])
        self.user_svc.update()

        reloaded = NFUserAccount(db=self.engine, user_passwords=self.passwords_svc)
        reloaded.load(self.user_svc.get_uid())

        self.assertEqual(reloaded.get_modemdevs(), ["ttyS0", "ttyS1"])
        self.assertEqual(reloaded.get_faxcats(), ["1", "2"])
        self.assertEqual(reloaded.get_didrouting(), ["10", "20"])


if __name__ == "__main__":
    unittest.main()
