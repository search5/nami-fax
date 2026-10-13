"""SAML sign-in is configured from the admin page and only accepts responses the identity provider signed.

Before: the sign-in code ignored the saved settings (the button went back to the login page without a word) and the ACS accepted any
unsigned XML naming an account, so anybody could sign in as anybody."""

from __future__ import annotations

import base64
import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import webtest
from bs4 import BeautifulSoup
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lxml import etree
from signxml import XMLSigner, methods

from namifax.services.saml import SAMLService
from namifax.services.system_config import SystemConfigService
from namifax.services.user_account import NFUserAccount

SSO = "https://idp.example.com/sso"
NS_P, NS_A = "urn:oasis:names:tc:SAML:2.0:protocol", "urn:oasis:names:tc:SAML:2.0:assertion"


def _key_and_cert(name="idp"):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=30)).sign(key, hashes.SHA256()))
    return key, cert.public_bytes(serialization.Encoding.PEM).decode()


@pytest.fixture(scope="module")
def idp():
    return _key_and_cert("idp")


@pytest.fixture
def configured(dbsession, idp):
    cfg = SystemConfigService(dbsession)
    for key, value in (("saml_enabled", "1"), ("saml_idp_sso_url", SSO), ("saml_idp_entity_id", "https://idp.example.com"),
                       ("saml_idp_x509_cert", idp[1]), ("saml_jit_provisioning", "0")):
        cfg.set(key, value)
    dbsession.flush()
    return cfg


@pytest.fixture
def person(dbsession):
    svc = NFUserAccount(db=dbsession)
    assert svc.create({"username": "ssouser", "password": "Secret123!", "email": "sso@corp.test", "name": "Sso", "acc_enabled": 1,
                       "last_login": "2026-01-01 10:00:00"})
    dbsession.flush()


@pytest.fixture
def client(testapp):
    return webtest.TestApp(testapp.app, extra_environ=testapp.extra_environ)


def _start(client):
    """Begin sign-in at the application; returns the AuthnRequest ID the IdP would answer."""
    res = client.get("/auth/saml/login")
    assert res.status_int == 302 and res.headers["Location"].startswith(SSO)
    from urllib.parse import parse_qs, urlparse
    import zlib

    request = parse_qs(urlparse(res.headers["Location"]).query)["SAMLRequest"][0]
    xml = zlib.decompress(base64.b64decode(request), -15)
    return re.search(rb'ID="([^"]+)"', xml).group(1).decode()


def _response(idp_key_cert, *, in_response_to, email="sso@corp.test", audience="http://example.com/auth/saml/metadata",
              recipient="http://example.com/auth/saml/acs", not_after=None, not_before=None, sign=True, tamper=False, attributes=None,
              issuer="https://idp.example.com"):
    key, cert = idp_key_cert
    now = datetime.now(timezone.utc)
    fmt = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")                                    # noqa: E731
    not_after = not_after or now + timedelta(minutes=5)
    not_before = not_before or now - timedelta(minutes=1)
    aid = f"_{uuid.uuid4().hex}"
    extra = "".join(f'<saml:Attribute Name="{name}">' + "".join(f"<saml:AttributeValue>{v}</saml:AttributeValue>" for v in values) + "</saml:Attribute>"
                    for name, values in (attributes or {}).items())
    xml = f"""<samlp:Response xmlns:samlp="{NS_P}" xmlns:saml="{NS_A}" ID="_{uuid.uuid4().hex}" Version="2.0" IssueInstant="{fmt(now)}"
       Destination="{recipient}" InResponseTo="{in_response_to}">
  <saml:Issuer>{issuer}</saml:Issuer>
  <samlp:Status><samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/></samlp:Status>
  <saml:Assertion ID="{aid}" Version="2.0" IssueInstant="{fmt(now)}">
    <saml:Issuer>{issuer}</saml:Issuer>
    <saml:Subject><saml:NameID>{email}</saml:NameID>
      <saml:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">
        <saml:SubjectConfirmationData InResponseTo="{in_response_to}" Recipient="{recipient}" NotOnOrAfter="{fmt(not_after)}"/>
      </saml:SubjectConfirmation></saml:Subject>
    <saml:Conditions NotBefore="{fmt(not_before)}" NotOnOrAfter="{fmt(not_after)}">
      <saml:AudienceRestriction><saml:Audience>{audience}</saml:Audience></saml:AudienceRestriction></saml:Conditions>
    <saml:AttributeStatement><saml:Attribute Name="email"><saml:AttributeValue>{email}</saml:AttributeValue></saml:Attribute>{extra}</saml:AttributeStatement>
  </saml:Assertion>
</samlp:Response>"""
    root = etree.fromstring(xml.encode())
    if sign:
        assertion = root.find(f"{{{NS_A}}}Assertion")
        signed = XMLSigner(method=methods.enveloped, signature_algorithm="rsa-sha256", digest_algorithm="sha256",
                           c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#").sign(
            assertion, key=key, cert=cert, reference_uri=aid)
        root.replace(assertion, signed)
    data = etree.tostring(root)
    if tamper:
        data = data.replace(email.encode(), b"admin@corp.test", 1)
    return base64.b64encode(data).decode()


def _post(client, saml_response, relay="/inbox"):
    return client.post("/auth/saml/acs", {"SAMLResponse": saml_response, "RelayState": relay}, expect_errors=True)


def _signed_in(client):
    return client.get("/inbox", expect_errors=True).status_int == 200


# --- the button and the login address -----------------------------------------------------------------------------------------

def test_the_button_is_hidden_until_saml_is_set_up(client):
    assert BeautifulSoup(client.get("/login").text, "html.parser").find("a", href="/auth/saml/login") is None


def test_the_button_shows_when_saml_is_enabled_and_has_an_idp(client, configured):
    assert BeautifulSoup(client.get("/login").text, "html.parser").find("a", href="/auth/saml/login") is not None


def test_the_login_address_says_so_when_saml_is_not_set_up(client):
    res = client.get("/auth/saml/login")
    assert res.status_int == 302 and res.headers["Location"].endswith("/login")
    assert "not set up" in res.follow().text


def test_a_disabled_saml_does_not_redirect_even_with_an_idp(client, configured):
    configured.set("saml_enabled", "0")
    res = client.get("/auth/saml/login")
    assert res.headers["Location"].endswith("/login")


def test_the_request_carries_the_saved_idp_and_our_addresses(client, configured):
    res = client.get("/auth/saml/login")
    assert res.headers["Location"].startswith(SSO + "?SAMLRequest=")


# --- what the ACS accepts -----------------------------------------------------------------------------------------------------

def test_a_correctly_signed_response_signs_the_person_in(client, configured, person, idp):
    request_id = _start(client)
    res = _post(client, _response(idp, in_response_to=request_id))
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox") and _signed_in(client)


def test_an_unsigned_response_is_refused(client, configured, person, idp):
    request_id = _start(client)
    res = _post(client, _response(idp, in_response_to=request_id, sign=False))
    assert "/login" in res.headers["Location"] and not _signed_in(client)


def test_a_forged_response_is_refused_when_saml_is_off(client, person, idp):
    res = _post(client, _response(idp, in_response_to="_x", sign=False))
    assert "/login" in res.headers["Location"] and not _signed_in(client)


def test_a_response_signed_by_somebody_else_is_refused(client, configured, person):
    request_id = _start(client)
    res = _post(client, _response(_key_and_cert("attacker"), in_response_to=request_id))
    assert "/login" in res.headers["Location"] and not _signed_in(client)


def test_changing_the_signed_assertion_breaks_the_signature(client, configured, person, idp):
    request_id = _start(client)
    res = _post(client, _response(idp, in_response_to=request_id, tamper=True))
    assert "/login" in res.headers["Location"] and not _signed_in(client)


@pytest.mark.parametrize("override", [
    {"not_after": datetime.now(timezone.utc) - timedelta(minutes=10), "not_before": datetime.now(timezone.utc) - timedelta(minutes=20)},
    {"not_before": datetime.now(timezone.utc) + timedelta(hours=1), "not_after": datetime.now(timezone.utc) + timedelta(hours=2)},
    {"audience": "https://other-service.example.com/"},
    {"recipient": "https://evil.example.com/auth/saml/acs"},
])
def test_a_response_for_another_time_audience_or_address_is_refused(client, configured, person, idp, override):
    request_id = _start(client)
    res = _post(client, _response(idp, in_response_to=request_id, **override))
    assert "/login" in res.headers["Location"] and not _signed_in(client)


def test_a_response_from_another_issuer_is_refused_even_if_the_signature_is_good(client, configured, person, idp):
    request_id = _start(client)
    res = _post(client, _response(idp, in_response_to=request_id, issuer="https://other-idp.example.net"))
    assert "/login" in res.headers["Location"] and not _signed_in(client)


def test_the_configured_issuer_is_accepted(client, configured, person, idp):
    request_id = _start(client)
    _post(client, _response(idp, in_response_to=request_id))
    assert _signed_in(client)


def test_without_a_configured_issuer_the_check_is_skipped_with_a_warning(client, configured, person, idp, caplog):
    configured.set("saml_idp_entity_id", "")
    request_id = _start(client)
    with caplog.at_level("WARNING", logger="namifax"):
        _post(client, _response(idp, in_response_to=request_id, issuer="https://whoever.example"))
    assert _signed_in(client)
    assert "Issuer of the response is not checked" in caplog.text


def test_an_answer_to_another_request_is_refused(client, configured, person, idp):
    _start(client)
    res = _post(client, _response(idp, in_response_to="_somebody_elses_request"))
    assert "/login" in res.headers["Location"] and not _signed_in(client)


def test_a_response_without_a_started_sign_in_is_refused(client, configured, person, idp):
    res = _post(client, _response(idp, in_response_to="_unsolicited"))
    assert "/login" in res.headers["Location"] and not _signed_in(client)


def test_the_same_response_cannot_be_used_twice(client, configured, person, idp, testapp):
    request_id = _start(client)
    answer = _response(idp, in_response_to=request_id)
    assert _post(client, answer).headers["Location"].endswith("/inbox")
    second = webtest.TestApp(testapp.app, extra_environ=testapp.extra_environ)
    assert second.get("/auth/saml/login").status_int == 302                  # (a fresh browser, same captured answer)
    res = _post(second, answer)
    assert "/login" in res.headers["Location"] and not _signed_in(second)


def test_an_unknown_person_is_refused_without_provisioning(client, configured, idp):
    request_id = _start(client)
    res = _post(client, _response(idp, in_response_to=request_id, email="stranger@corp.test"))
    assert "/login" in res.headers["Location"] and not _signed_in(client)


def test_xml_with_an_entity_bomb_is_refused(client, configured, person):
    request_id = _start(client)
    bomb = (b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]><r>&b;&b;&b;</r>')
    res = _post(client, base64.b64encode(bomb).decode())
    assert "/login" in res.headers["Location"] and not _signed_in(client)


def test_the_relay_state_stays_on_this_site(client, configured, person, idp):
    request_id = _start(client)
    res = _post(client, _response(idp, in_response_to=request_id), relay="https://evil.example.com/")
    assert res.headers["Location"].endswith("/inbox")


def test_an_answer_with_no_response_goes_back_to_the_login_page_with_a_message(client, configured):
    res = client.post("/auth/saml/acs", {}, expect_errors=True)
    assert res.status_int == 302 and "no answer" in res.follow().text.lower()


def test_a_refused_answer_is_explained_on_the_login_page(client, configured, person, idp):
    request_id = _start(client)
    res = _post(client, _response(idp, in_response_to=request_id, sign=False))
    assert "could not be accepted" in res.follow().text
