from __future__ import annotations

from pyramid.httpexceptions import HTTPFound
from pyramid.request import Request
from pyramid.security import remember
from pyramid.response import Response
from pyramid.view import view_config

from namifax.common.helpers import avantfaxlog
from namifax.services.saml import SAMLService, apply_role_mapping, saml_settings
from namifax.services.user_account import NFUserAccount

def _get_saml_service(request: Request) -> SAMLService:
    base_url = request.application_url if hasattr(request, "application_url") else "http://localhost:8000"
    return SAMLService(saml_settings(request.dbsession, base_url), db=request.dbsession)


def _back_to_login(request: Request, message_key: str) -> HTTPFound:
    request.session.flash(message_key, "login")
    return HTTPFound(location=request.route_url("login") if hasattr(request, "route_url") else "/login")


def _safe_relay(target: str) -> str:
    """Only paths on this site; ``RelayState`` comes from the browser and must not become an open redirect."""
    return target if target.startswith("/") and not target.startswith("//") and "\\" not in target else "/inbox"


@view_config(route_name="saml_metadata")
def saml_metadata_view(request: Request) -> Response:
    svc = _get_saml_service(request)
    xml_content = svc.generate_sp_metadata()
    return Response(
        xml_content,
        content_type="application/xml",
        charset="utf-8",
    )

@view_config(route_name="saml_login")
def saml_login_view(request: Request) -> Response:
    svc = _get_saml_service(request)
    if not svc.usable():                                                    # not set up: say so instead of bouncing silently
        return _back_to_login(request, "saml_not_configured")
    req_data = svc.create_authn_request(relay_state=request.params.get("relay_state", "/inbox"))
    request.session["saml_request_id"] = req_data["request_id"]               # the only answer accepted for this browser
    return HTTPFound(location=req_data["redirect_url"])


@view_config(route_name="saml_acs", request_method="POST")
def saml_acs_view(request: Request) -> Response:
    saml_response = request.POST.get("SAMLResponse") or request.params.get("SAMLResponse")
    relay_state = request.POST.get("RelayState") or request.params.get("RelayState") or "/inbox"

    if not saml_response:
        return _back_to_login(request, "saml_missing_response")

    svc = _get_saml_service(request)
    request_id = request.session.pop("saml_request_id", None)               # one answer per sign-in
    result = svc.process_saml_response(saml_response, expected_request_id=request_id)
    if not result.get("success"):
        return _back_to_login(request, "saml_refused")

    user = svc.provision_or_get_user(
        name_id=result.get("name_id", ""),
        attributes=result.get("attributes"),
    )
    if not user:
        return _back_to_login(request, "saml_no_account")
    if svc.settings.role_mapping:                                            # the identity provider decides the rights
        applied = apply_role_mapping(request.dbsession, user, result.get("attributes_multi") or {}, svc.settings)
        avantfaxlog(f"saml> rights of '{user.get_username()}' set from the identity provider: {applied}", echo=False, session=request.dbsession)

    # sign in like the password login does: the same checks (disabled account) and the same token cookie
    username = user.get_username()
    remote_ip = getattr(request, "remote_addr", None) or "127.0.0.1"
    if not NFUserAccount(db=request.dbsession).login_webauth(username, remote_ip=remote_ip):
        return _back_to_login(request, "saml_account_disabled")

    return HTTPFound(location=_safe_relay(relay_state), headers=remember(request, username))

@view_config(route_name="saml_sls")
def saml_sls_view(request: Request) -> Response:
    if hasattr(request, "session"):
        request.session.clear()
        if hasattr(request.session, "changed"):
            request.session.changed()
    return HTTPFound(location="/login")
