"""NamiFAX User Settings & Preferences View Controller."""

from __future__ import annotations

from pyramid.view import view_config

from namifax.common import settings as app_settings
from namifax.common.validators import is_valid_email
from namifax.i18n import _
from namifax.services.covers import Covers
from namifax.services.user_account import NFUserAccount

FAXES_PER_PAGE = ["10", "15", "20", "25", "30", "50", "100"]


def _cover_choices(session):
    covers = Covers(db=session)
    found = []
    for file in covers.get_covers() or []:
        if covers.load_cover(file):
            found.append((str(covers.get_cover_id()), covers.get_title() or file))
    return found


@view_config(route_name="settings", renderer="namifax:templates/settings.jinja2", permission="view")
def settings_view(request):
    """Render and handle user profile, contact details, and password settings form."""
    identity = request.identity or {"username": "admin", "is_admin": True, "superuser": True}
    message = None
    error = None

    user_account = NFUserAccount(db=request.dbsession)
    user_loaded = False

    uid = identity.get("uid")
    if uid:
        user_loaded = user_account.load(int(uid))
    elif identity.get("username"):
        user_loaded = user_account.load_username(identity["username"])

    if user_loaded and user_account.dbdata:
        profile_data = {
            "name": user_account.dbdata.get("name") or identity.get("name", "Administrator"),
            "email": user_account.dbdata.get("email") or identity.get("email", "admin@avantfax.local"),
            "from_company": user_account.dbdata.get("from_company") or "",
            "from_location": user_account.dbdata.get("from_location") or "",
            "from_voicenumber": user_account.dbdata.get("from_voicenumber") or "",
            "from_faxnumber": user_account.dbdata.get("from_faxnumber") or "",
            "user_tsi": user_account.dbdata.get("user_tsi") or "",
            "email_sig": user_account.dbdata.get("email_sig") or "",
            "language": user_account.dbdata.get("language") or "en",
            "coverpage_id": str(user_account.dbdata.get("coverpage_id") or ""),
            "faxperpageinbox": str(user_account.dbdata.get("faxperpageinbox") or app_settings.default_faxes_per_page_inbox()),
            "faxperpagearchive": str(user_account.dbdata.get("faxperpagearchive") or app_settings.default_faxes_per_page_archive()),
        }
    else:
        profile_data = {
            "name": identity.get("name", "Administrator"),
            "email": identity.get("email", "admin@avantfax.local"),
            "from_company": identity.get("from_company", "Enterprise Inc."),
            "from_location": identity.get("from_location", "Headquarters"),
            "from_voicenumber": identity.get("from_voicenumber", "+1-555-0100"),
            "from_faxnumber": identity.get("from_faxnumber", "+1-555-0199"),
            "user_tsi": identity.get("user_tsi", "ENTERPRISE-HQ"),
            "email_sig": identity.get("email_sig", "-- \nBest regards,\nNamiFAX Administrator"),
            "language": identity.get("language", "en"),
            "coverpage_id": "", "faxperpageinbox": str(app_settings.default_faxes_per_page_inbox()),
            "faxperpagearchive": str(app_settings.default_faxes_per_page_archive()),
        }

    # Determine current language from cookie, session, profile, or identity
    current_lang = profile_data.get("language", "en")
    if hasattr(request, "cookies") and request.cookies.get("_LOCALE_"):
        current_lang = request.cookies.get("_LOCALE_")
    elif hasattr(request, "session") and request.session.get("language"):
        current_lang = request.session.get("language")
    elif identity.get("language"):
        current_lang = identity.get("language")

    profile_data["language"] = current_lang

    if request.method == "POST":
        params = request.params
        old_pw = params.get("old_password", "").strip()
        new_pw = params.get("new_password", "").strip()
        confirm_pw = params.get("confirm_password", "").strip()

        # Handle password change
        if old_pw or new_pw:
            if not old_pw:
                error = "Old password is required to change password."
            elif not new_pw:
                error = "New password is required."
            elif new_pw != confirm_pw:
                error = "New passwords do not match."
            elif user_loaded:
                success = user_account.set_newpassword(old_pw, new_pw)
                if not success:
                    error = user_account.get_error() or "Failed to change password."
            else:
                error = "User account not loaded."

        # Handle profile fields update
        if not error:
            selected_lang = params.get("language", current_lang)
            name = (params.get("name", profile_data["name"]) or "").strip()
            email = (params.get("email", profile_data["email"]) or "").strip()
            if not name:
                error = _("You must enter a name.")
            elif not is_valid_email(email):
                error = _("Please enter a valid e-mail address.")
            elif user_loaded and not user_account.set_email(email):
                error = user_account.get_error() or _("Please enter a valid e-mail address.")

        if not error:
            def per_page(field, default):
                value = (params.get(field) or "").strip()
                return value if value in FAXES_PER_PAGE else default

            cover = (params.get("coverpage_id") or "").strip()
            profile_data.update({
                "name": name,
                "email": email,
                "from_company": params.get("from_company", ""),
                "from_location": params.get("from_location", ""),
                "from_voicenumber": params.get("from_voicenumber", ""),
                "from_faxnumber": params.get("from_faxnumber", ""),
                "user_tsi": params.get("user_tsi", "") if identity.get("superuser") else profile_data["user_tsi"],
                "email_sig": params.get("email_sig", ""),
                "language": selected_lang,
                "coverpage_id": cover if cover.isdecimal() else "",
                "faxperpageinbox": per_page("faxperpageinbox", profile_data["faxperpageinbox"]),
                "faxperpagearchive": per_page("faxperpagearchive", profile_data["faxperpagearchive"]),
            })

            if user_loaded:
                user_account.dbdata.update(
                    profile_data,
                    coverpage_id=int(profile_data["coverpage_id"]) if profile_data["coverpage_id"] else None,
                    faxperpageinbox=int(profile_data["faxperpageinbox"]),
                    faxperpagearchive=int(profile_data["faxperpagearchive"]))
                if not user_account.user_update():
                    error = user_account.get_error() or "Failed to update profile."

            if not error:
                # Update session language
                if hasattr(request, "session"):
                    request.session["language"] = selected_lang

                # Set _LOCALE_ cookie for immediate persistence across requests
                if hasattr(request, "response"):
                    request.response.set_cookie("_LOCALE_", selected_lang, max_age=31536000, path="/")

                message = "Settings updated successfully."

    # the session identity carries "user_id" (not "uid"); the loaded account is the reliable source
    account_uid = (user_account.get_uid() if user_loaded else None) or identity.get("uid") or identity.get("user_id")
    totp_enabled, recovery_codes_left = False, 0
    if account_uid:
        try:
            from namifax.services.totp import TotpService
            totp_svc = TotpService(request.dbsession)
            totp_enabled = totp_svc.is_totp_enabled(account_uid)
            recovery_codes_left = totp_svc.backup_codes_remaining(account_uid) if totp_enabled else 0
        except Exception:
            pass

    return {
        "title": "- NamiFAX - Settings",
        "current_user": identity,
        "active_tab": "settings",
        "message": message,
        "error": error,
        "user_profile": profile_data,
        "is_superuser": bool(identity.get("superuser")),
        "covers": _cover_choices(request.dbsession),
        "per_page": FAXES_PER_PAGE,
        "totp_enabled": totp_enabled,
        "recovery_codes_left": recovery_codes_left,
        "csrf_token": request.session.get_csrf_token(),
    }
