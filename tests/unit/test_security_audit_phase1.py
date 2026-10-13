import os
import unittest
from unittest.mock import patch, MagicMock
from pyramid import testing
from pyramid.httpexceptions import HTTPFound

from sqlsession import bare_session, empty_session, seeded_session
from namifax.services.user_account import NFUserAccount, md5_hash
from namifax.services.faxqueue import FaxQueue
from namifax.views.auth import login_post_view
from namifax.views.admin import get_all_syslogs


from linked_db import close_linked, linked_db


class TestSecurityAuditPhase1(unittest.TestCase):
    """Test suite covering Phase 1 security audit fixes (AUDIT-01, AUDIT-02, AUDIT-03, AUDIT-18)."""

    def setUp(self):
        self.config = testing.setUp()
        self.db, self.session = linked_db()

    def tearDown(self):
        testing.tearDown()
        close_linked(self.db, self.session)

    # =========================================================================
    # AUDIT-01: Admin Authentication Backdoor Removal
    # =========================================================================
    def test_admin_login_rejects_backdoor_password_when_password_changed(self):
        """Verify that admin login fails with initial 'password' once password has changed."""
        # 1. Update admin password to 'NewSecret123!'
        new_pwd_hash = md5_hash("NewSecret123!")
        self.db.query(f"UPDATE UserAccount SET password = '{new_pwd_hash}' WHERE username = 'admin'")

        # 2. Attempt login with old default password 'password'
        req_old = testing.DummyRequest(post={"username": "admin", "password": "password"})
        req_old.method = "POST"
        req_old.db = self.db
        req_old.dbsession = self.session

        with patch("namifax.views.auth.NFUserAccount", return_value=NFUserAccount(db=self.db)):
            res_old = login_post_view(req_old)

        # Must reject login (render error dict instead of redirect)
        self.assertIsInstance(res_old, dict)
        self.assertEqual(res_old.get("error"), "Invalid username or password")

        # 3. Attempt login with new password 'NewSecret123!'
        req_new = testing.DummyRequest(post={"username": "admin", "password": "NewSecret123!"})
        req_new.method = "POST"
        req_new.db = self.db
        req_new.dbsession = self.session

        with patch("namifax.views.auth.NFUserAccount", return_value=NFUserAccount(db=self.db)):
            res_new = login_post_view(req_new)

        # Must succeed and redirect to inbox
        self.assertIsInstance(res_new, HTTPFound)
        self.assertEqual(res_new.location, "/inbox")

    def test_default_seeded_admin_login_succeeds(self):
        """Verify that default admin login works via standard user_svc.login without backdoor."""
        # Ensure default seed has 'password' hash
        default_hash = md5_hash("password")
        self.db.query(f"UPDATE UserAccount SET password = '{default_hash}' WHERE username = 'admin'")

        req = testing.DummyRequest(post={"username": "admin", "password": "password"})
        req.method = "POST"
        req.db = self.db
        req.dbsession = self.session

        with patch("namifax.views.auth.NFUserAccount", return_value=NFUserAccount(db=self.db)):
            res = login_post_view(req)

        self.assertIsInstance(res, HTTPFound)
        self.assertEqual(res.location, "/inbox")

    # =========================================================================
    # AUDIT-02: HylaFAX CLI Subprocess Injection Prevention
    # =========================================================================
    @patch("subprocess.run")
    def test_killjob_safe_execution_and_meta_char_safety(self, mock_run):
        """Verify killjob uses list arguments without shell=True and handles meta-chars safely."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc

        fq = FaxQueue(auto_process=False)
        malicious_user = "admin; rm -rf /"
        job_id = 999

        ret = fq.killjob(malicious_user, job_id)

        self.assertTrue(ret)
        self.assertEqual(mock_run.call_count, 1)

        called_args, called_kwargs = mock_run.call_args
        cmd_list = called_args[0]

        # Must be passed as a list of strings
        self.assertIsInstance(cmd_list, list)
        self.assertEqual(cmd_list, ["faxrm", "999"])

        # shell must be False or not True
        self.assertFalse(called_kwargs.get("shell", False))

        # FAXUSER must be in environment safely
        self.assertIn("env", called_kwargs)
        self.assertEqual(called_kwargs["env"].get("FAXUSER"), malicious_user)

    @patch("subprocess.run")
    def test_shell_exec_runs_an_argument_list_without_a_shell(self, mock_run):
        """FaxQueue.shell_exec (faxstat -s / -d) takes an argument list and no shell, so metacharacters stay plain text."""
        mock_run.return_value = MagicMock(stdout="out")
        fq = FaxQueue(auto_process=False)
        self.assertEqual(fq.shell_exec("faxstat -s"), "out")
        argv = mock_run.call_args.args[0]
        self.assertEqual(argv, ["faxstat", "-s"])
        self.assertFalse(mock_run.call_args.kwargs.get("shell", False))
        fq.shell_exec("faxstat -s; touch /tmp/pwned")
        self.assertEqual(mock_run.call_args.args[0], ["faxstat", "-s;", "touch", "/tmp/pwned"])
        self.assertFalse(mock_run.call_args.kwargs.get("shell", False))

    def test_shell_exec_with_a_missing_program_gives_an_empty_queue_not_an_error_text(self):
        """No faxstat on the host: the output is empty (so no row is parsed from an error message)."""
        fq = FaxQueue(auto_process=False, faxsendq_cmd="/nonexistent/faxstat -s")
        self.assertEqual(fq.shell_exec("/nonexistent/faxstat -s"), "")
        self.assertEqual(fq.process_queue(), [])
        self.assertEqual(fq.shell_exec(""), "")
        self.assertEqual(fq.shell_exec("unterminated 'quote"), "")

    @patch("subprocess.run")
    def test_killjob_returns_false_on_failure(self, mock_run):
        """Verify killjob returns False when subprocess exits non-zero."""
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_run.return_value = mock_proc

        fq = FaxQueue(auto_process=False)
        ret = fq.killjob("admin", 123)
        self.assertFalse(ret)

    @patch("subprocess.run")
    def test_faxalter_safe_execution_and_meta_char_safety(self, mock_run):
        """Verify faxalter parses operations as list args without shell=True."""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc

        fq = FaxQueue(auto_process=False)
        ops = {
            "sendtime": '12:00"; rm -rf /',
            "destination": "01012345678",
            "priority": "normal",
        }

        ret = fq.faxalter("admin", 101, ops)

        self.assertTrue(ret)
        self.assertEqual(mock_run.call_count, 1)

        called_args, called_kwargs = mock_run.call_args
        cmd_list = called_args[0]

        # Must be a list of args
        self.assertIsInstance(cmd_list, list)
        self.assertEqual(cmd_list[0], "faxalter")
        self.assertIn("-a", cmd_list)
        self.assertIn('12:00"; rm -rf /', cmd_list)
        self.assertIn("-d", cmd_list)
        self.assertIn("01012345678", cmd_list)
        self.assertIn("-P", cmd_list)
        self.assertIn("normal", cmd_list)
        self.assertEqual(cmd_list[-1], "101")

        # shell must not be True
        self.assertFalse(called_kwargs.get("shell", False))

    @patch("subprocess.run")
    def test_faxalter_returns_false_on_failure(self, mock_run):
        """Verify faxalter returns False when subprocess fails."""
        mock_proc = MagicMock()
        mock_proc.returncode = 2
        mock_run.return_value = mock_proc

        fq = FaxQueue(auto_process=False)
        ret = fq.faxalter("admin", 101, {"priority": "high"})
        self.assertFalse(ret)

    # =========================================================================
    # AUDIT-03: System Logs SQL Injection Prevention
    # =========================================================================
    def test_get_all_syslogs_handles_sql_injection_payload(self):
        """Verify get_all_syslogs treats quotes and injection payloads as plain data."""
        from sqlalchemy.orm import Session

        import namifax.models  # noqa: F401  (registers every model)
        from namifax.db.provider import create_sa_engine
        from namifax.models import SysLog
        from namifax.models.meta import Base

        engine = create_sa_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(SysLog(logdate="2026-10-01 10:00:00", logtext="Legitimate security test log"))
            session.flush()

            # Attack payload in kw
            malicious_kw = "' OR '1'='1"
            rows = get_all_syslogs(kw=malicious_kw, session=session)
            # Should safely search for the literal string and return 0 results
            self.assertEqual(len(rows), 0)

            # Legitimate search should find the record
            legit_rows = get_all_syslogs(kw="security test", session=session)
            self.assertEqual(len(legit_rows), 1)
            self.assertEqual(legit_rows[0]["logtext"], "Legitimate security test log")

            # Attack payload in date parts
            malicious_day = "01' OR '1'='1"
            date_rows = get_all_syslogs(day=malicious_day, month="10", year="2026", session=session)
            self.assertEqual(len(date_rows), 0)
        engine.dispose()

    # =========================================================================
    # AUDIT-18: Package Import Path Verification
    # =========================================================================
    def test_audit_18_imports_namifax_db_engine(self):
        """Verify that all AUDIT-18 affected modules import from namifax.db.engine."""
        import ast

        files_to_check = [
            "src/namifax/services/ocr.py",
            "src/namifax/services/storage_lifecycle.py",
            "src/namifax/services/cover_studio.py",
            "src/namifax/views/admin.py",
        ]

        for rel_path in files_to_check:
            abs_path = os.path.abspath(rel_path)
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertNotIn(
                "from avantfax.db.engine import DatabaseEngine",
                content,
                f"File {rel_path} still imports DatabaseEngine from avantfax.db.engine!",
            )

        # the services are ORM-backed now: none of them imports the (removed) legacy engine
        for rel_path in files_to_check:
            with open(os.path.abspath(rel_path), "r", encoding="utf-8") as f:
                self.assertNotIn("namifax.db.engine", f.read(), rel_path)


if __name__ == "__main__":
    unittest.main()
