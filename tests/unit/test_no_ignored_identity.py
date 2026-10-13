"""``request.__dict__["identity"] = ...`` on a DummyRequest is silently ignored (see tests/request_identity.py).

72 tests used it and so ran as the view's default administrator, whatever identity they claimed. Use ``set_identity``.
"""

from __future__ import annotations

from pathlib import Path


def test_no_test_puts_an_identity_into_the_request_dict():
    here = Path(__file__).resolve().parent.parent
    offenders = [str(p.relative_to(here)) for p in here.rglob("*.py")
                 if p.name != "request_identity.py" and 'identity"] =' in p.read_text(encoding="utf-8")
                 and '__dict__["identity"]' in p.read_text(encoding="utf-8") and p != Path(__file__).resolve()]
    assert offenders == [], f"use tests/request_identity.set_identity instead in: {offenders}"
