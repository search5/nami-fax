"""Spec 48 loop 3: services receive their DatabaseEngine; no implicit unconnected engine."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session
from pyramid import testing

from sqlsession import bare_session, empty_session, seeded_session
from namifax.services.cover_studio import CoverStudioService
from namifax.services.ocr import OcrService
from namifax.services.saml import SAMLService
from namifax.services.storage_lifecycle import StorageLifecycleService
from namifax.services.totp import TotpService
from namifax.services.webauthn import WebAuthnService

SERVICES = [
    StorageLifecycleService,
    CoverStudioService,
    TotpService,
    SAMLService,
    WebAuthnService,
]


@pytest.fixture
def db():
    engine = bare_session()
    return engine


@pytest.mark.parametrize("cls", SERVICES, ids=lambda c: c.__name__)
def test_service_uses_injected_db(cls, db):
    svc = cls(db=db)
    assert svc.db is db


@pytest.mark.parametrize("cls", SERVICES, ids=lambda c: c.__name__)
def test_service_without_db_fails_loudly_on_first_use(cls):
    svc = cls()
    assert not isinstance(svc.db, Session)
    with pytest.raises(RuntimeError, match="database"):
        svc.db.query("SELECT 1")


def test_ocr_text_helpers_do_not_need_a_database():
    # OCR 추출 경로는 DB 없이도 동작해야 한다 (helpers.ocr_faxcontent 호환)
    svc = OcrService()
    assert svc.extract_text_from_image("/nonexistent.png") == ""


# --- view factories pass request.db -------------------------------------------

def test_saml_view_factory_passes_request_dbsession(db):
    from namifax.views.saml import _get_saml_service

    req = testing.DummyRequest()
    req.db = db
    req.dbsession = object()
    from unittest.mock import patch

    from namifax.services.saml import SAMLSettings

    with patch("namifax.views.saml.saml_settings", return_value=SAMLSettings()):
        assert _get_saml_service(req).db is req.dbsession


def test_webauthn_view_factory_passes_request_dbsession(db):
    from namifax.views.webauthn import _get_webauthn_service

    req = testing.DummyRequest()
    req.db = db
    req.dbsession = object()
    assert _get_webauthn_service(req).db is req.dbsession
