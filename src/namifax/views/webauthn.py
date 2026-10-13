from __future__ import annotations

import json
from typing import Any
from pyramid.request import Request
from pyramid.response import Response
from pyramid.security import remember
from pyramid.view import view_config

from namifax.services.user_account import NFUserAccount
from namifax.services.webauthn import WebAuthnService

def _json_res(data: Any, status: int = 200) -> Response:
    return Response(
        json.dumps(data),
        status=status,
        content_type="application/json",
        charset="utf-8",
    )

def _get_current_user(request: Request) -> NFUserAccount | None:
    username = getattr(request, "authenticated_userid", None)
    if not username and hasattr(request, "session"):
        username = request.session.get("username")
    if not username:
        return None
    user = NFUserAccount(db=request.dbsession)
    if user.load_by_username(username):
        return user
    return None

def _get_webauthn_service(request: Request) -> WebAuthnService:
    host = request.host.split(":")[0] if request.host else "localhost"
    origin = f"{request.scheme}://{request.host}" if hasattr(request, "scheme") and request.host else "http://localhost:8000"
    return WebAuthnService(rp_id=host, rp_name="NamiFAX Enterprise", origin=origin, db=request.dbsession)

@view_config(route_name="api_webauthn_register_options", renderer="json")
def webauthn_register_options_view(request: Request) -> Response:
    user = _get_current_user(request)
    if not user:
        return _json_res({"error": "Unauthorized"}, status=401)

    svc = _get_webauthn_service(request)
    opts = svc.generate_registration_options(
        user_id=user.get_uid(),
        user_name=user.get_username(),
        user_display_name=user.get_name() or user.get_username(),
    )
    if hasattr(request, "session"):
        request.session["webauthn_reg_challenge"] = opts.get("challenge")
    return _json_res(opts)

@view_config(route_name="api_webauthn_register_verify", renderer="json")
def webauthn_register_verify_view(request: Request) -> Response:
    user = _get_current_user(request)
    if not user:
        return _json_res({"error": "Unauthorized"}, status=401)

    challenge = request.session.pop("webauthn_reg_challenge", None) if hasattr(request, "session") else None
    if not challenge:
        return _json_res({"error": "Missing registration challenge"}, status=400)

    try:
        payload = request.json_body if hasattr(request, "json_body") else json.loads(request.body)
        device_name = payload.get("device_name", "Security Key")
        credential_data = payload.get("credential", payload)

        svc = _get_webauthn_service(request)
        result = svc.verify_registration_response(
            credential_data=credential_data,
            expected_challenge=challenge,
        )

        svc.save_credential(
            uid=user.get_uid(),
            credential_id=result["credential_id"],
            public_key=result["credential_public_key"],
            sign_count=result["sign_count"],
            device_name=device_name,
        )
        return _json_res({"success": True, "credential_id": result["credential_id"]})
    except Exception as e:
        return _json_res({"error": str(e)}, status=400)

@view_config(route_name="api_webauthn_auth_options", renderer="json")
def webauthn_auth_options_view(request: Request) -> Response:
    username = request.params.get("username")
    uid = None
    if username:
        u = NFUserAccount(db=request.dbsession)
        if u.load_by_username(username):
            uid = u.get_uid()

    svc = _get_webauthn_service(request)
    opts = svc.generate_authentication_options(user_id=uid)
    if hasattr(request, "session"):
        request.session["webauthn_auth_challenge"] = opts.get("challenge")
    return _json_res(opts)

@view_config(route_name="api_webauthn_auth_verify", renderer="json")
def webauthn_auth_verify_view(request: Request) -> Response:
    challenge = request.session.pop("webauthn_auth_challenge", None) if hasattr(request, "session") else None   # one use
    if not challenge:
        return _json_res({"error": "Missing authentication challenge"}, status=400)

    try:
        payload = request.json_body if hasattr(request, "json_body") else json.loads(request.body)
        credential_data = payload.get("credential", payload)
        cred_id = credential_data.get("id")

        svc = _get_webauthn_service(request)
        cred_row = svc.get_credential_by_id(cred_id)
        if not cred_row:
            return _json_res({"error": "Unknown credential"}, status=400)

        pub_key = bytes.fromhex(cred_row["public_key"])
        new_sign_count = svc.verify_authentication_response(
            credential_data=credential_data,
            expected_challenge=challenge,
            credential_public_key=pub_key,
            credential_current_sign_count=cred_row.get("sign_count", 0),
        )
        svc.update_sign_count(cred_id, new_sign_count)

        # Sign in like the password login: the same disabled-account check and the same token cookie
        uid = cred_row["uid"]
        user = NFUserAccount(db=request.dbsession)
        if user.load_by_id(uid):
            username = user.get_username()
            remote_ip = getattr(request, "remote_addr", None) or "127.0.0.1"
            if not NFUserAccount(db=request.dbsession).login_webauth(username, remote_ip=remote_ip):
                return _json_res({"error": "Account is disabled"}, status=400)
            response = _json_res({"success": True, "username": username})
            response.headerlist.extend(remember(request, username))
            return response

        return _json_res({"error": "User account not found"}, status=400)
    except Exception as e:
        return _json_res({"error": str(e)}, status=400)

@view_config(route_name="api_webauthn_credentials", renderer="json")
def webauthn_list_credentials_view(request: Request) -> Response:
    user = _get_current_user(request)
    if not user:
        return _json_res({"error": "Unauthorized"}, status=401)

    svc = _get_webauthn_service(request)
    creds = svc.list_credentials(user.get_uid())
    data = [
        {
            "id": c.id,
            "credential_id": c.credential_id,
            "device_name": c.device_name,
            "created_at": str(c.created_at),
            "last_used_at": str(c.last_used_at) if c.last_used_at else None,
        }
        for c in creds
    ]
    return _json_res(data)

@view_config(route_name="api_webauthn_credentials_delete", renderer="json")
def webauthn_delete_credential_view(request: Request) -> Response:
    user = _get_current_user(request)
    if not user:
        return _json_res({"error": "Unauthorized"}, status=401)

    cred_db_id = request.POST.get("credential_db_id") or request.params.get("credential_db_id")
    if not cred_db_id or not str(cred_db_id).isdecimal():
        return _json_res({"error": "Invalid credential ID"}, status=400)

    svc = _get_webauthn_service(request)
    success = svc.delete_credential(user.get_uid(), int(cred_db_id))
    return _json_res({"success": success})
