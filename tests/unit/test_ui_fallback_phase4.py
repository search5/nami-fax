"""Unit tests for Phase 4 UI and View fallback removal (AUDIT-08, AUDIT-09, AUDIT-12, AUDIT-14)."""

import unittest
from unittest.mock import MagicMock, patch
from pyramid import testing

from namifax.views.sendfax import sendfax_view
from namifax.views.inbox import inbox_view, viewfax_view
from namifax.views.admin import get_all_admin_modems
from namifax.views.addressbook import addressbook_edit_view
from namifax.views.distrolist import distrolist_edit_view
from namifax.views.helpers import upload_fax_contacts


class MockRequest(testing.DummyRequest):
    """Custom DummyRequest supporting writable identity property."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._mock_identity = None
        self.db = MagicMock()
        self.dbsession = MagicMock()

    @property
    def identity(self):
        return self._mock_identity

    @identity.setter
    def identity(self, val):
        self._mock_identity = val


class TestUIFallbackPhase4(unittest.TestCase):
    """Test suite covering Phase 4 fixes for AUDIT-08, AUDIT-09, AUDIT-12, and AUDIT-14."""

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    # =========================================================================
    # AUDIT-08: sendfax_view cover page fallback removal
    # =========================================================================
    @patch("namifax.views.sendfax.Covers")
    def test_sendfax_view_no_covers_returns_empty_list(self, mock_covers_cls):
        """Verify that when no covers are in DB, empty list is returned instead of hardcoded fallbacks."""
        mock_inst = MagicMock()
        mock_inst.get_covers.return_value = None
        mock_covers_cls.return_value = mock_inst

        req = MockRequest()
        req.identity = {"username": "admin", "is_admin": True}

        with patch("namifax.views.sendfax.NFUserAccount"), patch("namifax.views.sendfax.FaxModem"):
            res = sendfax_view(req)
        self.assertIsInstance(res, dict)
        self.assertEqual(res.get("cover_list"), [])
        self.assertEqual(res.get("default_cover"), "")

    # =========================================================================
    # AUDIT-09: inbox and viewfax fallback removal
    # =========================================================================
    @patch("namifax.views.inbox.ArchiveIn")
    @patch("namifax.views.inbox.NFAddressBook")
    def test_inbox_view_empty_fields_not_injected_with_fake_defaults(self, mock_ab_cls, mock_arc_cls):
        """Verify that missing DB fields do not receive fake Acme Corp or ttyS0 defaults in inbox."""
        mock_arc = MagicMock()
        mock_arc.list_inbox.return_value = [
            {
                "fid": 10,
                "company": None,
                "origfaxnum": None,
                "archstamp": None,
                "modemdev": None,
                "pages": None,
                "description": None,
            }
        ]
        mock_arc.get_num_faxes.return_value = 1
        mock_arc_cls.return_value = mock_arc

        mock_ab = MagicMock()
        mock_ab.loadbycid.return_value = False
        mock_ab.loadbyfaxnumid.return_value = False
        mock_ab_cls.return_value = mock_ab

        req = MockRequest()
        req.db = MagicMock()
        req.identity = {"username": "admin", "is_admin": True}

        res = inbox_view(req)
        faxes = res.get("faxes", [])
        self.assertEqual(len(faxes), 1)
        fax = faxes[0]

        self.assertEqual(fax.get("company"), "")
        self.assertEqual(fax.get("archstamp"), "")
        self.assertEqual(fax.get("modemdev"), "")
        self.assertEqual(fax.get("description"), "")
        self.assertNotEqual(fax.get("company"), "Acme Corp")
        self.assertNotEqual(fax.get("archstamp"), "2026-09-29 10:00:00")
        self.assertNotEqual(fax.get("modemdev"), "ttyS0")
        self.assertNotEqual(fax.get("description"), "Received Facsimile")

    @patch("namifax.views.inbox.ArchiveIn")
    @patch("namifax.views.inbox.NFAddressBook")
    def test_viewfax_view_nonexistent_goes_back_to_the_inbox(self, mock_ab_cls, mock_arc_cls):
        """A fax that cannot be loaded gives no made-up metadata: the visitor is sent back to the inbox."""
        mock_arc = MagicMock()
        mock_arc.load_fax.return_value = False
        mock_arc_cls.return_value = mock_arc

        req = MockRequest()
        req.params = {"fid": "999"}
        req.identity = {"username": "admin", "is_admin": True}
        req.route_url = MagicMock(return_value="/inbox")

        res = viewfax_view(req)
        self.assertEqual(res.status_code, 302)

    def test_viewfax_template_renders_hyphen_when_metadata_missing(self):
        """Verify viewfax.jinja2 renders '-' placeholder instead of Acme Global or hardcoded timestamps."""
        self.config.include("pyramid_jinja2")
        self.config.add_jinja2_renderer(".jinja2")
        self.config.add_jinja2_search_path("namifax:templates")

        from pyramid.renderers import render

        context = {
            "title": "NamiFAX - View Fax",
            "current_user": {"username": "admin", "is_admin": True},
            "fid": "999",
            "pages": 1,
            "archstamp": "",
            "modemdev": "",
            "company": "",
            "_": lambda msg: msg,
        }

        html = render("namifax:templates/viewfax.jinja2", context, request=testing.DummyRequest())
        self.assertNotIn("Acme Global (+1-555-0100)", html)
        self.assertNotIn("Acme Global Corp", html)
        self.assertNotIn("2026-09-29 10:00:00", html)
        self.assertIn("-", html)

    # =========================================================================
    # AUDIT-12: FaxModem.get_status dynamic reflection in admin dashboard
    # =========================================================================
    @patch("namifax.services.modem.FaxModem")
    def test_admin_modems_dynamically_calls_get_status(self, mock_modem_cls):
        """Verify that get_all_admin_modems queries FaxModem.get_status() instead of static 'Running and idle'."""
        mock_svc = MagicMock()
        mock_svc.list_all.return_value = [
            {"devid": 1, "device": "ttyS1", "alias": "Modem 1", "contact": "", "printer": "", "faxcatid": None}
        ]
        mock_svc.get_status.return_value = {"status": "Sending fax to 555-1234", "class": "modem-busy"}
        mock_modem_cls.return_value = mock_svc

        modems = get_all_admin_modems()
        self.assertEqual(len(modems), 1)
        self.assertEqual(modems[0]["status"], "Sending fax to 555-1234")
        self.assertNotEqual(modems[0]["status"], "Running and idle")
        mock_svc.load_device.assert_called_with("ttyS1")
        mock_svc.get_status.assert_called()

    # =========================================================================
    # AUDIT-14: Address book and distro list ID 1 fallback removal & helpers
    # =========================================================================
    @patch("namifax.views.addressbook.get_all_companies")
    def test_addressbook_view_missing_id_1_does_not_fallback_to_first_company(self, mock_get_comps):
        """Verify that requesting company_id=1 when id 1 does not exist does not fallback to companies[0]."""
        mock_get_comps.return_value = [
            {"id": 2, "company_id": 2, "company": "Other Corp", "faxnumber": "555-9999"}
        ]

        req = MockRequest()
        req.params = {"company_id": "1"}
        req.identity = {"username": "admin", "is_admin": True}

        res = addressbook_edit_view(req)
        # Should return blank company dict, NOT Other Corp
        self.assertEqual(res.get("company", {}).get("company"), "")
        self.assertNotEqual(res.get("company", {}).get("company"), "Other Corp")

    @patch("namifax.views.distrolist.get_all_distrolists")
    def test_distrolist_view_missing_id_1_does_not_fallback_to_first_distrolist(self, mock_get_dl):
        """Verify that requesting dl_id=1 when id 1 does not exist does not fallback to distrolists[0]."""
        mock_get_dl.return_value = [
            {"dl_id": 2, "listname": "Marketing Team", "listdata": "555-1111"}
        ]

        req = MockRequest()
        req.params = {"dl_id": "1"}
        req.identity = {"username": "admin", "is_admin": True}

        res = distrolist_edit_view(req)
        self.assertIsNone(res.get("selected_list"))

    @patch("namifax.views.helpers.FaxPDFCategory")
    def test_helpers_upload_faxcontacts_queries_categories_dynamically(self, mock_cat_cls):
        """Verify upload_fax_contacts queries FaxPDFCategory dynamically instead of hardcoded General/Confidential."""
        mock_cat = MagicMock()
        mock_cat.get_categories.return_value = [
            {"catid": 10, "name": "Dynamic Sales"},
            {"catid": 20, "name": "Dynamic Support"},
        ]
        mock_cat_cls.return_value = mock_cat

        req = MockRequest()
        res = upload_fax_contacts(req)
        html = res.text
        self.assertIn("Dynamic Sales", html)
        self.assertIn("Dynamic Support", html)
        self.assertIn('value="10"', html)
        self.assertIn('value="20"', html)
