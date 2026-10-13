"""P1: SessionManager lives in namifax.sessions so namifax.web can be removed."""

from __future__ import annotations

import subprocess
import sys


def test_sessions_module_provides_session_classes():
    from namifax.sessions import Session, SessionManager

    mgr = SessionManager(ttl_seconds=60)
    sess = mgr.create_session(user_id=1, username="admin", is_admin=True)
    assert isinstance(sess, Session)
    assert mgr.get_session(sess.token) is sess
    assert mgr.destroy_session(sess.token) is True
    assert mgr.get_session(sess.token) is None


def test_security_policy_does_not_import_the_web_package():
    code = (
        "import sys; import namifax.security; "
        "bad = [m for m in sys.modules if m == 'namifax.web' or m.startswith('namifax.web.')]; "
        "sys.exit(1 if bad else 0)"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
