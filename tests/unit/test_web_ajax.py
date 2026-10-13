"""Unit tests for NamiFAX asynchronous AJAX API views."""

from unittest.mock import MagicMock, patch
from pyramid import testing
import pytest

from namifax.views.ajax import (
    ajax_modem_status,
    ajax_inbox_count,
    ajax_addressbook_suggest,
    ajax_emailbook_suggest,
    ajax_addressbook_prefill,
    ajax_distrolist_faxes,
    ajax_archive_fax,
    ajax_faxalter,
)


@pytest.fixture
def dummy_request(seeded_db, dbsession):
    request = testing.DummyRequest()
    request.db = seeded_db
    request.dbsession = dbsession
    request.session = {"user_id": 1, "username": "admin", "is_admin": True, "superuser": True}
    return request


def test_ajax_modem_status(dummy_request, as_superuser):
    """Verify XML response structure for modem status."""
    res = ajax_modem_status(dummy_request)
    assert res.status_code == 200
    assert "text/xml" in res.content_type
    assert "<response>" in res.text
    assert "<modem>" in res.text
    assert "<status>" in res.text


def test_ajax_inbox_count(dummy_request):
    """Verify text response for unread inbox count."""
    res = ajax_inbox_count(dummy_request)
    assert res.status_code == 200
    assert "text/plain" in res.content_type
    assert res.text.strip().isdigit() or "|" in res.text


def test_ajax_addressbook_suggest(dummy_request):
    """Verify XML response for company auto-suggest."""
    dummy_request.GET["q"] = "Acme"
    res = ajax_addressbook_suggest(dummy_request)
    assert res.status_code == 200
    assert "text/xml" in res.content_type
    assert "<response>" in res.text
    assert "<company>" in res.text
    assert "<faxnum>" in res.text


def test_ajax_emailbook_suggest(dummy_request):
    """Verify XML response for email auto-suggest."""
    dummy_request.GET["q"] = "user"
    res = ajax_emailbook_suggest(dummy_request)
    assert res.status_code == 200
    assert "text/xml" in res.content_type
    assert "<response>" in res.text
    assert "<email>" in res.text


def test_ajax_addressbook_prefill(dummy_request):
    """Verify XML response for contact prefill."""
    dummy_request.GET["fnid"] = "1"
    res = ajax_addressbook_prefill(dummy_request)
    assert res.status_code == 200
    assert "text/xml" in res.content_type
    assert "<response>" in res.text
    assert "<to_company>" in res.text
    assert "<to_person>" in res.text




def test_ajax_archive_fax(dummy_request):
    """Verify 200 OK response for archiving faxes."""
    dummy_request.params = {"fids": "1,2"}
    dummy_request.headers["X-Requested-With"] = "XMLHttpRequest"
    with patch("namifax.views.ajax.load_fax", return_value=False):
        res = ajax_archive_fax(dummy_request)
    assert res.status_code == 200


def test_ajax_faxalter_get(dummy_request):
    """The dialog for a queued job is rendered from a template (its fields are checked in test_faxalter_dialog.py)."""
    dummy_request.GET["jid"] = "1"
    res = ajax_faxalter(dummy_request)
    assert res["title"] == "- NamiFAX - Modify Fax Job" and res["values"]["jid"] == "1"
    assert res["priority_list"][0] == "*" and res["error"] is None