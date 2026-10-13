"""Unit tests for popup helper views and vCard upload views."""

from unittest.mock import MagicMock
from pyramid import testing
import pytest

from namifax.views.helpers import (
    upload_email_contacts,
    upload_fax_contacts,
)


@pytest.fixture
def dummy_request(seeded_db, dbsession):
    request = testing.DummyRequest()
    request.db = seeded_db
    request.dbsession = dbsession
    request.session = {"user_id": 1, "username": "admin", "is_admin": True, "superuser": True}
    return request










def test_upload_email_contacts_get(dummy_request):
    """Verify GET renders vCard email contact upload form."""
    res = upload_email_contacts(dummy_request)
    assert res.status_code == 200
    assert "Upload Email Contacts" in res.text
    assert 'type="file"' in res.text
    assert 'name="upload"' in res.text


def test_upload_fax_contacts_get(dummy_request):
    """Verify GET renders vCard fax contact upload form with categories."""
    res = upload_fax_contacts(dummy_request)
    assert res.status_code == 200
    assert "Upload Fax Contacts" in res.text
    assert 'type="file"' in res.text
    assert 'name="catid"' in res.text


@pytest.mark.parametrize("path,title", [("/helper/distrocontacts", "Distribution Contacts"), ("/helper/faxcontacts", "Fax Contacts"),
                                         ("/helper/emailcontacts", "Email Contacts")])
def test_the_contact_pickers_render(testapp, path, title):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    res = testapp.get(path)
    assert res.status_int == 200 and title in res.text and 'name="regexp"' in res.text
