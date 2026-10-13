"""When the database is down the visitor gets a plain page that retries by itself (the original no-database.php), not a traceback."""

from __future__ import annotations

from unittest.mock import patch

from sqlalchemy.exc import OperationalError


def test_a_database_that_is_down_shows_the_no_database_page(testapp):
    boom = OperationalError("SELECT 1", {}, Exception("connection refused"))
    with patch("namifax.views.auth.NFUserAccount", side_effect=boom):
        res = testapp.post("/login", {"username": "admin", "password": "x", "_submit_check": "1"}, status=503)
    assert 'http-equiv="refresh"' in res.text and "refused" not in res.text
    assert "database" in res.text.lower()
