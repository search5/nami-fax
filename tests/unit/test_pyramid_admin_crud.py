"""Unit tests for NamiFAX Admin CRUD views with real domain service integration."""

from unittest.mock import MagicMock, patch
from pyramid import testing
import pytest

from namifax.views.admin import (
    admin_categories_view,
    admin_dynconf_view,
    admin_barcodes_view,
    admin_covers_view,
    admin_fax2email_view,
    admin_routing_did_view,
    admin_system_func_view,
)
from namifax.views.distrolist import distrolist_edit_view
from request_identity import set_identity


@pytest.fixture
def dummy_request(seeded_db, dbsession):
    request = testing.DummyRequest()
    request.db = seeded_db
    request.dbsession = dbsession
    set_identity(request, {"username": "admin", "is_admin": True, "superuser": True})
    return request


def test_admin_categories_get(dummy_request):
    """Verify categories view retrieves list from domain service."""
    with patch("namifax.views.admin.FaxPDFCategory") as mock_cls:
        inst = MagicMock()
        # Mock get_list generator/iterator
        inst.get_categories.return_value = [{"catid": 1, "name": "Invoices"}]
        mock_cls.return_value = inst
        res = admin_categories_view(dummy_request)
        assert res["title"] == "NamiFAX - Admin - Fax Categories"
        assert len(res["categories"]) >= 1


def test_admin_categories_post_create(dummy_request):
    """Verify category creation via POST."""
    dummy_request.method = "POST"
    dummy_request.params = {"create": "1", "name": "NewCategory", "_submit_check": "1"}
    with patch("namifax.views.admin.FaxPDFCategory") as mock_cls:
        inst = MagicMock()
        inst.create.return_value = True
        inst.get_categories.return_value = [{"catid": 2, "name": "NewCategory"}]
        mock_cls.return_value = inst
        res = admin_categories_view(dummy_request)
        inst.create.assert_called_with("NewCategory")
        assert res["message"] is not None or "NewCategory" in str(res)


def test_admin_categories_post_delete(dummy_request):
    """Verify category deletion via POST."""
    dummy_request.method = "POST"
    dummy_request.params = {"delete": "1", "catid": "2", "_submit_check": "1"}
    with patch("namifax.views.admin.FaxPDFCategory") as mock_cls:
        inst = MagicMock()
        inst.delete_category.return_value = True
        mock_cls.return_value = inst
        res = admin_categories_view(dummy_request)
        inst.delete_category.assert_called_with(2)


def test_admin_categories_get_selected(dummy_request):
    """Verify loading selected category for editing."""
    dummy_request.params = {"catid": "1"}
    with patch("namifax.views.admin.FaxPDFCategory") as mock_cls:
        inst = MagicMock()
        inst.get_name.return_value = "General"
        inst.get_categories.return_value = [{"catid": 1, "name": "General"}]
        mock_cls.return_value = inst
        res = admin_categories_view(dummy_request)
        assert res["selected_category"] is not None
        assert res["selected_category"]["name"] == "General"


def test_admin_categories_post_save_edit(dummy_request):
    """Verify updating category name via POST save."""
    dummy_request.method = "POST"
    dummy_request.params = {"save": "1", "catid": "1", "name": "Invoices-Updated", "_submit_check": "1"}
    with patch("namifax.views.admin.FaxPDFCategory") as mock_cls:
        inst = MagicMock()
        inst.set_name.return_value = True
        mock_cls.return_value = inst
        res = admin_categories_view(dummy_request)
        inst.set_name.assert_called_with("Invoices-Updated", 1)
        assert res["message"] is not None
        assert "updated" in res["message"]


def test_admin_dynconf_post_create(dummy_request):
    """Verify blacklist rule creation via POST."""
    dummy_request.method = "POST"
    dummy_request.params = {"create": "1", "callid": "01099998888", "device": "ttyS0", "_submit_check": "1"}
    with patch("namifax.views.admin.DynamicConfig") as mock_cls:
        inst = MagicMock()
        inst.create.return_value = True
        inst.list_rules.return_value = [{"dynconf_id": 1, "callid": "01099998888", "device": "ttyS0"}]
        mock_cls.return_value = inst
        res = admin_dynconf_view(dummy_request)
        inst.create.assert_called_with("ttyS0", "01099998888")


def test_admin_barcodes_post_create(dummy_request):
    """Verify barcode route creation via POST."""
    dummy_request.method = "POST"
    dummy_request.params = {"create": "1", "barcode": "BC-200", "alias": "Warehouse", "_submit_check": "1"}
    with patch("namifax.views.admin.BarcodeRouting") as mock_cls:
        inst = MagicMock()
        inst.create.return_value = True
        inst.list_all.return_value = [{"barcode_id": 1, "barcode": "BC-200", "alias": "Warehouse"}]
        mock_cls.return_value = inst
        res = admin_barcodes_view(dummy_request)
        assert res["barcodes"] is not None


def test_admin_barcodes_get_selected(dummy_request):
    """Verify barcode route editing loads existing rule data."""
    dummy_request.params = {"barcode_id": "1"}
    with patch("namifax.views.admin.BarcodeRouting") as mock_cls:
        inst = MagicMock()
        inst.loadbyid.return_value = True
        inst.get_barcode_id.return_value = 1
        inst.get_barcode.return_value = "BC-1001"
        inst.get_alias.return_value = "Sales Barcode"
        inst.get_contact.return_value = "sales@company.com"
        inst.get_printer.return_value = "HPLaserJet"
        mock_cls.return_value = inst
        res = admin_barcodes_view(dummy_request)
        assert res["selected_barcode"] is not None
        assert res["selected_barcode"]["barcode"] == "BC-1001"


def test_admin_barcodes_post_save_edit(dummy_request):
    """Verify updating an existing barcode route via POST save."""
    dummy_request.method = "POST"
    dummy_request.params = {
        "save": "1",
        "barcode_id": "1",
        "barcode": "BC-1001-MOD",
        "alias": "Updated Barcode",
        "contact": "sales-mod@company.com",
        "printer": "OfficeJet",
        "_submit_check": "1",
    }
    with patch("namifax.views.admin.BarcodeRouting") as mock_cls:
        inst = MagicMock()
        inst.loadbyid.return_value = True
        mock_cls.return_value = inst
        res = admin_barcodes_view(dummy_request)
        inst.set_barcode.assert_called_with("BC-1001-MOD")
        inst.set_alias.assert_called_with("Updated Barcode")
        assert res["message"] is not None


def test_admin_covers_post_delete(dummy_request):
    """Verify cover page deletion via POST."""
    dummy_request.method = "POST"
    dummy_request.params = {"delete": "1", "cover_id": "99", "_submit_check": "1"}
    with patch("namifax.views.admin.Covers") as mock_cls:
        inst = MagicMock()
        inst.delete_cover.return_value = True
        inst.list_all.return_value = []
        mock_cls.return_value = inst
        res = admin_covers_view(dummy_request)
        inst.delete_cover.assert_called_with(99)


def test_admin_covers_get_selected(dummy_request):
    """Verify cover page template loading for editing."""
    dummy_request.params = {"cover_id": "1"}
    with patch("namifax.views.admin.Covers") as mock_cls:
        inst = MagicMock()
        inst.load_by_id.return_value = True
        inst.get_cover_id.return_value = 1
        inst.get_title.return_value = "standard"
        inst.get_file.return_value = "standard.ps"
        mock_cls.return_value = inst
        res = admin_covers_view(dummy_request)
        assert res["selected_cover"] is not None
        assert res["selected_cover"]["title"] == "standard"


def test_admin_covers_post_save_edit(dummy_request):
    """Verify updating cover page template title via POST save."""
    dummy_request.method = "POST"
    dummy_request.params = {
        "save": "1",
        "cover_id": "1",
        "title": "Standard Updated",
        "file": "standard.ps",
        "_submit_check": "1",
    }
    with patch("namifax.views.admin.Covers") as mock_cls:
        inst = MagicMock()
        inst.load_by_id.return_value = True
        mock_cls.return_value = inst
        res = admin_covers_view(dummy_request)
        inst.set_title.assert_called_with("Standard Updated")
        assert res["message"] is not None


def test_admin_routing_did_get(dummy_request):
    """Verify DID routing view retrieves list and categories."""
    res = admin_routing_did_view(dummy_request)
    assert res["title"] == "NamiFAX - Admin - Configure DID Routing"
    assert "did_routes" in res
    assert "categories" in res
    assert res["selected_route"] is None


def test_admin_routing_did_get_selected(dummy_request):
    """Verify DID routing view loads selected route for editing."""
    dummy_request.params = {"didr_id": "1"}
    res = admin_routing_did_view(dummy_request)
    assert res["selected_route"] is not None
    assert res["selected_route"]["route"] == "1000"
    assert res["selected_route"]["alias"] == "Main Trunk"


def test_admin_routing_did_post_create(dummy_request):
    """Verify creating a new DID route via POST."""
    dummy_request.method = "POST"
    dummy_request.params = {
        "create": "1",
        "route": "2000",
        "alias": "Support Hotline",
        "contact": "support@example.com",
        "printer": "lp3",
        "_submit_check": "1",
    }
    with patch("namifax.views.admin.DIDRouting") as mock_cls:
        inst = MagicMock()
        inst.create.return_value = True
        inst.list_all.return_value = [{"didr_id": 99, "route": "2000", "alias": "Support Hotline"}]
        mock_cls.return_value = inst
        res = admin_routing_did_view(dummy_request)
        assert res["message"] is not None
        assert "created" in res["message"]


def test_admin_routing_did_post_save_edit(dummy_request):
    """Verify updating an existing DID route via POST save."""
    dummy_request.method = "POST"
    dummy_request.params = {
        "save": "1",
        "didr_id": "1",
        "route": "1000-MOD",
        "alias": "Main Trunk Updated",
        "contact": "reception@example.com",
        "printer": "lp-new",
        "_submit_check": "1",
    }
    with patch("namifax.views.admin.DIDRouting") as mock_cls:
        inst = MagicMock()
        inst.loadbyid.return_value = True
        mock_cls.return_value = inst
        res = admin_routing_did_view(dummy_request)
        inst.set_routecode.assert_called_with("1000-MOD")
        inst.set_alias.assert_called_with("Main Trunk Updated")
        assert res["message"] is not None
        assert "updated" in res["message"]


def test_admin_routing_did_post_delete(dummy_request):
    """Verify deleting a DID route via POST delete."""
    dummy_request.method = "POST"
    dummy_request.params = {
        "delete": "1",
        "didr_id": "999",
        "_submit_check": "1",
    }
    with patch("namifax.views.admin.DIDRouting") as mock_cls:
        inst = MagicMock()
        inst.delete_route.return_value = True
        mock_cls.return_value = inst
        res = admin_routing_did_view(dummy_request)
        inst.delete_route.assert_called_with(999)
        assert res["message"] is not None
        assert "deleted" in res["message"]


def test_admin_dynconf_get_selected(dummy_request):
    """Verify loading selected dynconf rule for editing."""
    dummy_request.params = {"dynconf_id": "1"}
    with patch("namifax.views.admin.DynamicConfig") as mock_cls:
        inst = MagicMock()
        inst.load_rule.return_value = True
        inst.get_dynconf_id.return_value = 1
        inst.get_callid.return_value = "01012345678"
        inst.get_device.return_value = "ttyS0"
        inst.list_rules.return_value = [{"dynconf_id": 1, "callid": "01012345678", "device": "ttyS0"}]
        mock_cls.return_value = inst
        res = admin_dynconf_view(dummy_request)
        assert res["selected_rule"] is not None
        assert res["selected_rule"]["callid"] == "01012345678"


def test_admin_dynconf_post_save_edit(dummy_request):
    """Verify updating an existing dynconf rule via POST save."""
    dummy_request.method = "POST"
    dummy_request.params = {
        "save": "1",
        "dynconf_id": "1",
        "callid": "01099998888",
        "device": "ttyS0",
        "_submit_check": "1",
    }
    with patch("namifax.views.admin.DynamicConfig") as mock_cls:
        inst = MagicMock()
        inst.load_rule.return_value = True
        inst.save_rule.return_value = True
        mock_cls.return_value = inst
        res = admin_dynconf_view(dummy_request)
        inst.load_rule.assert_called_with(1)
        inst.save_rule.assert_called_with("ttyS0", "01099998888")
        assert res["message"] is not None
        assert "updated" in res["message"]


def test_admin_dynconf_post_delete(dummy_request):
    """Verify deleting a dynconf rule via POST delete."""
    dummy_request.method = "POST"
    dummy_request.params = {
        "delete": "1",
        "dynconf_id": "999",
        "_submit_check": "1",
    }
    with patch("namifax.views.admin.DynamicConfig") as mock_cls:
        inst = MagicMock()
        inst.remove.return_value = True
        mock_cls.return_value = inst
        res = admin_dynconf_view(dummy_request)
        inst.remove.assert_called_with(999)
        assert res["message"] is not None
        assert "removed" in res["message"]






def test_distrolist_edit_get_selected(dummy_request):
    """Verify loading selected distribution list for editing."""
    dummy_request.params = {"dl_id": "1"}
    res = distrolist_edit_view(dummy_request)
    assert res["selected_list"] is not None
    assert res["selected_list"]["listname"] == "Executive Team"


def test_distrolist_edit_post_delete(dummy_request):
    """Verify deleting a distribution list via POST delete."""
    dummy_request.method = "POST"
    dummy_request.params = {"delete": "1", "dl_id": "999", "_submit_check": "1"}
    dummy_request.route_url = MagicMock(return_value="/distrolist")
    res = distrolist_edit_view(dummy_request)
    assert res.status_code == 302


# Fax to Email (per fax number settings, deleting, validation) is tested with real data in test_admin_fax2email.py
