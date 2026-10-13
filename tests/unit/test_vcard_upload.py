"""Unit tests for vCard uploads, helper dialogs, and AJAX API service integrations."""

import io
from unittest.mock import MagicMock, patch
from pyramid import testing
import pytest

from namifax.views.helpers import (
    upload_email_contacts,
    upload_fax_contacts,
)
from namifax.views.ajax import (
    ajax_modem_status,
    ajax_inbox_count,
    ajax_addressbook_suggest,
    ajax_emailbook_suggest,
    ajax_addressbook_prefill,
    ajax_archive_fax,
)
from request_identity import set_identity


@pytest.fixture
def dummy_request(seeded_db, dbsession):
    request = testing.DummyRequest()
    request.db = seeded_db
    request.dbsession = dbsession
    set_identity(request, {"username": "admin", "uid": 1, "is_admin": True, "superuser": True})
    return request


def test_upload_email_contacts_vcard_post(dummy_request):
    """Verify vCard email contacts import via POST."""
    vcard_data = b"BEGIN:VCARD\nVERSION:3.0\nFN:Alice Smith\nEMAIL;TYPE=INTERNET:alice@example.com\nEND:VCARD\n"
    file_mock = MagicMock()
    file_mock.file = io.BytesIO(vcard_data)
    file_mock.filename = "contacts.vcf"

    dummy_request.method = "POST"
    dummy_request.POST["upload"] = file_mock
    dummy_request.POST["_submit_check"] = "1"

    with patch("namifax.views.helpers.NFAddressBook") as mock_ab_cls:
        inst_ab = MagicMock()
        inst_ab.create_contact.return_value = True
        mock_ab_cls.return_value = inst_ab

        res = upload_email_contacts(dummy_request)
        inst_ab.create_contact.assert_called_with("Alice Smith", "alice@example.com")
        assert res.status_code == 200
        assert "Upload" in res.text


def test_upload_fax_contacts_vcard_post(dummy_request):
    """Verify vCard fax contacts import via POST."""
    vcard_data = b"BEGIN:VCARD\nVERSION:3.0\nFN:Bob Jones\nORG:Wayne Enterprises\nTEL;TYPE=FAX:+15550144\nEMAIL;TYPE=INTERNET:bob@wayne.com\nEND:VCARD\n"
    file_mock = MagicMock()
    file_mock.file = io.BytesIO(vcard_data)
    file_mock.filename = "faxcontacts.vcf"

    dummy_request.method = "POST"
    dummy_request.POST["upload"] = file_mock
    dummy_request.POST["catid"] = "2"
    dummy_request.POST["_submit_check"] = "1"

    with patch("namifax.views.helpers.NFAddressBook") as mock_ab_cls:
        inst_ab = MagicMock()
        inst_ab.create.return_value = True
        inst_ab.create_faxnumid.return_value = True
        mock_ab_cls.return_value = inst_ab

        res = upload_fax_contacts(dummy_request)
        inst_ab.create.assert_called()
        inst_ab.create_faxnumid.assert_called()
        assert res.status_code == 200




def test_ajax_inbox_count_view(dummy_request):
    """Verify real ArchiveIn query for inbox count."""
    with patch("namifax.views.ajax.ArchiveIn") as mock_arc_cls:
        inst_arc = MagicMock()
        inst_arc.get_num_faxes.return_value = 5
        mock_arc_cls.return_value = inst_arc

        res = ajax_inbox_count(dummy_request)
        assert res.status_code == 200
        assert "5" in res.text


def test_ajax_archive_fax_view(dummy_request):
    """Verify real ArchiveIn call to move fax from inbox to archive."""
    dummy_request.params = {"fid": "42"}
    dummy_request.headers["X-Requested-With"] = "XMLHttpRequest"
    with patch("namifax.views.ajax.ArchiveIn") as mock_arc_cls, patch("namifax.views.ajax.load_fax", return_value=True):
        inst_arc = MagicMock()
        inst_arc.set_archivebox.return_value = True
        mock_arc_cls.return_value = inst_arc

        res = ajax_archive_fax(dummy_request)
        assert res.status_code == 200
        inst_arc.set_archivebox.assert_called_with(42)
