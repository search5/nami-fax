"""``"²".isdigit()`` is true but ``int("²")`` raises: a request carrying such a value must be refused like any other bad number, never a 500."""

from __future__ import annotations

import pytest


@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


@pytest.mark.parametrize("path", [
    "/ajax/deletefaxes?fids=%C2%B2", "/ajax/deletefaxes?fids=1,%C2%B2", "/ajax/archivefaxes?fids=%C2%B2",
    "/inbox?pageindex=%C2%B2", "/inbox?pagelimit=%C2%B2", "/fax?fid=%C2%B2", "/modals/email?fid=%C2%B2",
    "/admin/users?uid=%C2%B2",
])
def test_a_superscript_digit_is_not_a_number(client, path):
    res = client.get(path, expect_errors=True)
    assert res.status_int < 500, (path, res.status_int)


def test_no_string_digit_check_is_left_that_int_cannot_parse():
    import re
    from pathlib import Path

    src = Path(__file__).resolve().parents[2] / "src" / "namifax"
    left = [f"{p.relative_to(src)}:{n}" for p in src.rglob("*.py") for n, line in enumerate(p.read_text().splitlines(), 1)
            if re.search(r"\.isdigit\(\)", line) and "any(c.isdigit() for c in number)" not in line]
    assert left == []
