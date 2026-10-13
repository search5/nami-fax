"""Two-factor authentication self-service: turn it on, turn it off, get new recovery codes.

All four requests change the security of the signed-in account, so each one carries a CSRF token. Turning it off
or asking for new recovery codes also needs a valid code (a wrong one counts towards the lockout), and turning it
off needs the password as well.
"""

from __future__ import annotations

import hmac
from datetime import datetime
import re
from typing import Any, Optional

from pyramid.csrf import check_csrf_token
from pyramid.httpexceptions import HTTPBadRequest, HTTPFound
from pyramid.view import view_config

from namifax.common.secretbox import SecretDecryptError, SecretKeyError, decrypt, encrypt
from namifax.i18n import _
from namifax.services.totp import TotpService
from namifax.common.passwords import verify_password
from namifax.services.user_account import NFUserAccount

TEMPLATE = "namifax:templates/settings_2fa.jinja2"
_PENDING = "totp_pending"


# --- the secret waiting to be confirmed ---------------------------------------------------------------------------

def begin_enrolment(request: Any) -> str:
    """Make a new secret and keep it (encrypted) in the flow session until the user confirms it with a code."""
    secret = TotpService.generate_secret()
    request.session[_PENDING] = encrypt(secret)
    return secret


def pending_secret(request: Any) -> Optional[str]:
    stored = request.session.get(_PENDING)
    if not stored:
        return None
    try:
        return decrypt(stored)
    except (SecretDecryptError, SecretKeyError):
        return None


# --- helpers ---------------------------------------------------------------------------------------------------------

def _uid(request: Any) -> int:
    identity = request.identity or {}
    uid = identity.get("uid") or identity.get("user_id")
    if not uid:
        raise HTTPBadRequest("not signed in")
    return int(uid)


def _username(request: Any) -> str:
    return (request.identity or {}).get("username", "")


def _guard(request: Any) -> int:
    """The signed-in user's id; a request without a valid CSRF token is refused."""
    uid = _uid(request)
    if not check_csrf_token(request, raises=False):
        raise HTTPBadRequest("Invalid or missing CSRF token")
    return uid


def _backup_file(user: str, stamp: str, codes: list) -> str:
    """The text the user can save: the recovery codes only (the authenticator key is never put in a file)."""
    lines = ["NamiFAX two-factor authentication", f"Account: {user}", f"Saved: {stamp}", ""]
    lines += ["Recovery codes (each works once if you lose your authenticator):", *codes, "",
              "Keep this file somewhere safe and private. Anyone who has it can pass the second step of your login."]
    return "\n".join(lines) + "\n"


def _setup_page(request: Any, secret: str, error: Optional[str] = None) -> dict:
    import segno

    uri = TotpService.get_provisioning_uri(_username(request), secret)
    return {
        "mode": "setup", "error": error, "secret": secret, "uri": uri,
        "qr_svg": segno.make(uri, error="m").svg_inline(scale=5, dark="#0f172a", border=2),
        "csrf_token": request.session.get_csrf_token(), "current_user": request.identity, "active_tab": "settings",
    }


def _result(request: Any, *, error: Optional[str] = None, message: Optional[str] = None, codes: Optional[list] = None) -> dict:
    stamp = datetime.now().strftime("%Y-%m-%d")
    who = re.sub(r"[^A-Za-z0-9_.-]", "_", _username(request) or "user")
    file_text = _backup_file(who, stamp, codes or []) if codes else ""
    return {"mode": "codes" if codes else "message", "error": error, "message": message, "codes": codes or [],
            "backup_file": file_text, "backup_name": f"namifax-2fa-{who}-{stamp}.txt",
            "current_user": request.identity, "active_tab": "settings"}


def _lockout_text(svc: TotpService, uid: int) -> str:
    minutes = max(1, -(-svc.lock_remaining_seconds(uid) // 60))
    return _("Too many failed attempts. Try again in %(minutes)d minutes.") % {"minutes": minutes}


def _check_code(svc: TotpService, uid: int, code: str) -> Optional[str]:
    """None when the code is right; otherwise the message to show."""
    if svc.is_locked(uid):
        return _lockout_text(svc, uid)
    if svc.verify_user_login(uid, code or ""):
        return None
    return _lockout_text(svc, uid) if svc.is_locked(uid) else _("The code is not valid.")


# --- views -------------------------------------------------------------------------------------------------------------

@view_config(route_name="totp_setup", request_method="GET", renderer=TEMPLATE, permission="view")
def totp_setup_view(request):
    _uid(request)
    try:
        secret = pending_secret(request) or begin_enrolment(request)
    except SecretKeyError as exc:
        return {"mode": "message", "error": str(exc), "message": None, "codes": [],
                "current_user": request.identity, "active_tab": "settings"}
    return _setup_page(request, secret)


@view_config(route_name="totp_enable", request_method="POST", renderer=TEMPLATE, permission="view")
def totp_enable_view(request):
    uid = _guard(request)
    secret = pending_secret(request)
    if not secret:
        return HTTPFound(location=request.route_url("totp_setup"))
    result = TotpService(request.dbsession).enable_totp(uid, secret, (request.POST.get("code") or "").strip())
    if not result["success"]:
        return _setup_page(request, secret, error=_("The code did not match. Check the time on your phone and try again."))
    request.session.pop(_PENDING, None)
    return _result(request, codes=result["backup_codes"])


@view_config(route_name="totp_disable", request_method="POST", renderer=TEMPLATE, permission="view")
def totp_disable_view(request):
    uid = _guard(request)
    user = NFUserAccount(db=request.dbsession)
    if not user.load(uid) or not verify_password(user.dbdata.get("password"), request.POST.get("password") or ""):
        return _result(request, error=_("The password is not correct."))
    svc = TotpService(request.dbsession)
    problem = _check_code(svc, uid, request.POST.get("code", ""))
    if problem:
        return _result(request, error=problem)
    svc.disable_totp(uid)
    return HTTPFound(location=request.route_url("settings"))


@view_config(route_name="totp_recovery", request_method="POST", renderer=TEMPLATE, permission="view")
def totp_recovery_view(request):
    uid = _guard(request)
    svc = TotpService(request.dbsession)
    problem = _check_code(svc, uid, request.POST.get("code", ""))
    if problem:
        return _result(request, error=problem)
    return _result(request, codes=svc.regenerate_backup_codes(uid))
