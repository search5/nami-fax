"""Pyramid Web Integration Test for Address Book Views (W14, W15)."""

import pytest
from webtest import TestApp

from namifax import create_app


@pytest.fixture
def authenticated_app():
    """Create Pyramid test application fixture logged in as admin."""
    wsgi_app = create_app({})
    client = TestApp(wsgi_app)
    client.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return client


def test_addressbook_list(authenticated_app):
    """Verify address book list (W14) renders table and + New Company link."""
    res = authenticated_app.get("/addressbook", status=200)
    assert res.status_code == 200
    assert "Address Book" in res.text
    assert "+ New Company" in res.text
    assert "/addressbook/edit" in res.text


def test_addressbook_edit_get_and_post(authenticated_app):
    """Verify address book edit GET (W15) and POST form submission."""
    res = authenticated_app.get("/addressbook/edit", status=200)
    assert res.status_code == 200
    assert "Company Name" in res.text
    assert "Fax Number" in res.text
    assert 'name="new_to_address"' in res.text           # every fax number carries its contact and address details

    # Post new company
    post_res = authenticated_app.post(
        "/addressbook/edit",
        {"company": "Test Enterprise", "faxnumber": "555-9999", "email": "test@enterprise.com", "_submit_check": "1"},
        status=302,
    )
    assert post_res.status_code == 302
    assert "/addressbook" in post_res.headers["Location"]


def test_addressbook_edit_selected_and_delete(authenticated_app):
    """Verify loading existing company (W65) and delete POST."""
    res = authenticated_app.get("/addressbook/edit?company_id=1", status=200)
    assert res.status_code == 200
    assert "Company" in res.text
    assert "Save" in res.text
    assert "Delete" in res.text

    del_res = authenticated_app.post(
        "/addressbook/edit",
        {"delete": "1", "company_id": "999", "_submit_check": "1"},
        status=302,
    )
    assert del_res.status_code == 302
    assert "/addressbook" in del_res.headers["Location"]


def test_emailbook_edit_selected_and_delete(authenticated_app):
    """Verify loading existing email contact (W67) and delete POST."""
    res = authenticated_app.get("/emailbook/edit?email_id=1", status=200)
    assert res.status_code == 200
    assert "Email Book" in res.text
    assert "Save" in res.text
    assert "Delete" in res.text

    del_res = authenticated_app.post(
        "/emailbook/edit",
        {"delete": "1", "email_id": "999", "_submit_check": "1"},
        status=302,
    )
    assert del_res.status_code == 302
    assert "/emailbook" in del_res.headers["Location"]

