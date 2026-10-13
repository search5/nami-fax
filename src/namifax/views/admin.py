"""NamiFAX Admin View Controllers protected by permission='admin'."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode

from pyramid.httpexceptions import HTTPFound, HTTPForbidden
from pyramid.view import view_config

from namifax.services.barcode import BarcodeRouting
from namifax.services.categories import FaxPDFCategory
from namifax.services.covers import Covers
from namifax.services.did import DIDRouting
from namifax.services.dynconf import DynamicConfig
from namifax.services import hylafax_info
from namifax.i18n import _

def get_all_admin_users(db: Any = None) -> list[dict[str, Any]]:
    """Retrieve users directly from database."""
    try:
        from namifax.services.user_account import NFUserAccount
        svc = NFUserAccount(db=db)
        rows = svc.list_accounts()
        if rows:
            users_list = []
            for r in rows:
                users_list.append({
                    "uid": r.get("uid"),
                    "name": r.get("name") or r.get("username"),
                    "username": r.get("username"),
                    "email": r.get("email"),
                    "superuser": bool(r.get("superuser")),
                    "is_admin": bool(r.get("is_admin") or r.get("superuser")),
                    "last_login": r.get("last_login") or "Never",
                    "last_ip": r.get("last_ip") or "-",
                    "can_del": bool(r.get("can_del")),
                    "any_modem": bool(r.get("any_modem", 1)),
                })
            # Ensure admin user is first if present
            users_list.sort(key=lambda u: 0 if u.get("uid") == 1 else 1)
            return users_list
    except Exception:
        pass
    return []


def get_all_admin_modems(db: Any = None) -> list[dict[str, Any]]:
    """Retrieve modems directly from database."""
    try:
        from namifax.services.modem import FaxModem
        svc = FaxModem(db=db)
        rows = svc.list_all()
        if rows:
            modems_list = []
            for r in rows:
                device = r.get("device")
                svc.load_device(device)
                modem_stat = svc.get_status()
                status_text = modem_stat.get("status") if isinstance(modem_stat, dict) else str(modem_stat)
                modems_list.append({
                    "devid": r.get("devid"),
                    "device": device,
                    "alias": r.get("alias"),
                    "contact": r.get("contact") or "",
                    "printer": r.get("printer") or "",
                    "faxcatid": r.get("faxcatid"),
                    "status": status_text or "Running and idle",
                    "status_class": modem_stat.get("class") if isinstance(modem_stat, dict) else "",
                })
            return modems_list
    except Exception:
        pass
    return []


@view_config(route_name="admin", renderer="namifax:templates/admin.jinja2", permission="admin")
def admin_dashboard_view(request):
    """Admin Dashboard and server overview."""
    identity = request.identity or {"username": "admin", "is_admin": True, "superuser": True}
    users = get_all_admin_users(request.dbsession)
    modems = get_all_admin_modems(request.dbsession)

    if "Authorization" in request.headers or "application/json" in request.headers.get("Accept", ""):
        from pyramid.response import Response
        return Response(json_body={"modems": modems, "users": users}, content_type="application/json")

    return {
        "title": "NamiFAX - Admin Control Panel",
        "current_user": identity,
        "active_tab": "admin",
        "active_admin": "dashboard",
        "users": users,
        "total_users": len(users),
        "modems": modems,
        "hylafax_version": hylafax_info.version(),
    }


@view_config(route_name="admin_modems", renderer="namifax:templates/admin_modems.jinja2", permission="admin")
def admin_modems_view(request):
    """Fax modem lines: create, save and delete, with a category and a message for each outcome (the original conf_modems)."""
    identity = request.identity or {"username": "admin", "is_admin": True, "superuser": True}
    from namifax.services.modem import FaxModem

    fm = FaxModem(db=request.dbsession)
    message = error = None
    selected_devid = None

    if request.method == "POST":
        post = request.POST
        device, alias = (post.get("device") or "").strip(), (post.get("alias") or "").strip()
        contact, printer = (post.get("contact") or "").strip(), (post.get("printer") or "").strip()
        faxcat = (post.get("faxcatid") or "").strip()
        faxcatid = int(faxcat) if faxcat.isdecimal() else None
        devid = (post.get("devid") or "").strip()
        if devid.isdecimal():
            selected_devid = int(devid)
            if post.get("delete"):
                if fm.delete_device(int(devid)):
                    message, selected_devid = _("The modem was deleted"), None
                else:
                    error = fm.get_error()
            elif post.get("save"):
                if not alias:
                    error = _("You must enter an alias")
                elif fm.load_device((post.get("device2") or device).strip()):
                    fm.set_contact(contact)
                    fm.set_printer(printer)
                    fm.set_faxcatid(faxcatid)
                    fm.set_alias(alias)
                    message = _("The modem was updated")
                else:
                    error = fm.get_error()
        elif not device:
            error = _("You must enter a device name")
        elif not alias:
            error = _("You must enter an alias")
        elif fm.load_device(device):
            error = _("This modem already exists")
        elif fm.create(device=device, alias=alias, contact=contact, printer=printer, faxcatid=faxcatid):
            message = _("The modem was created")
        else:
            error = fm.get_error()
    else:
        raw = (request.params.get("devid") or "").strip()
        selected_devid = int(raw) if raw.isdecimal() else None
        if not selected_devid and request.params.get("device"):
            if fm.load_device(request.params["device"]):
                selected_devid = fm.devid

    modems = get_all_admin_modems(request.dbsession)
    selected = next((m for m in modems if m.get("devid") == selected_devid), None) if selected_devid else None
    categories = [(str(c["catid"]), c["name"]) for c in FaxPDFCategory(db=request.dbsession).get_categories() or []]
    return {
        "title": "NamiFAX - Admin - Modems", "current_user": identity, "active_tab": "admin", "active_admin": "modems",
        "modems": modems, "categories": categories, "message": message, "error": error,
        "selected_modem": selected or {"device": "", "alias": "", "contact": "", "printer": "", "faxcatid": None},
    }


@view_config(route_name="admin_routing_did", renderer="namifax:templates/admin_routing_did.jinja2", permission="admin")
@view_config(route_name="admin_did", renderer="namifax:templates/admin_routing_did.jinja2", permission="admin")
def admin_routing_did_view(request):
    """Admin DID inbound routing configuration and full CRUD management."""
    identity = request.identity or {"username": "admin", "is_admin": True, "superuser": True}
    did = DIDRouting(db=request.dbsession)
    fc = FaxPDFCategory(db=request.dbsession)
    message = None
    error = None

    didr_id_param = request.params.get("didr_id")
    selected_id = int(didr_id_param) if didr_id_param and str(didr_id_param).isdecimal() else None

    if request.method == "POST":
        route_code = request.params.get("route", "").strip()
        alias = request.params.get("alias", "").strip()
        contact = request.params.get("contact", "").strip()
        printer = request.params.get("printer", "").strip()
        cat_param = request.params.get("faxcatid")
        faxcatid = int(cat_param) if cat_param and str(cat_param).isdecimal() else None

        if request.params.get("delete") and selected_id:
            try:
                did.delete_route(selected_id)
            except Exception:
                pass
            message = "DID routing rule deleted successfully"
            selected_id = None
        elif selected_id and (request.params.get("save") or not request.params.get("create")):
            if not route_code or not alias:
                error = "Route Code and Alias are required"
            else:
                updated = False
                try:
                    if did.loadbyid(selected_id):
                        did.set_routecode(route_code)
                        did.set_alias(alias)
                        did.set_contact(contact)
                        did.set_printer(printer)
                        did.set_faxcatid(faxcatid)
                        updated = True
                except Exception:
                    pass
                if updated:
                    message = "DID routing rule updated successfully"
                else:
                    error = did.get_error() or "Failed to update DID route"
        elif route_code and alias:
            try:
                did.create(route_code, alias, contact=contact, printer=printer, faxcatid=faxcatid)
                message = "DID routing rule created successfully"
            except Exception:
                error = "Failed to create DID route"
        else:
            error = "Route Code and Alias are required"

    try:
        did_routes = did.list_all()
    except Exception:
        did_routes = []

    # Ensure route field compatibility
    for r in did_routes:
        if "route" not in r:
            r["route"] = r.get("routecode", "")

    selected_route = None
    if selected_id:
        try:
            if did.loadbyid(selected_id):
                selected_route = {
                    "didr_id": did.get_didr_id(),
                    "route": did.get_route(),
                    "alias": did.get_alias(),
                    "contact": did.get_contact() or "",
                    "printer": did.get_printer() or "",
                    "faxcatid": did.get_faxcatid(),
                }
        except Exception:
            pass
        if not selected_route:
            selected_route = next((r for r in did_routes if r.get("didr_id") == selected_id), None)

    try:
        categories = fc.list_all() if hasattr(fc, "list_all") else fc.get_categories()
    except Exception:
        categories = []

    return {
        "title": "NamiFAX - Admin - Configure DID Routing",
        "current_user": identity,
        "active_tab": "admin",
        "active_admin": "did",
        "did_routes": did_routes,
        "selected_route": selected_route,
        "categories": categories,
        "message": message,
        "error": error,
    }


def _months_of_the_year():
    return [_("January"), _("February"), _("March"), _("April"), _("May"), _("June"), _("July"), _("August"), _("September"),
            _("October"), _("November"), _("December")]


def count_syslogs(kw: str = "", day: str = "", month: str = "", year: str = "", session: Any = None) -> int:
    """How many system log events the filter matches."""
    if session is None:
        return 0
    from namifax.services.syslog import SysLogService

    return SysLogService(session).count(kw=kw, day=day, month=month, year=year)


def get_all_syslogs(kw: str = "", day: str = "", month: str = "", year: str = "", session: Any = None,
                    limit: int | None = None, offset: int = 0) -> list[dict[str, Any]]:
    """Retrieve system logs from the database through an ORM session (empty without a session)."""
    if session is None:
        return []
    from namifax.services.syslog import SysLogService

    return SysLogService(session).search(kw=kw, day=day, month=month, year=year, limit=limit, offset=offset)


SYSLOG_PER_PAGE = 100


@view_config(route_name="admin_system_logs", renderer="namifax:templates/admin_system_logs.jinja2", permission="admin")
@view_config(route_name="admin_syslog", renderer="namifax:templates/admin_system_logs.jinja2", permission="admin")
def admin_system_logs_view(request):
    """Admin system events and HylaFAX audit log viewer with keyword and date filter."""
    import datetime

    identity = request.identity or {"username": "admin", "is_admin": True, "superuser": True}
    searched = "_submit_check" in request.params
    today = datetime.date.today()
    if searched:
        kw = request.params.get("kw", "").strip()
        day, month, year = (request.params.get(n, "") for n in ("day", "month", "year"))
    else:                                                       # the original lists the day's events until a search is made
        kw, day, month, year = "", f"{today.day:02d}", f"{today.month:02d}", str(today.year)

    total = count_syslogs(kw=kw, day=day, month=month, year=year, session=request.dbsession)
    pages = max(1, -(-total // SYSLOG_PER_PAGE))
    raw = request.params.get("page", "1")
    page = min(max(int(raw) if raw.isdecimal() else 1, 1), pages)
    logs = get_all_syslogs(kw=kw, day=day, month=month, year=year, session=request.dbsession,
                           limit=SYSLOG_PER_PAGE, offset=(page - 1) * SYSLOG_PER_PAGE)
    pages = max(1, -(-total // SYSLOG_PER_PAGE))
    query = urlencode({"_submit_check": "1", "kw": kw, "day": day, "month": month, "year": year})

    return {
        "page": page, "pages": pages, "total": total, "pager_query": query,
        "title": "NamiFAX - Admin - System Logs",
        "current_user": identity,
        "active_tab": "admin",
        "active_admin": "syslog",
        "logs": logs,
        "kw": kw,
        "day": day,
        "month": month,
        "year": year,
        "days": [f"{d:02d}" for d in range(1, 32)],
        "months": [(f"{m:02d}", str(name)) for m, name in enumerate(_months_of_the_year(), 1)],
        "years": [str(y) for y in range(2004, today.year + 2)],
    }


@view_config(route_name="admin_covers", renderer="namifax:templates/admin_covers.jinja2", permission="admin")
def admin_covers_view(request):
    """Admin configure cover page templates and CRUD."""
    identity = request.identity or {"username": "admin", "is_admin": True, "superuser": True}
    cv = Covers(db=request.dbsession)
    message = None
    error = None

    cover_id_param = request.params.get("cover_id")
    selected_id = int(cover_id_param) if cover_id_param and str(cover_id_param).isdecimal() else None

    if request.method == "POST":
        cover_id = request.params.get("cover_id")
        cid = int(cover_id) if cover_id and str(cover_id).isdecimal() else selected_id

        if request.params.get("delete") and cid:
            if cv.delete_cover(cid):
                message = _("Cover page template removed successfully")
                selected_id = None
            else:
                error = cv.error or _("Failed to remove cover page template")
        elif cid and (request.params.get("save") or not request.params.get("create")):
            title = request.params.get("title", "").strip()
            if cv.load_by_id(cid):
                if title:
                    cv.set_title(title)
                filename = request.params.get("file", "").strip()
                if filename:
                    cv.set_file(filename)
                message = _("The cover page was updated")
            else:
                error = cv.error or _("Failed to update cover page template")
        elif request.params.get("create") or not cid:
            title = request.params.get("title", "").strip()
            filename = request.params.get("file", "").strip()
            if title and filename:
                if cv.create(title, filename):
                    message = _("Cover page template registered successfully")
                else:
                    error = cv.error
            else:
                error = _("Title and File are required")

    covers = cv.list_all() or []

    selected_cover = None
    if selected_id:
        try:
            if cv.load_by_id(selected_id):
                selected_cover = {
                    "cover_id": cv.get_cover_id(),
                    "title": cv.get_title(),
                    "file": cv.get_file(),
                }
        except Exception:
            pass
        if not selected_cover:
            selected_cover = next((c for c in covers if c.get("cover_id") == selected_id), None)

    return {
        "title": "NamiFAX - Admin - Configure Cover Pages",
        "current_user": identity,
        "active_tab": "admin",
        "active_admin": "covers",
        "covers": covers,
        "selected_cover": selected_cover,
        "supported_tags": [
            {"tag": "TO_COMPANY", "desc": "Recipient company name"},
            {"tag": "TO_LOCATION", "desc": "Recipient department / location"},
            {"tag": "TO_VOICENUMBER", "desc": "Recipient telephone number"},
            {"tag": "TO_FAXNUMBER", "desc": "Recipient fax number"},
            {"tag": "TO_PERSON", "desc": "Recipient person name"},
            {"tag": "FROM_COMPANY", "desc": "Sender company name"},
            {"tag": "FROM_LOCATION", "desc": "Sender location"},
            {"tag": "FROM_VOICENUMBER", "desc": "Sender telephone number"},
            {"tag": "FROM_FAXNUMBER", "desc": "Sender fax number"},
            {"tag": "FROM_PERSON", "desc": "Sender name"},
            {"tag": "PAGECOUNT", "desc": "Total page count"},
            {"tag": "DATE_TIME", "desc": "Cover creation timestamp"},
            {"tag": "REGARDING", "desc": "Subject / Regarding"},
            {"tag": "COMMENTS", "desc": "Cover note comments"},
        ],
        "message": message,
        "error": error,
    }


@view_config(route_name="admin_categories", renderer="namifax:templates/admin_categories.jinja2", permission="admin")
def admin_categories_view(request):
    """Admin fax categories manager."""
    identity = request.identity or {"username": "admin", "is_admin": True, "superuser": True}
    fc = FaxPDFCategory(db=request.dbsession)
    message = None
    error = None

    catid_param = request.params.get("catid")
    selected_id = int(catid_param) if catid_param and str(catid_param).isdecimal() else None

    if request.method == "POST":
        catid = request.params.get("catid")
        cid = int(catid) if catid and str(catid).isdecimal() else selected_id

        if request.params.get("delete") and cid:
            if fc.delete_category(cid):
                from namifax.services.archive_base import FaxPDFArchive
                FaxPDFArchive(db=request.dbsession).remove_category(cid)         # the faxes that had it no longer point to it
                message = "Fax category deleted successfully"
                selected_id = None
            else:
                error = fc.error or "Failed to delete category"
        elif cid and (request.params.get("save") or not request.params.get("create")):
            name = request.params.get("name", "").strip()
            if name:
                if fc.set_name(name, cid):
                    message = "Fax category updated successfully"
                else:
                    error = fc.error or "Failed to update category"
            else:
                error = "Category Name is required"
        elif request.params.get("create") or not cid:
            name = request.params.get("name", "").strip()
            if name:
                if fc.create(name):
                    message = "Fax category created successfully"
                else:
                    error = fc.error
            else:
                error = "Category Name is required"

    categories = fc.get_categories() or []

    selected_category = None
    if selected_id:
        try:
            name_val = fc.get_name(selected_id)
            if name_val:
                selected_category = {"catid": selected_id, "name": name_val}
        except Exception:
            pass
        if not selected_category:
            selected_category = next((c for c in categories if c.get("catid") == selected_id), None)

    return {
        "title": "NamiFAX - Admin - Fax Categories",
        "current_user": identity,
        "active_tab": "admin",
        "active_admin": "categories",
        "categories": categories,
        "selected_category": selected_category,
        "message": message,
        "error": error,
    }


@view_config(route_name="admin_barcodes", renderer="namifax:templates/admin_barcodes.jinja2", permission="admin")
def admin_barcodes_view(request):
    """Admin configure barcode routing and CRUD."""
    identity = request.identity or {"username": "admin", "is_admin": True, "superuser": True}
    bc = BarcodeRouting(db=request.dbsession)
    message = None
    error = None

    barcode_id_param = request.params.get("barcode_id")
    selected_id = int(barcode_id_param) if barcode_id_param and str(barcode_id_param).isdecimal() else None

    if request.method == "POST":
        barcode = request.params.get("barcode", "").strip()
        alias = request.params.get("alias", "").strip()
        contact = request.params.get("contact", "").strip()
        printer = request.params.get("printer", "").strip()
        faxcat = (request.params.get("faxcatid") or "").strip()
        faxcatid = int(faxcat) if faxcat.isdecimal() else None
        barcode_id = request.params.get("barcode_id")
        bid = int(barcode_id) if barcode_id and str(barcode_id).isdecimal() else selected_id

        if request.params.get("delete") and bid:
            if bc.delete_route(bid):
                message = "Barcode routing rule deleted"
                selected_id = None
            else:
                error = bc.error or "Failed to delete barcode rule"
        elif bid and (request.params.get("save") or not request.params.get("create")):
            if bc.loadbyid(bid):
                bc.set_barcode(barcode)
                bc.set_alias(alias)
                bc.set_contact(contact)
                bc.set_printer(printer)
                bc.set_faxcatid(faxcatid)
                message = "Barcode routing rule updated"
            else:
                error = bc.error or "Failed to update barcode route"
        elif request.params.get("create") or not bid:
            if barcode and alias and bc.create(barcode, alias=alias, contact=contact, printer=printer, faxcatid=faxcatid):
                message = "Barcode routing rule created"
            else:
                error = bc.error or "Barcode and Alias are required"

    barcodes = bc.list_all() or []

    selected_barcode = None
    if selected_id:
        try:
            if bc.loadbyid(selected_id):
                selected_barcode = {
                    "barcode_id": bc.get_barcode_id(),
                    "barcode": bc.get_barcode(),
                    "alias": bc.get_alias(),
                    "contact": bc.get_contact() or "",
                    "printer": bc.get_printer() or "",
                    "faxcatid": bc.faxcatid,
                }
        except Exception:
            pass
        if not selected_barcode:
            selected_barcode = next((b for b in barcodes if b.get("barcode_id") == selected_id), None)

    return {
        "title": "NamiFAX - Admin - Configure Barcode Routing",
        "current_user": identity,
        "active_tab": "admin",
        "active_admin": "barcodes",
        "barcodes": barcodes,
        "selected_barcode": selected_barcode,
        "categories": [(str(c["catid"]), c["name"]) for c in FaxPDFCategory(db=request.dbsession).get_categories() or []],
        "message": message,
        "error": error,
    }


@view_config(route_name="admin_dynconf", renderer="namifax:templates/admin_dynconf.jinja2", permission="admin")
def admin_dynconf_view(request):
    """Admin dynamic configuration / blacklist."""
    identity = request.identity or {"username": "admin", "is_admin": True, "superuser": True}
    dc = DynamicConfig(db=request.dbsession)
    message = None
    error = None

    dynconf_id_param = request.params.get("dynconf_id")
    selected_id = int(dynconf_id_param) if dynconf_id_param and str(dynconf_id_param).isdecimal() else None

    if request.method == "POST":
        dynconf_id = request.params.get("dynconf_id")
        cid = int(dynconf_id) if dynconf_id and str(dynconf_id).isdecimal() else selected_id

        if request.params.get("delete") and cid:
            if dc.remove(cid):
                message = "Blacklist rule removed"
                selected_id = None
            else:
                error = dc.get_error() or "Failed to remove blacklist rule"
        elif cid and (request.params.get("save") or not request.params.get("create")):
            callid = request.params.get("callid", "").strip()
            device = request.params.get("device", "").strip() or None
            if callid:
                if dc.load_rule(cid):
                    if dc.save_rule(device, callid):
                        message = "Blacklist rule updated"
                    else:
                        error = dc.get_error() or "Failed to update blacklist rule"
                else:
                    error = dc.get_error() or "Rule not found"
            else:
                error = "Caller ID is required"
        elif request.params.get("create") or not cid:
            callid = request.params.get("callid", "").strip()
            device = request.params.get("device", "").strip() or None
            if callid:
                if dc.create(device, callid):
                    message = "Blacklist rule created"
                else:
                    error = dc.get_error()
            else:
                error = "Caller ID is required"

    rules = dc.list_rules() or []

    selected_rule = None
    if selected_id:
        try:
            if dc.load_rule(selected_id):
                selected_rule = {
                    "dynconf_id": dc.get_dynconf_id(),
                    "callid": dc.get_callid(),
                    "device": dc.get_device(),
                }
        except Exception:
            pass
        if not selected_rule:
            selected_rule = next((r for r in rules if r.get("dynconf_id") == selected_id), None)

    try:
        from namifax.services.modem import FaxModem
        fm = FaxModem(db=request.dbsession)
        modems = []
        for device in fm.get_modems() or []:
            modems.append((device, f"{fm.get_alias()} ({device})" if fm.load_device(device) and fm.get_alias() else device))
    except Exception:
        modems = []

    return {
        "title": "NamiFAX - Admin - Dynamic Configuration",
        "current_user": identity,
        "active_tab": "admin",
        "active_admin": "dynconf",
        "dynconf_rules": rules,
        "selected_rule": selected_rule,
        "modems": modems,
        "message": message,
        "error": error,
    }


@view_config(route_name="admin_fax2email", renderer="namifax:templates/admin_fax2email.jinja2", permission="admin")
def admin_fax2email_view(request):
    """Admin > Fax to Email: forwarding address, printer and category for each fax number of a company.

    Port of the original admin/fax2email.php + fax2email_edit.php. Companies and numbers are created in the address
    book; this page only sets how the faxes received on a number are routed.
    """
    import re as _re

    from namifax.common.validators import is_valid_email
    from namifax.services.addressbook import NFAddressBook
    from namifax.services.categories import FaxPDFCategory

    identity = request.identity or {"username": "admin", "is_admin": True, "superuser": True}
    ab = NFAddressBook(db=request.dbsession)
    message = None
    error = None

    params = request.POST if request.method == "POST" else request.params
    raw_id = params.get("abook_id") or params.get("c_id") or params.get("id")
    selected_id = int(raw_id) if raw_id and str(raw_id).isdecimal() else None

    def bad_address(value: str) -> bool:
        parts = [p.strip() for p in _re.split(r"[;,]", value) if p.strip()]
        return any(not is_valid_email(p) for p in parts)

    if request.method == "POST" and selected_id:
        if not ab.loadbycid(selected_id):
            error = _("The company does not exist.")
            selected_id = None
        elif params.get("delete"):
            if ab.delete_company(selected_id):
                message = _("The company and its fax numbers were deleted.")
                selected_id = None
            else:
                error = ab.get_error()
        else:
            company = params.get("company", "").strip()
            own = {int(n["abookfax_id"]): n for n in ab.get_faxnums()}
            ids = params.getall("abookfax_id")
            columns = {key: params.getall(key) for key in ("email", "printer", "faxcatid")}
            changes = []
            for i, raw in enumerate(ids):
                if not raw.isdecimal() or int(raw) not in own:
                    continue                                   # not a number of this company: never touched
                current = own[int(raw)]
                email = (columns["email"][i] if i < len(columns["email"]) else "").strip()
                printer = (columns["printer"][i] if i < len(columns["printer"]) else "").strip()
                cat = (columns["faxcatid"][i] if i < len(columns["faxcatid"]) else "").strip()
                if email != (current.get("email") or "") and bad_address(email):
                    error = _("Please enter a valid e-mail address.") + f" ({email})"
                    break
                changes.append((int(raw), {"email": email, "printer": printer, "faxcatid": int(cat) if cat.isdecimal() else None}))
            if not company and not error:
                error = _("You must enter a company name")
            if not error:
                if ab.set_company(company):
                    for number_id, data in changes:
                        if ab.loadbyfaxnumid(number_id):
                            ab.save_settings(data)
                    message = _("Fax to Email settings saved")
                else:
                    error = ab.get_error()

    numbers_by_company = ab.numbers_by_company()
    companies = []
    for c in ab.get_companies(with_reserved=True):
        own = numbers_by_company.get(c.get("abook_id"), [])
        companies.append({"abook_id": c.get("abook_id"), "c_id": c.get("abook_id"), "company": c.get("company"),
                          "numbers": len(own),
                          "email": next((n.get("email") for n in own if n.get("email")), "") or "",
                          "printer": next((n.get("printer") for n in own if n.get("printer")), "") or ""})

    selected_company = None
    if selected_id and ab.loadbycid(selected_id):
        selected_company = {"abook_id": selected_id, "c_id": selected_id, "company": ab.get_company(),
                            "numbers": ab.get_faxnums()}

    categories = FaxPDFCategory(db=request.dbsession).get_categories() or []
    return {
        "title": "NamiFAX - Admin - Fax to Email",
        "current_user": identity,
        "active_tab": "admin",
        "active_admin": "fax2email",
        "fax2emails": companies,
        "selected_company": selected_company,
        "categories": categories,
        "message": message,
        "error": error,
    }


@view_config(route_name="admin_system_func", renderer="namifax:templates/admin_sysfunc.jinja2", permission="admin")
@view_config(route_name="admin_sysfunc", renderer="namifax:templates/admin_sysfunc.jinja2", permission="admin")
def admin_system_func_view(request):
    """System functions: reboot, shut down, download the fax archive or a database dump (the original system_func.php)."""
    import datetime
    import shutil
    import subprocess
    import tempfile

    from pyramid.response import FileIter, Response

    from namifax.services import sysfunc

    identity = request.identity or {"username": "admin", "is_admin": True, "superuser": True}
    message = error = None

    def download(path: str, name: str, content_type: str):
        """Send a temporary file and remove it afterwards."""
        def chunks():
            try:
                yield from FileIter(open(path, "rb"))
            finally:
                os.unlink(path)

        response = Response(content_type=content_type, app_iter=chunks(), content_length=os.path.getsize(path))
        response.headers["Content-Disposition"] = f'attachment; filename="{name}"'
        return response

    if request.method == "POST":
        post = request.POST
        today = datetime.date.today().strftime("%Y%m%d")
        if post.get("reboot") or post.get("shutdown"):
            command = sysfunc.reboot_command() if post.get("reboot") else sysfunc.shutdown_command()
            try:
                subprocess.Popen(command)
                message = _("The system is rebooting. Please wait...") if post.get("reboot") else \
                    _("The system is shutting down. Please wait...")
            except OSError as exc:
                error = f"{_('The command could not be run')}: {exc}"
        elif post.get("download_ar"):
            handle, path = tempfile.mkstemp(prefix="namifax-archive-", suffix=".tar.gz")
            os.close(handle)
            if sysfunc.write_archive(path):
                return download(path, f"avantfax-archive-{today}.tar.gz", "application/gzip")
            os.unlink(path)
            error = _("There is no fax archive folder to download.")
        elif post.get("download_db"):
            handle, path = tempfile.mkstemp(prefix="namifax-schema-", suffix=".sql.gz")
            os.close(handle)
            url = request.dbsession.get_bind().url
            try:
                if sysfunc.is_sqlite(url):
                    sysfunc.write_sqlite_dump(url.database, path)
                else:
                    import gzip

                    argv, env = sysfunc.dump_command(url)
                    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, env=env)
                    with gzip.open(path, "wb", compresslevel=9) as target:
                        shutil.copyfileobj(proc.stdout, target)
                    if proc.wait() != 0:
                        raise OSError(f"{argv[0]} exited with {proc.returncode}")
                return download(path, f"avantfax-schema-{today}.sql.gz", "application/gzip")
            except (OSError, ValueError) as exc:
                os.unlink(path)
                error = f"{_('The database dump could not be made')}: {exc}"

    return {
        "title": "NamiFAX - Admin - System Functions",
        "current_user": identity,
        "active_tab": "admin",
        "active_admin": "sysfunc",
        "daemons": sysfunc.daemon_status(),
        "message": message,
        "error": error,
    }


@view_config(route_name="admin_smtp", renderer="namifax:templates/admin_smtp.jinja2", permission="admin")
def admin_smtp_view(request):
    """Admin SMTP Gateway settings and connectivity diagnostics view."""
    identity = getattr(request, "identity", None)
    session = getattr(request, "session", {})
    is_admin = False
    if identity:
        is_admin = bool(identity.get("superuser") or identity.get("is_superadmin"))
    elif session:
        is_admin = bool(session.get("is_superadmin") or session.get("superuser"))

    if not is_admin:
        raise HTTPForbidden(_("Access denied. Superadmin permission required."))

    from namifax.services.smtp_settings import SmtpSettingsService, SmtpConfig
    service = SmtpSettingsService(request.dbsession)

    message = None
    error = None
    test_result = None

    params = dict(getattr(request, "POST", {}))
    if hasattr(request, "params") and request.params:
        params.update(request.params)

    if request.method == "POST":
        action = params.get("action")
        if action == "save":
            try:
                service.save_settings(params)
                message = _("SMTP Gateway settings saved successfully.")
                loc = "/admin/smtp"
                if hasattr(request, "route_url"):
                    try:
                        loc = request.route_url("admin_smtp")
                    except Exception:
                        pass
                return HTTPFound(location=loc)
            except Exception as exc:
                error = str(exc)
        elif action == "test":
            target_email = params.get("test_email", "admin@localhost")
            cfg = SmtpConfig(
                smtp_host=params.get("smtp_host", "localhost"),
                smtp_port=int(params.get("smtp_port", 25) or 25),
                smtp_security=params.get("smtp_security", "NONE"),
                smtp_auth=params.get("smtp_auth") in ("on", "1", "true", True),
                smtp_username=params.get("smtp_username"),
                smtp_password=params.get("smtp_password"),
                from_email=params.get("from_email", "root@localhost"),
                from_name=params.get("from_name", "NamiFAX"),
            )
            res = service.test_connection(target_email, cfg)
            test_result = {
                "success": res.success,
                "message": res.message,
                "details": res.details,
            }

    config = service.get_settings()
    return {
        "title": "NamiFAX - Admin - SMTP Gateway",
        "current_user": identity or {"username": session.get("username", "admin"), "is_admin": True, "superuser": True},
        "active_tab": "admin",
        "active_admin": "smtp",
        "config": config,
        "message": message,
        "error": error,
        "test_result": test_result,
    }


@view_config(route_name="admin_printers", renderer="namifax:templates/admin_printers.jinja2", permission="admin")
def admin_printers_view(request):
    """Network Printer management console."""
    identity = getattr(request, "identity", None)
    session = getattr(request, "session", {})
    is_admin = False
    if identity:
        is_admin = bool(identity.get("superuser") or identity.get("is_superadmin"))
    elif session:
        is_admin = bool(session.get("is_superadmin") or session.get("superuser"))

    if not is_admin:
        raise HTTPForbidden(_("Access denied. Superadmin permission required."))

    from namifax.services.printer import NetworkPrinterService
    service = NetworkPrinterService(request.dbsession)

    message = None
    error = None
    test_result = None

    if request.method == "POST":
        action = request.params.get("action", "")
        if action == "add":
            name = request.params.get("name", "").strip()
            protocol = request.params.get("protocol", "RAW").strip()
            host = request.params.get("host", "").strip()
            port = int(request.params.get("port", 9100) or 9100)
            queue_name = request.params.get("queue_name", "").strip() or None
            description = request.params.get("description", "").strip() or None
            if not name or not host:
                error = _("Printer name and host are required.")
            else:
                try:
                    service.create_printer(name, protocol, host, port, queue_name, description)
                    message = _("Network printer registered successfully.")
                except Exception as exc:
                    error = f"Error creating printer: {exc}"
        elif action == "delete":
            printer_id = int(request.params.get("printer_id", 0))
            if printer_id:
                service.delete_printer(printer_id)
                message = _("Printer deleted successfully.")
        elif action == "test":
            host = request.params.get("test_host", "").strip()
            port = int(request.params.get("test_port", 9100) or 9100)
            if host:
                res = service.send_raw_print(host, port, b"NamiFAX Direct Print Test OK\r\n\x0c")
                test_result = res
                if res.get("success"):
                    message = res.get("message")
                else:
                    error = res.get("message")

    printers = service.list_printers()

    return {
        "current_admin_tab": "printers",
        "current_user": identity or {"username": session.get("username", "admin"), "is_admin": True, "superuser": True},
        "active_tab": "admin",
        "active_admin": "printers",
        "printers": printers,
        "message": message,
        "error": error,
        "test_result": test_result,
    }


@view_config(route_name="admin_storage", renderer="namifax:templates/admin_storage.jinja2", permission="admin")
def admin_storage_view(request):
    """Enterprise Storage & Cloud Lifecycle management console."""
    identity = getattr(request, "identity", None)
    session = getattr(request, "session", {})
    is_admin = False
    if identity:
        is_admin = bool(identity.get("superuser") or identity.get("is_superadmin"))
    elif session:
        is_admin = bool(session.get("is_superadmin") or session.get("superuser"))

    if not is_admin:
        raise HTTPForbidden(_("Access denied. Superadmin permission required."))

    from namifax.services.cloud_storage import StorageConfig, CloudStorageManager
    from namifax.services.storage_lifecycle import StorageLifecyclePolicy, StorageLifecycleService
    from namifax.common.secretbox import SecretKeyError
    from namifax.services.system_config import SystemConfigService

    config_store = SystemConfigService(request.dbsession)
    get_cfg, set_cfg = config_store.get, config_store.set

    message = None
    error = None
    test_result = None

    if request.method == "POST":
        action = request.params.get("action", "")
        if action == "save_lifecycle":
            purge_tiff = int(request.params.get("purge_tiff_after_days", 7) or 7)
            retention = int(request.params.get("full_retention_days", 365) or 365)
            remote_sync = "remote_sync_delete" in request.params
            set_cfg("storage_purge_tiff_days", str(purge_tiff))
            set_cfg("storage_retention_days", str(retention))
            set_cfg("storage_remote_sync_delete", "1" if remote_sync else "0")
            message = _("Lifecycle policy saved successfully.")
        elif action == "save_cloud":
            stype = request.params.get("storage_type", "LOCAL").strip()
            endpoint = request.params.get("endpoint_url", "").strip()
            region = request.params.get("region_name", "").strip()
            bucket = request.params.get("bucket_name", "").strip()
            access_key = request.params.get("access_key", "").strip()
            secret_key = request.params.get("secret_key", "").strip()
            prefix = request.params.get("prefix", "").strip()

            set_cfg("cloud_storage_type", stype)
            set_cfg("cloud_endpoint_url", endpoint)
            set_cfg("cloud_region_name", region)
            set_cfg("cloud_bucket_name", bucket)
            set_cfg("cloud_access_key", access_key)
            try:
                if secret_key:
                    config_store.set_secret("cloud_secret_key", secret_key)
                set_cfg("cloud_prefix", prefix)
                message = _("Cloud storage configuration saved successfully.")
            except SecretKeyError as exc:
                error = str(exc)
        elif action == "test_cloud":
            stype = request.params.get("storage_type", "LOCAL").strip()
            endpoint = request.params.get("endpoint_url", "").strip() or None
            region = request.params.get("region_name", "").strip() or None
            bucket = request.params.get("bucket_name", "").strip() or None
            access_key = request.params.get("access_key", "").strip() or None
            secret_key = request.params.get("secret_key", "").strip() or config_store.get_secret("cloud_secret_key", "")
            prefix = request.params.get("prefix", "").strip()

            cfg = StorageConfig(
                storage_type=stype,
                endpoint_url=endpoint,
                region_name=region,
                bucket_name=bucket,
                access_key=access_key,
                secret_key=secret_key,
                prefix=prefix,
            )
            provider = CloudStorageManager.get_provider(cfg)
            res = provider.test_connection()
            test_result = res
            if res.get("success"):
                message = res.get("message")
            else:
                error = res.get("message")

    # Load current configs
    lifecycle = {
        "purge_tiff_after_days": int(get_cfg("storage_purge_tiff_days", "7")),
        "full_retention_days": int(get_cfg("storage_retention_days", "365")),
        "remote_sync_delete": get_cfg("storage_remote_sync_delete", "1") == "1",
    }
    cloud = {
        "storage_type": get_cfg("cloud_storage_type", "LOCAL"),
        "endpoint_url": get_cfg("cloud_endpoint_url", ""),
        "region_name": get_cfg("cloud_region_name", "us-east-1"),
        "bucket_name": get_cfg("cloud_bucket_name", ""),
        "access_key": get_cfg("cloud_access_key", ""),
        "has_secret_key": bool(get_cfg("cloud_secret_key", "")),
        "prefix": get_cfg("cloud_prefix", ""),
    }

    return {
        "current_admin_tab": "storage",
        "current_user": identity or {"username": session.get("username", "admin"), "is_admin": True, "superuser": True},
        "active_tab": "admin",
        "active_admin": "storage",
        "lifecycle": lifecycle,
        "cloud": cloud,
        "message": message,
        "error": error,
        "test_result": test_result,
    }


@view_config(route_name="admin_saml", renderer="namifax:templates/admin_saml.jinja2", permission="admin")
def admin_saml_view(request):
    """Enterprise SAML 2.0 Identity Provider configuration console."""
    identity = getattr(request, "identity", None)
    session = getattr(request, "session", {})
    is_admin = False
    if identity:
        is_admin = bool(identity.get("superuser") or identity.get("is_superadmin"))
    elif session:
        is_admin = bool(session.get("is_superadmin") or session.get("superuser"))

    if not is_admin:
        raise HTTPForbidden(_("Access denied. Superadmin permission required."))

    from namifax.services.saml import SAMLSettings, SAMLService
    from namifax.services.system_config import SystemConfigService

    config_store = SystemConfigService(request.dbsession)
    get_cfg, set_cfg = config_store.get, config_store.set

    message = None
    error = None

    if request.method == "POST":
        enabled = "enabled" in request.params
        idp_entity_id = request.params.get("idp_entity_id", "").strip()
        idp_sso_url = request.params.get("idp_sso_url", "").strip()
        idp_x509_cert = request.params.get("idp_x509_cert", "").strip()
        jit_provisioning = "jit_provisioning" in request.params
        default_role = request.params.get("default_role", "user").strip()

        set_cfg("saml_enabled", "1" if enabled else "0")
        set_cfg("saml_idp_entity_id", idp_entity_id)
        set_cfg("saml_idp_sso_url", idp_sso_url)
        set_cfg("saml_idp_x509_cert", idp_x509_cert)
        set_cfg("saml_jit_provisioning", "1" if jit_provisioning else "0")
        set_cfg("saml_default_role", default_role)
        set_cfg("saml_role_mapping", "1" if "saml_role_mapping" in request.params else "0")
        for key in ("role_attribute", "role_admin", "role_superuser", "role_can_del", "role_any_modem",
                    "attr_modems", "attr_faxcats", "attr_didroutes"):
            set_cfg(f"saml_{key}", request.params.get(f"saml_{key}", "").strip())
        message = _("SAML 2.0 configuration saved successfully.")

    settings = {
        "enabled": get_cfg("saml_enabled", "0") == "1",
        "idp_entity_id": get_cfg("saml_idp_entity_id", ""),
        "idp_sso_url": get_cfg("saml_idp_sso_url", ""),
        "idp_x509_cert": get_cfg("saml_idp_x509_cert", ""),
        "jit_provisioning": get_cfg("saml_jit_provisioning", "1") == "1",
        "default_role": get_cfg("saml_default_role", "user"),
        "role_mapping": get_cfg("saml_role_mapping", "0") == "1",
        "role_attribute": get_cfg("saml_role_attribute", "Role"),
        "role_admin": get_cfg("saml_role_admin", "namifax-admin"),
        "role_superuser": get_cfg("saml_role_superuser", "namifax-superuser"),
        "role_can_del": get_cfg("saml_role_can_del", "namifax-can-delete"),
        "role_any_modem": get_cfg("saml_role_any_modem", "namifax-any-modem"),
        "attr_modems": get_cfg("saml_attr_modems", ""),
        "attr_faxcats": get_cfg("saml_attr_faxcats", ""),
        "attr_didroutes": get_cfg("saml_attr_didroutes", ""),
        "sp_metadata_url": request.route_url("saml_metadata"),
        "sp_acs_url": request.route_url("saml_acs"),
    }

    return {
        "current_admin_tab": "saml",
        "current_user": identity or {"username": session.get("username", "admin"), "is_admin": True, "superuser": True},
        "active_tab": "admin",
        "active_admin": "saml",
        "saml": settings,
        "message": message,
        "error": error,
    }

