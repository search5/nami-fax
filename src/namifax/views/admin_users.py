"""Admin > Users (the original admin/users.php and deluser.php).

Every field of the original, the lines / DID routes / categories a user may use, messages for each mistake, a random password
mailed to a new user who was given none, and a confirmation before an account is deleted.
"""

from __future__ import annotations

import glob
import os
import re
from datetime import date

from pyramid.csrf import check_csrf_token
from pyramid.httpexceptions import HTTPFound
from pyramid.view import view_config

from namifax.common import settings
from namifax.common.helpers import send_mail
from namifax.common.validators import is_valid_email
from namifax.i18n import _
from namifax.services import hylafax_users
from namifax.services.covers import Covers
from namifax.services.did import DIDRouting
from namifax.services.categories import FaxPDFCategory
from namifax.services.fax_access import _did_routing_enabled
from namifax.services.login_throttle import LoginThrottle
from namifax.services.modem import FaxModem
from namifax.services.user_account import NFUserAccount
from namifax.views.admin import get_all_admin_users

FAXES_PER_PAGE = ["10", "15", "20", "25", "30", "50", "100"]


def _default_inbox() -> str:
    return str(settings.default_faxes_per_page_inbox())


def _default_archive() -> str:
    return str(settings.default_faxes_per_page_archive())


FLAGS = ("is_admin", "superuser", "can_del", "any_modem", "pwd_reuse")


def _add_months(start: date, months: int) -> str:
    month = start.month - 1 + months
    year, month = start.year + month // 12, month % 12 + 1
    day = min(start.day, [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day).isoformat()


def _expiry(pwdcycle: str):
    return _add_months(date.today(), int(pwdcycle)) if pwdcycle in ("3", "6") else None


def _languages() -> list[tuple[str, str]]:
    from babel import Locale

    root = os.path.join(os.path.dirname(os.path.dirname(__file__)), "locale")
    found = []
    for code in sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))):
        try:
            found.append((code, Locale.parse(code).get_display_name("en").title()))
        except Exception:
            found.append((code, code))
    return found


def _audio_files() -> list[str]:
    from namifax.views.ajax import audio_dir

    folder = audio_dir()
    return sorted(os.path.basename(f) for ext in ("ogg", "wav", "mp3") for f in glob.glob(os.path.join(folder, f"*.{ext}")))


def _choices(request) -> dict:
    db = request.dbsession
    modems = FaxModem(db=db)
    lines = []
    for device in modems.get_modems() or []:
        if modems.load_device(device):
            lines.append((modems.get_device() or device, modems.get_alias() or device))
    routes = [("0", _("Catch All"))] + [(str(r["didr_id"]), f"{r.get('alias') or ''} ({r.get('routecode') or ''})")
                                        for r in DIDRouting(db=db).list_all()]
    covers = Covers(db=db)
    cover_list = []
    for file in covers.get_covers() or []:
        if covers.load_cover(file):
            cover_list.append((str(covers.get_cover_id()), covers.get_title() or file))
    return {
        "lines": lines, "routes": routes, "did_enabled": _did_routing_enabled(),
        "categories": [(str(c["catid"]), c["name"]) for c in FaxPDFCategory(db=db).get_categories() or []],
        "covers": cover_list, "audio": [(f, f) for f in _audio_files()], "languages": _languages(),
        "per_page": [(n, n) for n in FAXES_PER_PAGE],
        "cycles": [("0", _("Never")), ("3", _("Every 3 Months")), ("6", _("Every 6 Months"))],
    }


def _blank() -> dict:
    return {"uid": None, "name": "", "username": "", "email": "", "password": "", "acc_enabled": True, "pwdcycle": "0",
            "pwd_reuse": False, "language": "en", "from_company": os.environ.get("FROM_COMPANY", ""),
            "from_location": os.environ.get("FROM_LOCATION", ""), "from_voicenumber": os.environ.get("FROM_VOICENUMBER", ""),
            "from_faxnumber": os.environ.get("FROM_FAXNUMBER", ""), "user_tsi": os.environ.get("DEFAULT_TSI_ID", ""),
            "coverpage_id": "", "audiofile": "", "faxperpageinbox": _default_inbox(), "faxperpagearchive": _default_archive(),
            "is_admin": False, "superuser": False, "can_del": False, "any_modem": False,
            "modemdevs": [], "didrouting": [], "faxcats": []}


def _from_account(svc: NFUserAccount) -> dict:
    d = svc.dbdata
    values = _blank()
    for key in ("uid", "name", "username", "email", "language", "from_company", "from_location", "from_voicenumber",
                "from_faxnumber", "user_tsi", "audiofile"):
        values[key] = d.get(key) if d.get(key) is not None else values[key]
    values.update(
        acc_enabled=bool(d.get("acc_enabled")), pwdcycle=str(d.get("pwdcycle") or "0"),
        coverpage_id=str(d.get("coverpage_id") or ""), faxperpageinbox=str(d.get("faxperpageinbox") or _default_inbox()),
        faxperpagearchive=str(d.get("faxperpagearchive") or _default_archive()),
        modemdevs=svc.get_modemdevs(), didrouting=svc.get_didrouting(), faxcats=svc.get_faxcats(),
        **{f: bool(d.get(f)) for f in FLAGS})
    return values


def _posted(post) -> dict:
    def number(name, allowed, default):
        value = (post.get(name) or "").strip()
        return value if value in allowed else default

    values = _blank()
    values.update(
        uid=(post.get("uid") or "").strip() or None, name=(post.get("name") or "").strip(),
        username=(post.get("username") or "").strip(), email=(post.get("email") or "").strip(), password=post.get("password") or "",
        acc_enabled=bool(post.get("acc_enabled")), pwdcycle=number("pwdcycle", ("0", "3", "6"), "0"),
        language=(post.get("language") or "en").strip(), coverpage_id=(post.get("coverpage_id") or "").strip(),
        audiofile=os.path.basename(post.get("audiofile") or ""),
        faxperpageinbox=number("faxperpageinbox", FAXES_PER_PAGE, _default_inbox()),
        faxperpagearchive=number("faxperpagearchive", FAXES_PER_PAGE, _default_archive()),
        modemdevs=post.getall("modemdevs[]"), didrouting=post.getall("didrouting[]"), faxcats=post.getall("faxcats[]"),
        **{f: bool(post.get(f)) for f in FLAGS})
    for key in ("from_company", "from_location", "from_voicenumber", "from_faxnumber", "user_tsi"):
        values[key] = (post.get(key) or "").strip()
    return values


def _mistakes(values: dict) -> list[str]:
    errors = []
    if not values["name"]:
        errors.append(_("You must enter a name."))
    if not values["username"]:
        errors.append(_("You must enter a username"))
    elif not re.fullmatch(r"[\.\w]+", values["username"]):
        errors.append(_("Non-alphanumeric characters are not allowed in username."))
    if not is_valid_email(values["email"]):
        errors.append(_("Please enter a valid e-mail address."))
    return errors


def _apply(svc: NFUserAccount, v: dict) -> None:
    """Copy the form onto the loaded account (the original's field list)."""
    svc.dbdata.update(
        name=v["name"], language=v["language"], is_admin=int(v["is_admin"]), superuser=int(v["superuser"]),
        can_del=int(v["can_del"]), any_modem=int(v["any_modem"]), acc_enabled=int(v["acc_enabled"]),
        pwd_reuse=int(v["pwd_reuse"]), audiofile=v["audiofile"] or None,
        coverpage_id=int(v["coverpage_id"]) if v["coverpage_id"].isdecimal() else None,
        from_company=v["from_company"], from_location=v["from_location"], from_voicenumber=v["from_voicenumber"],
        from_faxnumber=v["from_faxnumber"], user_tsi=v["user_tsi"], faxperpageinbox=int(v["faxperpageinbox"]),
        faxperpagearchive=int(v["faxperpagearchive"]))
    svc.set_modemdevs(v["modemdevs"])
    svc.set_didrouting(v["didrouting"])
    svc.set_faxcats(v["faxcats"])


def _mail_new_user(request, v: dict, password: str) -> None:
    body = str(_("Hello %(name)s,\n\nThis email contains your username and password to log into NamiFAX (%(url)s)\n\n"
             "Username - %(username)s\nPassword - %(password)s\n\nPlease do not respond to this message as it is "
             "automatically generated and is for information purposes only")) % {
        "name": v["name"], "url": request.host_url, "username": v["username"], "password": password}
    send_mail(v["email"], None, str(_("New User Details")), str(body), session=request.dbsession)


@view_config(route_name="admin_users", renderer="namifax:templates/admin_users.jinja2", permission="admin")
def admin_users_view(request):
    """The user list and the form to add or change one."""
    identity = request.identity or {"username": "admin", "is_admin": True, "superuser": True}
    svc = NFUserAccount(db=request.dbsession)
    errors: list[str] = []
    saved = False
    values = _blank()

    if request.method == "POST" and request.POST.get("unlock_uid"):
        return _unlock(request, svc)

    if request.method == "POST":
        values = _posted(request.POST)
        if request.POST.get("delete") and values["uid"]:
            return HTTPFound(location=request.route_url("admin_user_delete", _query={"uid": values["uid"]}))
        errors = _mistakes(values)
        if not errors and values["uid"]:
            errors, saved = _edit(request, svc, values)
        elif not errors:
            errors, saved = _create(request, svc, values)
        if saved:
            values = _from_account(svc)
    else:
        uid = (request.params.get("uid") or "").strip()
        if uid.isdecimal() and svc.load(int(uid)):
            values = _from_account(svc)

    users = get_all_admin_users(request.dbsession)
    locked = LoginThrottle(request.dbsession).locked_accounts([str(u["username"]) for u in users if u.get("username")])
    for user in users:
        user["locked"] = str(user.get("username")) in locked
    return {"title": "NamiFAX - Admin - Users", "current_user": identity, "active_tab": "admin", "active_admin": "users",
            "csrf_token": request.session.get_csrf_token(), "users": users, "values": values, "errors": errors, "saved": saved, "choices": _choices(request),
            "max_username": settings.max_username_size(), "max_email": settings.max_email_size(),
            "max_password": settings.max_passwd_size()}


def _unlock(request, svc: NFUserAccount):
    """Lift the lock that too many wrong passwords put on an account (only an administrator can; the page is admin-only)."""
    if not check_csrf_token(request, raises=False):
        request.session.flash(str(_("The form has expired. Please try again.")), "error")
        return HTTPFound(location=request.route_url("admin_users"))
    uid = (request.POST.get("unlock_uid") or "").strip()
    if uid.isdecimal() and svc.load(int(uid)):
        username = str(svc.dbdata.get("username") or "")
        if LoginThrottle(request.dbsession).unlock(username):
            svc._log(f"Account {username} unlocked by {(request.identity or {}).get('username', 'admin')}")
    return HTTPFound(location=request.route_url("admin_users"))


def _edit(request, svc: NFUserAccount, v: dict):
    errors = []
    if not svc.load(int(v["uid"])):
        return [_("The user does not exist.")], False
    previous = str(svc.dbdata.get("username") or "")
    if not svc.set_username(v["username"]):
        errors.append(svc.get_error())
    elif previous and previous != v["username"]:
        hylafax_users.remove_user(previous)                       # the old name no longer belongs to this account
    if not svc.set_email(v["email"]):
        errors.append(svc.get_error())
    _apply(svc, v)
    if str(svc.dbdata.get("pwdcycle") or 0) != v["pwdcycle"]:
        svc.dbdata["pwdcycle"] = int(v["pwdcycle"])
        svc.dbdata["pwdexpire"] = _expiry(v["pwdcycle"])
    if not v["acc_enabled"]:
        svc.dbdata["wasreset"] = 1                              # a new password is needed when the account is enabled again
    if not errors:
        svc.update()
        if v["password"] and not svc.change_password(v["password"]):
            errors.append(svc.get_error())
    return errors, not errors


def _create(request, svc: NFUserAccount, v: dict):
    details = {k: v[k] for k in ("name", "username", "email", "password", "language", "from_company", "from_location",
                                 "from_voicenumber", "from_faxnumber", "user_tsi", "audiofile")}
    details.update(pwdcycle=v["pwdcycle"], acc_enabled=1, **{f: int(v[f]) for f in FLAGS})
    details.update(faxperpageinbox=int(v["faxperpageinbox"]), faxperpagearchive=int(v["faxperpagearchive"]),
                   coverpage_id=int(v["coverpage_id"]) if v["coverpage_id"].isdecimal() else None)
    if not svc.create(details):
        return [svc.get_error()], False
    svc.set_modemdevs(v["modemdevs"])
    svc.set_didrouting(v["didrouting"])
    svc.set_faxcats(v["faxcats"])
    svc.update()
    if svc.generated_password:
        _mail_new_user(request, v, svc.generated_password)
    return [], True


@view_config(route_name="admin_user_delete", renderer="namifax:templates/admin_user_delete.jinja2", permission="admin")
def admin_user_delete_view(request):
    """Ask before an account is deleted (the original deluser.php); yourself and the last superuser stay."""
    params = request.POST if request.method == "POST" else request.params
    uid = (params.get("uid") or "").strip()
    svc = NFUserAccount(db=request.dbsession)
    if not uid.isdecimal() or not svc.load(int(uid)):
        return HTTPFound(location=request.route_url("admin_users"))
    error = None
    if request.method == "POST":
        me = (request.identity or {}).get("username")
        superusers = [u for u in svc.list_accounts() if u.get("superuser")]
        if svc.dbdata.get("username") == me:
            error = _("You cannot delete your own account.")
        elif svc.dbdata.get("superuser") and len(superusers) <= 1:
            error = _("You cannot delete the last superuser.")
        else:
            svc.remove(int(uid))
            return HTTPFound(location=request.route_url("admin_users"))
    return {"title": "NamiFAX - Admin - Delete User", "current_user": request.identity, "active_tab": "admin",
            "active_admin": "users", "uid": uid, "user_name": svc.dbdata.get("name"), "error": error}
