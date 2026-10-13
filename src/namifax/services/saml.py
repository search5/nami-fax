from __future__ import annotations

import base64
import logging
import re
import os
import urllib.parse
import uuid
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import threading
import time as _time

_USED: dict[str, float] = {}
_USED_LOCK = threading.Lock()


def _seen_before(assertion_id: str, not_after: float) -> bool:
    """Remember an assertion ID until it expires; True if it was already used (a replay)."""
    now = _time.time()
    with _USED_LOCK:
        for key in [k for k, until in _USED.items() if until < now]:
            del _USED[key]
        if assertion_id in _USED:
            return True
        _USED[assertion_id] = (not_after or now) + 300
        return False

from namifax.db.missing import resolve_db
from namifax.services.user_account import NFUserAccount

@dataclass
class SAMLSettings:
    enabled: bool = False
    idp_entity_id: str = ""
    idp_sso_url: str = ""
    idp_x509_cert: str = ""
    sp_entity_id: str = "http://localhost:8000/auth/saml/metadata"
    sp_acs_url: str = "http://localhost:8000/auth/saml/acs"
    sp_sls_url: str = "http://localhost:8000/auth/saml/sls"
    jit_provisioning: bool = True
    default_role: str = "user"
    # roles and attributes of the identity provider that become the account's settings (all off until switched on)
    role_mapping: bool = False
    role_attribute: str = "Role"
    role_admin: str = "namifax-admin"
    role_superuser: str = "namifax-superuser"
    role_can_del: str = "namifax-can-delete"
    role_any_modem: str = "namifax-any-modem"
    attr_modems: str = ""
    attr_faxcats: str = ""
    attr_didroutes: str = ""

def saml_settings(session: Any, base_url: str) -> SAMLSettings:
    """The settings saved on the admin SAML page (disabled until an administrator turns it on and names the identity provider)."""
    from namifax.services.system_config import SystemConfigService

    cfg = SystemConfigService(session)
    base = base_url.rstrip("/")
    return SAMLSettings(
        enabled=cfg.get("saml_enabled", "0") == "1",
        idp_entity_id=cfg.get("saml_idp_entity_id", ""),
        idp_sso_url=cfg.get("saml_idp_sso_url", ""),
        idp_x509_cert=cfg.get("saml_idp_x509_cert", ""),
        sp_entity_id=f"{base}/auth/saml/metadata",
        sp_acs_url=f"{base}/auth/saml/acs",
        sp_sls_url=f"{base}/auth/saml/sls",
        jit_provisioning=cfg.get("saml_jit_provisioning", "1") == "1",
        default_role=cfg.get("saml_default_role", "user"),
        role_mapping=cfg.get("saml_role_mapping", "0") == "1",
        role_attribute=cfg.get("saml_role_attribute", "Role"),
        role_admin=cfg.get("saml_role_admin", "namifax-admin"),
        role_superuser=cfg.get("saml_role_superuser", "namifax-superuser"),
        role_can_del=cfg.get("saml_role_can_del", "namifax-can-delete"),
        role_any_modem=cfg.get("saml_role_any_modem", "namifax-any-modem"),
        attr_modems=cfg.get("saml_attr_modems", ""),
        attr_faxcats=cfg.get("saml_attr_faxcats", ""),
        attr_didroutes=cfg.get("saml_attr_didroutes", ""),
    )


class SAMLService:
    """Enterprise SAML 2.0 Service Provider implementation."""

    def __init__(self, settings: SAMLSettings | None = None, db: Any = None) -> None:
        self.settings = settings or SAMLSettings()
        self.db = resolve_db(db, "SAMLService")

    def generate_sp_metadata(self) -> str:
        """Generate SP metadata XML."""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata"
                     entityID="{self.settings.sp_entity_id}">
    <md:SPSSODescriptor AuthnRequestsSigned="false"
                        WantAssertionsSigned="false"
                        protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
        <md:SingleLogoutService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
                                Location="{self.settings.sp_sls_url}"/>
        <md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</md:NameIDFormat>
        <md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified</md:NameIDFormat>
        <md:AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
                                     Location="{self.settings.sp_acs_url}"
                                     index="1"/>
    </md:SPSSODescriptor>
</md:EntityDescriptor>
""".strip()

    def usable(self) -> bool:
        """Is SAML switched on with an identity provider to send people to?"""
        return bool(self.settings.enabled and self.settings.idp_sso_url)

    def create_authn_request(self, relay_state: str = "/") -> dict[str, str]:
        """Generate SAML 2.0 AuthnRequest and HTTP-Redirect parameters."""
        req_id = f"_{uuid.uuid4().hex}"
        issue_instant = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        xml_request = f"""<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                    ID="{req_id}"
                    Version="2.0"
                    IssueInstant="{issue_instant}"
                    Destination="{self.settings.idp_sso_url}"
                    AssertionConsumerServiceURL="{self.settings.sp_acs_url}"
                    ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">
    <saml:Issuer>{self.settings.sp_entity_id}</saml:Issuer>
    <samlp:NameIDPolicy Format="urn:oasis:names:tc:SAML:1.1:nameid-format:unspecified"
                        AllowCreate="true"/>
</samlp:AuthnRequest>"""

        # Deflate compression for HTTP-Redirect binding (wbits=-15 for raw deflate)
        compressor = zlib.compressobj(wbits=-15)
        deflated = compressor.compress(xml_request.encode("utf-8")) + compressor.flush()
        b64_request = base64.b64encode(deflated).decode("ascii")

        params = {
            "SAMLRequest": b64_request,
            "RelayState": relay_state,
        }
        redirect_url = f"{self.settings.idp_sso_url}?{urllib.parse.urlencode(params)}" if self.settings.idp_sso_url else ""

        return {
            "request_id": req_id,
            "saml_request": b64_request,
            "relay_state": relay_state,
            "redirect_url": redirect_url,
        }

    def process_saml_response(self, saml_response_b64: str, expected_request_id: str | None = None) -> dict[str, Any]:
        """Check a SAML Response and return who signed in.

        Only what the identity provider *signed* is believed: the signature must verify against the configured certificate and the
        name and attributes are read from the signed element only. The assertion must be for this service (audience, recipient),
        inside its time window, an answer to the request this browser started (``expected_request_id``) and not used before.
        """
        import time

        from lxml import etree
        from signxml import XMLVerifier
        from signxml.exceptions import InvalidSignature

        def refuse(reason: str) -> dict[str, Any]:
            return {"success": False, "error": reason}

        if not self.settings.enabled:
            return refuse("saml_not_enabled")
        if not (self.settings.idp_x509_cert or "").strip():
            return refuse("saml_no_idp_certificate")
        if not expected_request_id:
            return refuse("saml_no_request")                                  # only answers to a sign-in this browser started

        try:
            xml_bytes = base64.b64decode(saml_response_b64, validate=False)
            parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, load_dtd=False)
            root = etree.fromstring(xml_bytes, parser)
            if root.getroottree().docinfo.doctype:                            # no DTDs: no entity tricks
                return refuse("saml_dtd_not_allowed")
        except Exception:
            return refuse("saml_invalid_xml")

        ns = {"samlp": "urn:oasis:names:tc:SAML:2.0:protocol", "saml": "urn:oasis:names:tc:SAML:2.0:assertion"}
        status = root.find(".//samlp:StatusCode", ns)
        if status is None or not status.attrib.get("Value", "").endswith(":Success"):
            return refuse("saml_status_not_success")
        if root.get("InResponseTo") not in (None, expected_request_id):
            return refuse("saml_wrong_request")

        try:
            verified = XMLVerifier().verify(root, x509_cert=self.settings.idp_x509_cert)
        except InvalidSignature:
            return refuse("saml_bad_signature")
        except Exception:
            return refuse("saml_unsigned_or_unreadable")
        signed = verified.signed_xml
        assertion = signed if etree.QName(signed).localname == "Assertion" else signed.find(".//saml:Assertion", ns)
        if assertion is None:
            return refuse("saml_no_assertion")

        expected_issuer = (self.settings.idp_entity_id or "").strip()
        if expected_issuer:
            issuer = assertion.find("saml:Issuer", ns)                       # (inside the signed part)
            if issuer is None or (issuer.text or "").strip() != expected_issuer:
                return refuse("saml_wrong_issuer")
        else:
            logging.getLogger("namifax").warning(
                "SAML: no IdP entity ID is configured, so the Issuer of the response is not checked")

        now = time.time()
        skew = 120

        def moment(value: str | None) -> float | None:
            if not value:
                return None
            try:
                return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                return None

        conditions = assertion.find("saml:Conditions", ns)
        if conditions is None:
            return refuse("saml_no_conditions")
        not_before, not_after = moment(conditions.get("NotBefore")), moment(conditions.get("NotOnOrAfter"))
        if not_after is None or now >= not_after + skew or (not_before is not None and now < not_before - skew):
            return refuse("saml_expired")
        audiences = [a.text.strip() for a in conditions.findall("saml:AudienceRestriction/saml:Audience", ns) if a.text]
        if self.settings.sp_entity_id not in audiences:
            return refuse("saml_wrong_audience")

        confirmations = assertion.findall("saml:Subject/saml:SubjectConfirmation/saml:SubjectConfirmationData", ns)
        if not any(c.get("Recipient") == self.settings.sp_acs_url and c.get("InResponseTo") == expected_request_id
                   and (moment(c.get("NotOnOrAfter")) or 0) + skew > now for c in confirmations):
            return refuse("saml_wrong_recipient")

        assertion_id = assertion.get("ID") or ""
        if not assertion_id or _seen_before(assertion_id, not_after):
            return refuse("saml_replayed")

        name_id_elem = assertion.find("saml:Subject/saml:NameID", ns)
        name_id = name_id_elem.text.strip() if name_id_elem is not None and name_id_elem.text else ""
        if not name_id:
            return refuse("saml_no_name_id")
        attributes: dict[str, str] = {}
        multi: dict[str, list[str]] = {}
        for attr in assertion.findall("saml:AttributeStatement/saml:Attribute", ns):
            attr_name = attr.attrib.get("Name", "")
            values = [v.text.strip() for v in attr.findall("saml:AttributeValue", ns) if v.text and v.text.strip()]
            if attr_name and values:
                attributes[attr_name] = values[0]
                multi.setdefault(attr_name, []).extend(values)
        return {"success": True, "name_id": name_id, "attributes": attributes, "attributes_multi": multi}

    def provision_or_get_user(
        self,
        name_id: str,
        attributes: dict[str, Any] | None = None,
    ) -> NFUserAccount | None:
        """Find the account with the asserted email, or create one when JIT provisioning is on.

        An existing account is matched by email only. Matching on the local part of the NameID would let
        ``admin@other-company`` sign in as the local ``admin``. A new account gets a free username derived
        from the local part, no admin rights and a random password it never uses.
        """
        attributes = attributes or {}
        local = name_id.split("@")[0] if "@" in name_id else name_id
        base = re.sub(r"[^\w.]", "_", local) or "user"
        email = attributes.get("email") or (name_id if "@" in name_id else f"{base}@local")
        display_name = attributes.get("displayName") or attributes.get("name") or base

        user = NFUserAccount(db=self.db)
        if user.loadbyemail(email):
            return user

        if self.settings.jit_provisioning:
            username = base
            for n in range(1, 1000):
                if not NFUserAccount(db=self.db).load_username(username):
                    break
                username = f"{base}{n}"
            temp_pwd = base64.b64encode(os.urandom(12)).decode("ascii")
            if user.create_user(
                username=username,
                password=temp_pwd,
                name=display_name,
                email=email,
                is_admin=(self.settings.default_role == "admin" and not self.settings.role_mapping),
            ):
                return user

        return None


def apply_role_mapping(session: Any, user: NFUserAccount, multi: dict[str, list[str]], settings: SAMLSettings) -> dict[str, Any]:
    """Make the account's rights what the identity provider says (called at every sign-in while the mapping is on).

    Roles (values of ``role_attribute``) set the admin / superuser / may-delete / any-line flags. The attributes named for lines and
    categories list their names; a name that does not exist here is ignored. A setting whose attribute name is blank is not managed.
    Returns what was set, for the log.
    """
    from namifax.services.categories import FaxPDFCategory
    from namifax.services.did import DIDRouting
    from namifax.services.modem import FaxModem

    if not settings.role_mapping or not getattr(user, "uid", None):
        return {}
    roles = set(multi.get(settings.role_attribute, [])) if settings.role_attribute else set()
    superuser = bool(settings.role_superuser) and settings.role_superuser in roles
    changes: dict[str, Any] = {
        "superuser": int(superuser),
        "is_admin": int(superuser or (bool(settings.role_admin) and settings.role_admin in roles)),      # (a superuser may use the console)
        "can_del": int(bool(settings.role_can_del) and settings.role_can_del in roles),
        "any_modem": int(bool(settings.role_any_modem) and settings.role_any_modem in roles),
    }
    if settings.attr_modems:
        known = set(FaxModem(db=session).get_modems() or [])
        changes["modemdevs"] = "|".join(v for v in multi.get(settings.attr_modems, []) if v in known) or None
    if settings.attr_faxcats:
        by_name = {c["name"]: str(c["catid"]) for c in FaxPDFCategory(db=session).get_categories() or []}
        changes["faxcats"] = "|".join(by_name[v] for v in multi.get(settings.attr_faxcats, []) if v in by_name) or None
    if settings.attr_didroutes:
        routes = {str(r.get("routecode") or ""): str(r["didr_id"]) for r in DIDRouting(db=session).list_all()}
        routes.update({str(r.get("alias") or ""): str(r["didr_id"]) for r in DIDRouting(db=session).list_all() if r.get("alias")})
        changes["didrouting"] = "|".join(routes[v] for v in multi.get(settings.attr_didroutes, []) if v in routes) or None
    user.useraccount.update_entry({"uid": user.uid, **changes})
    user.dbdata.update(changes)
    return changes
