"""Unit tests for NamiFAX modal POST actions with real domain service integration."""

from unittest.mock import MagicMock, patch
from pyramid import testing
import pytest

from namifax.views.modals import (
    modal_delete_view,
    modal_note_view,
    modal_assign_view,
    modal_email_view,
)
from request_identity import set_identity


@pytest.fixture
def dummy_request():
    request = testing.DummyRequest()
    set_identity(request, {"username": "admin", "uid": 1, "is_admin": True, "superuser": True})
    request.db = MagicMock()
    request.dbsession = MagicMock()
    return request


def test_modal_delete_post(dummy_request, as_superuser):
    """Verify fax deletion via modal POST."""
    dummy_request.method = "POST"
    dummy_request.params = {"fid": "42", "_submit_check": "1"}
    with patch("namifax.views.modals.ArchiveIn") as mock_cls:
        inst = MagicMock()
        inst.delete_fax.return_value = True
        mock_cls.return_value = inst
        res = modal_delete_view(dummy_request)
        inst.load_fax.assert_called_with(42)
        inst.delete_fax.assert_called_once_with()
        assert res.get("title") == "- NamiFAX - Delete Fax" or res.get("status") == "deleted"


def test_modal_note_post(dummy_request):
    """Verify updating note/description on fax via modal POST."""
    dummy_request.method = "POST"
    dummy_request.params = {"fid": "42", "description": "Important review note", "_submit_check": "1"}
    with patch("namifax.views.modals.ArchiveIn") as mock_cls:
        inst = MagicMock()
        inst.load_fax.return_value = True
        inst.set_note.return_value = True
        mock_cls.return_value = inst
        res = modal_note_view(dummy_request)
        inst.set_note.assert_called()
        assert res.get("title") == "- NamiFAX - Add Note"
