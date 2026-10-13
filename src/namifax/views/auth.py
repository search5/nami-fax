"""NamiFAX Authentication Views matching legacy NamiFAX behavior."""

from __future__ import annotations

from pyramid.csrf import check_csrf_token
from pyramid.httpexceptions import HTTPFound
from pyramid.security import forget, remember
from pyramid.view import view_config

from namifax.common.helpers import avantfaxlog, get_admin_email, send_mail
from namifax.common.validators import is_valid_email
from namifax.services.user_account import NFUserAccount
from namifax.services.totp import TotpService
from namifax.i18n import _


@view_config(route_name="home", renderer="namifax:templates/login.jinja2", request_method="GET", permission="public")
@view_config(route_name="login", renderer="namifax:templates/login.jinja2", request_method="GET", permission="public")
def login_get_view(request):
    """Render login page with NamiFAX visual structure."""
    if request.identity:
        return HTTPFound(location=request.route_url("inbox"))

    error = _saml_message(request)
    from namifax.auth import alternate

    remote_user = (request.environ.get("REMOTE_USER") or "").strip()
    if alternate.webserver_login() and remote_user:                 # the web server has authenticated this person
        account = NFUserAccount(db=request.dbsession)
        if account.login_webauth(remote_user, remote_ip=getattr(request, "remote_addr", None) or "127.0.0.1"):
            return _finish_login(request, account.get_uid(), remote_user)
        error = account.get_error()
    return {
        "title": "- NamiFAX - Login",
        "server_name": "NamiFAX Server 3.3.5",
        "username": "",
        "error": error,
        "current_user": None,
        "saml_enabled": _saml_usable(request),
    }


def _saml_usable(request) -> bool:
    from namifax.services.saml import saml_settings

    try:
        settings = saml_settings(request.dbsession, request.application_url)
        return bool(settings.enabled and settings.idp_sso_url)
    except Exception:
        return False


def _saml_message(request):
    """What the SAML views left for the login page (one message, once)."""
    texts = {
        "saml_not_configured": _("SAML sign-in is not set up on this server."),
        "saml_missing_response": _("The identity provider sent no answer."),
        "saml_refused": _("The identity provider's answer could not be accepted. Start the sign-in again."),
        "saml_no_account": _("No account here matches the identity provider's answer."),
        "saml_account_disabled": _("Account is disabled"),
    }
    try:
        keys = request.session.pop_flash("login")
    except Exception:
        return None
    return texts.get(keys[0]) if keys else None


_PWD_PENDING = "pwd_change_pending"


@view_config(route_name="login", renderer="namifax:templates/login.jinja2", request_method="POST", permission="public")
def login_post_view(request):
    """Authenticate user and redirect or re-render login page on failure."""
    params = request.params if (hasattr(request, "params") and request.params) else (getattr(request, "POST", None) or getattr(request, "GET", None) or {})
    username = params.get("username", "").strip()
    password = params.get("password", "")

    # Check credentials using NFUserAccount service
    user = NFUserAccount(db=request.dbsession)
    is_valid = False

    remote_ip = getattr(request, "remote_addr", None) or "127.0.0.1"
    from namifax.auth import alternate

    # The system password first when that is configured; the account's own password when it is not, or may follow
    from namifax.services.login_throttle import LoginThrottle

    throttle = LoginThrottle(request.dbsession)
    if not throttle.begin_attempt(username, remote_ip):            # locked: the password is not even looked at; else this attempt is counted now
        return {
            "title": "- NamiFAX - Login",
            "server_name": "NamiFAX Server 3.3.5",
            "username": username,
            "error": (_("Too many failed sign-in attempts. This account is locked until an administrator unlocks it.")
                      if throttle.lock_reason(username) == "account"
                      else _("Too many failed sign-in attempts. Please try again later.")),
            "current_user": None,
        }

    alt_error = None
    if alternate.enabled():
        if user.login_alternate_auth(username, password, remote_ip=remote_ip):
            is_valid = True
        else:
            alt_error = user.get_error()
    if not is_valid and (not alternate.enabled() or alternate.fallback()):
        if user.login(username, password, remote_ip=remote_ip):
            is_valid = True
        alt_error = None if is_valid else user.get_error()

    if not is_valid:
        request.response.status_code = 200                       # (the failure was counted before the password was checked)
        problem = alt_error or user.get_error()
        if problem == "Account is disabled":
            message = _("Account is disabled")
        elif problem and problem.startswith("User '"):
            message = problem                                    # a system user without an AvantFAX account
        else:
            message = "Invalid username or password"
        return {
            "title": "- NamiFAX - Login",
            "server_name": "NamiFAX Server 3.3.5",
            "username": username,
            "error": message,
            "current_user": None,
        }

    throttle.record_success(username, remote_ip)
    uid = getattr(user, "get_uid", lambda: None)() or getattr(user, "uid", None)

    # An account that was reset, has expired or has never been used must choose a new password first. The login
    # cookie is not issued until it has (the second factor, if any, comes after that).
    if uid and user.is_expired():
        request.session[_PWD_PENDING] = {"uid": int(uid), "username": username}
        return HTTPFound(location=request.route_url("pwdexpired"))

    return _finish_login(request, uid, username)


def _finish_login(request, uid, username):
    """Second factor if the account has one, otherwise the login cookie."""
    from namifax.services.totp import TotpService
    totp_svc = TotpService(request.dbsession)
    if uid and totp_svc.is_totp_enabled(uid):
        request.session["2fa_pending_uid"] = uid
        request.session["2fa_pending_username"] = username
        loc = "/login/totp"
        if hasattr(request, "route_url"):
            try:
                loc = request.route_url("login_totp")
            except Exception:
                pass
        return HTTPFound(location=loc)

    # Successful login: remember credentials and redirect to inbox
    headers = remember(request, username)
    loc = "/inbox"
    if hasattr(request, "route_url"):
        try:
            loc = request.route_url("inbox")
        except Exception:
            pass
    return HTTPFound(location=loc, headers=headers)


def _lockout_message(totp_svc, uid) -> str:
    minutes = max(1, -(-totp_svc.lock_remaining_seconds(uid) // 60))
    return _("Too many failed attempts. Try again in %(minutes)d minutes.") % {"minutes": minutes}


@view_config(route_name="login_totp", renderer="namifax:templates/login_totp.jinja2", permission="public")
def login_totp_view(request):
    """Render and verify 2FA TOTP / backup code challenge."""
    pending_uid = request.session.get("2fa_pending_uid")
    if not pending_uid:
        loc = request.route_url("login") if hasattr(request, "route_url") else "/login"
        return HTTPFound(location=loc)

    error = None
    if request.method == "POST":
        params = dict(getattr(request, "POST", {}))
        if hasattr(request, "params") and request.params:
            params.update(request.params)

        code = params.get("code", "").strip()
        from namifax.services.totp import TotpService
        totp_svc = TotpService(request.dbsession)

        if totp_svc.is_locked(pending_uid):
            error = _lockout_message(totp_svc, pending_uid)
        elif totp_svc.verify_user_login(pending_uid, code):
            username = request.session.pop("2fa_pending_username", "user")
            request.session.pop("2fa_pending_uid", None)
            request.session["user_id"] = pending_uid
            headers = remember(request, username)
            loc = "/inbox"
            if hasattr(request, "route_url"):
                try:
                    loc = request.route_url("inbox")
                except Exception:
                    pass
            return HTTPFound(location=loc, headers=headers)
        else:
            error = _lockout_message(totp_svc, pending_uid) if totp_svc.is_locked(pending_uid) \
                else _("Invalid or expired verification code.")

    return {
        "title": "- NamiFAX - Two-Factor Authentication",
        "error": error,
    }


def _forgot_page(error=None, done=False):
    return {"title": "- NamiFAX - Lost Password", "message": None, "error": error, "done": done}


@view_config(route_name="forgot", renderer="namifax:templates/forgot.jinja2", request_method="GET", permission="public")
def forgot_get_view(request):
    """Render lost password recovery page."""
    return _forgot_page()


@view_config(route_name="forgot", renderer="namifax:templates/forgot.jinja2", request_method="POST", permission="public")
def forgot_post_view(request):
    """The original forgot.php: a new temporary password is mailed to the account with that address.

    Like the original it says when no account has the address. Unlike the original the new password is not written to
    the log, and when the mail cannot be sent the old password stays valid (the original left the account locked out).
    """
    email = (request.POST.get("email") or "").strip()
    if not is_valid_email(email):
        return _forgot_page(_("Please enter a valid e-mail address."))

    ip = request.remote_addr or ""
    user = NFUserAccount(db=request.dbsession)
    ok, new_password = user.reset_password(email)
    if not ok:
        avantfaxlog(f"forgot> Attempt to reset password for email '{email}' from IP: {ip}", session=request.dbsession)
        return _forgot_page(_(user.get_error()) if user.get_error() == "Sorry, no corresponding user was found."
                            else user.get_error())

    username = user.get_username()
    avantfaxlog(f"forgot> reset password for {username} <{email}> from IP: {ip}", session=request.dbsession)
    body = str(_(
        "The user account %(user)s has this email associated with it.  A web user from %(ip)s has just requested that a "
        "new password be sent.\n\nYour New Password is: %(password)s\n\nIf this was an error just login with your new "
        "password and then change your password to what you would like it to be."
    )) % {"user": username, "ip": ip, "password": new_password}
    if send_mail(email, get_admin_email(), "password reset", body, session=request.dbsession):
        return _forgot_page(done=True)
    user.undo_reset()
    return _forgot_page(_("Email failed to send"))


def _pwd_page(error=None):
    return {"title": "- NamiFAX - Password Expired", "error": error}


@view_config(route_name="pwdexpired", renderer="namifax:templates/pwdexpired.jinja2", request_method="GET", permission="public")
def pwdexpired_get_view(request):
    """The page an account lands on after a correct login when it has to choose a new password."""
    if not request.session.get(_PWD_PENDING):
        return HTTPFound(location=request.route_url("login"))
    return _pwd_page()


@view_config(route_name="pwdexpired", renderer="namifax:templates/pwdexpired.jinja2", request_method="POST", permission="public")
def pwdexpired_post_view(request):
    """Change the password of the account that just logged in, then finish the login.

    Only the account parked here by ``login_post_view`` can be changed: the request carries no user name.
    """
    pending = request.session.get(_PWD_PENDING)
    if not pending:
        return HTTPFound(location=request.route_url("login"))

    params = request.POST
    oldpwd, newpwd, conpwd = params.get("oldpwd", ""), params.get("newpwd", ""), params.get("conpwd", "")
    if not oldpwd or not newpwd or not conpwd:
        return _pwd_page("All fields are required.")
    if newpwd != conpwd:
        return _pwd_page("New passwords do not match.")

    user = NFUserAccount(db=request.dbsession)
    if not user.load(pending["uid"]):
        request.session.pop(_PWD_PENDING, None)
        return HTTPFound(location=request.route_url("login"))
    if not user.set_newpassword(oldpwd, newpwd):
        return _pwd_page(user.get_error() or "The password could not be changed.")

    request.session.pop(_PWD_PENDING, None)
    return _finish_login(request, pending["uid"], pending["username"])


@view_config(route_name="logout", renderer="namifax:templates/logout.jinja2", permission="public")
def logout_view(request):
    """Sign out: a POST with the session's CSRF token clears the login cookie and goes to the login page.

    A plain link (the original's logout.php) could be followed by any other web page, which would sign the user out
    against their will. A GET therefore only asks "Sign out?" and offers the button.
    """
    if request.method == "POST":
        check_csrf_token(request)
        return HTTPFound(location=request.route_url("login"), headers=forget(request))
    return {"title": "- NamiFAX - Sign out", "csrf_token": request.session.get_csrf_token()}

