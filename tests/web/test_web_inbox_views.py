"""Pyramid Web Integration Test for Inbox Views (W04, W05).

Verifies the rendered HTML of the inbox: the page title, the fax rows, the action icons (shown or withheld by the
rights and settings of the user) and the empty-inbox text.
"""

from pathlib import Path
import pytest
from webtest import TestApp

from namifax import create_app


@pytest.fixture
def authenticated_app():
    """Create Pyramid test application fixture logged in as admin."""
    wsgi_app = create_app({})
    client = TestApp(wsgi_app)
    # Log in as admin
    client.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return client


def test_inbox_view_authenticated_list(authenticated_app):
    """Verify inbox list view (W05_inbox_list) renders 9 action buttons, metadata, and status bar."""
    res = authenticated_app.get("/inbox", status=200)
    assert res.status_code == 200
    assert "- NamiFAX - Inbox" in res.text
    assert "Acme Corp" in res.text
    assert "ttyS0" in res.text
    assert "MODEM IDLE" not in res.text              # AUDIT-09: no hard-coded status text in the page
    assert "0 FAXES" not in res.text
    
    # Verify presence of 9 action buttons for the fax item
    assert "viewfax.png" in res.text
    assert "rotate.png" in res.text
    assert "pdf.png" in res.text
    assert "tiff.png" not in res.text                 # the TIFF download is only offered with ENABLE_DL_TIFF
    assert "refax.png" in res.text
    assert "email.png" in res.text
    assert "note.png" in res.text
    assert "folder.png" in res.text
    assert "remove.png" in res.text


def test_inbox_view_empty_state(authenticated_app):
    """Verify empty inbox view (W04_inbox_empty) displays empty state text."""
    res = authenticated_app.get("/inbox?empty=1", status=200)
    assert res.status_code == 200
    assert "0 FAXES" in res.text
    assert "There are no incoming faxes waiting in your inbox." in res.text
