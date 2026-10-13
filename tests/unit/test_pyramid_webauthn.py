from unittest.mock import MagicMock, patch
import json
import pytest
from pyramid.testing import DummyRequest
from namifax.views.webauthn import (
    webauthn_register_options_view,
    webauthn_auth_options_view,
    webauthn_list_credentials_view,
    webauthn_delete_credential_view,
)

def test_webauthn_register_options_view_unauthenticated():
    req = DummyRequest()
    req.db = MagicMock()
    req.dbsession = MagicMock()
    req.session = {}
    res = webauthn_register_options_view(req)
    assert res.status_code == 401

def test_webauthn_register_options_view_success():
    req = DummyRequest()
    req.db = MagicMock()
    req.dbsession = MagicMock()
    req.session = {"username": "admin"}
    with patch("namifax.views.webauthn.NFUserAccount") as mock_user_cls:
        mock_user = MagicMock()
        mock_user.load_by_username.return_value = True
        mock_user.get_uid.return_value = 1
        mock_user.get_name.return_value = "Admin User"
        mock_user_cls.return_value = mock_user

        with patch("namifax.views.webauthn.WebAuthnService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.generate_registration_options.return_value = {
                "challenge": "sample_challenge_base64",
                "rp": {"name": "NamiFAX"},
            }
            mock_svc_cls.return_value = mock_svc

            res = webauthn_register_options_view(req)
            data = json.loads(res.body)
            assert data["challenge"] == "sample_challenge_base64"
            assert req.session.get("webauthn_reg_challenge") == "sample_challenge_base64"

def test_webauthn_auth_options_view():
    req = DummyRequest()
    req.db = MagicMock()
    req.dbsession = MagicMock()
    req.session = {}
    with patch("namifax.views.webauthn.WebAuthnService") as mock_svc_cls:
        mock_svc = MagicMock()
        mock_svc.generate_authentication_options.return_value = {
            "challenge": "auth_challenge_123",
            "rpId": "localhost",
        }
        mock_svc_cls.return_value = mock_svc

        res = webauthn_auth_options_view(req)
        data = json.loads(res.body)
        assert data["challenge"] == "auth_challenge_123"
        assert req.session.get("webauthn_auth_challenge") == "auth_challenge_123"

def test_webauthn_list_and_delete_credentials_views():
    req = DummyRequest()
    req.db = MagicMock()
    req.dbsession = MagicMock()
    req.session = {"username": "admin"}
    with patch("namifax.views.webauthn.NFUserAccount") as mock_user_cls:
        mock_user = MagicMock()
        mock_user.load_by_username.return_value = True
        mock_user.get_uid.return_value = 1
        mock_user_cls.return_value = mock_user

        with patch("namifax.views.webauthn.WebAuthnService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_cred = MagicMock()
            mock_cred.id = 1
            mock_cred.credential_id = "cred_1"
            mock_cred.device_name = "TouchID"
            mock_cred.created_at = "2026-10-01"
            mock_cred.last_used_at = None
            mock_svc.list_credentials.return_value = [mock_cred]
            mock_svc.delete_credential.return_value = True
            mock_svc_cls.return_value = mock_svc

            res_list = webauthn_list_credentials_view(req)
            data_list = json.loads(res_list.body)
            assert len(data_list) == 1
            assert data_list[0]["device_name"] == "TouchID"

            req.POST = {"credential_db_id": "1"}
            res_del = webauthn_delete_credential_view(req)
            data_del = json.loads(res_del.body)
            assert data_del["success"] is True
