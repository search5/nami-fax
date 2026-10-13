import base64
import zlib
from unittest.mock import MagicMock, patch
import pytest

from namifax.services.saml import SAMLService, SAMLSettings

SAMPLE_SAML_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                ID="_response_123" Version="2.0" IssueInstant="2026-10-01T00:00:00Z">
    <samlp:Status>
        <samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/>
    </samlp:Status>
    <saml:Assertion ID="_assertion_123" Version="2.0" IssueInstant="2026-10-01T00:00:00Z">
        <saml:Subject>
            <saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">john.doe@enterprise.com</saml:NameID>
        </saml:Subject>
        <saml:AttributeStatement>
            <saml:Attribute Name="email">
                <saml:AttributeValue>john.doe@enterprise.com</saml:AttributeValue>
            </saml:Attribute>
            <saml:Attribute Name="displayName">
                <saml:AttributeValue>John Doe</saml:AttributeValue>
            </saml:Attribute>
        </saml:AttributeStatement>
    </saml:Assertion>
</samlp:Response>
"""

def test_saml_service_init():
    settings = SAMLSettings(
        enabled=True,
        idp_entity_id="https://idp.example.com/entity",
        idp_sso_url="https://idp.example.com/sso",
        sp_entity_id="https://fax.example.com/auth/saml/metadata",
        sp_acs_url="https://fax.example.com/auth/saml/acs",
    )
    svc = SAMLService(settings)
    assert svc.settings.enabled is True
    assert svc.settings.idp_entity_id == "https://idp.example.com/entity"

def test_generate_sp_metadata():
    settings = SAMLSettings(
        enabled=True,
        sp_entity_id="https://fax.example.com/auth/saml/metadata",
        sp_acs_url="https://fax.example.com/auth/saml/acs",
        sp_sls_url="https://fax.example.com/auth/saml/sls",
    )
    svc = SAMLService(settings)
    metadata = svc.generate_sp_metadata()
    assert "EntityDescriptor" in metadata
    assert "https://fax.example.com/auth/saml/metadata" in metadata
    assert "https://fax.example.com/auth/saml/acs" in metadata
    assert "AssertionConsumerService" in metadata

def test_create_authn_request():
    settings = SAMLSettings(
        enabled=True,
        idp_sso_url="https://idp.example.com/sso",
        sp_entity_id="https://fax.example.com/auth/saml/metadata",
        sp_acs_url="https://fax.example.com/auth/saml/acs",
    )
    svc = SAMLService(settings)
    result = svc.create_authn_request(relay_state="/inbox")
    assert "saml_request" in result
    assert "redirect_url" in result
    assert result["relay_state"] == "/inbox"
    assert "https://idp.example.com/sso" in result["redirect_url"]

    # Decode and decompress check
    compressed = base64.b64decode(result["saml_request"])
    xml_str = zlib.decompress(compressed, -15).decode("utf-8")
    assert "AuthnRequest" in xml_str
    assert "https://fax.example.com/auth/saml/acs" in xml_str

def test_an_unsigned_response_is_not_believed():
    """The sample names john.doe but nobody signed it: the signed, verified cases are in test_saml_security.py."""
    svc = SAMLService(SAMLSettings(enabled=True, idp_x509_cert="-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----"))
    b64_response = base64.b64encode(SAMPLE_SAML_RESPONSE.encode("utf-8")).decode("ascii")
    parsed = svc.process_saml_response(b64_response, expected_request_id="_req")
    assert parsed["success"] is False and "name_id" not in parsed


# provisioning (match by email, free username, no JIT) is tested with real accounts in test_sso_and_2fa_login.py
