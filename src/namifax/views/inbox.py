"""NamiFAX Inbox and Fax Viewer Views."""

from __future__ import annotations

import os

from pyramid.csrf import check_csrf_token
from pyramid.httpexceptions import HTTPBadRequest, HTTPFound, HTTPMethodNotAllowed, HTTPNotFound
from pyramid.response import Response
from pyramid.view import view_config

from namifax.common import settings
from namifax.common.helpers import avantfaxlog, clean_faxnum
from namifax.services.addressbook import RESERVED_FAX_NUM, NFAddressBook
from namifax.services.archive_in import ArchiveIn
from namifax.views.admin import get_all_admin_modems
from namifax.views.fax_rights import fax_access, load_fax


def _sender(ab: NFAddressBook, r: dict) -> dict:
    """Who a received fax is from, as the original's get_company_details() decides.

    ``assign`` is ``"x"`` when the sender is unknown (no entry, or the reserved one: the name can be given with *assignx*),
    ``"c"`` when its company is named after its own number (the company can be renamed with *assign*) and empty when it has
    been assigned properly (the name links to its address book entry). ``choices`` lists the companies a shared number
    could belong to.
    """
    origfaxnum = r.get("origfaxnum") or ""
    out = {"company": "", "assign": "", "cid": None, "description": "", "choices": []}

    def named(company: str, number: str, cid, description: str = "") -> dict:
        out.update(company=company, cid=cid, description=description or "")
        if company == RESERVED_FAX_NUM:
            out["assign"] = "x"
        elif clean_faxnum(company) and clean_faxnum(company) == clean_faxnum(number):
            out["assign"] = "c"
        return out

    try:
        if r.get("companyid") and ab.loadbycid(r["companyid"]) and ab.get_company():           # given a company by assignx
            return named(ab.get_company(), origfaxnum, r["companyid"])
        if r.get("faxnumid") and ab.loadbyfaxnumid(r["faxnumid"]):
            return named(ab.get_company() or "", ab.get_faxnumber() or origfaxnum, ab.get_companyid(), ab.get_description())
        if origfaxnum:
            found, several = ab.loadbyfaxnum(origfaxnum)
            if found and several:
                out["choices"] = ab.number_matches(origfaxnum)
                return out
            if found and ab.fax_array.get("abookfax_id") and ab.loadbyfaxnumid(ab.fax_array["abookfax_id"]):
                return named(ab.get_company() or "", ab.get_faxnumber() or origfaxnum, ab.get_companyid(), ab.get_description())
    except Exception:
        pass
    out["assign"] = "x"                                                                          # nobody knows this sender
    return out


def _line_names(request, rows):
    """A function giving the line (modem alias, or DID group when routing by DID) a received fax came in on."""
    from namifax.services.did import DIDRouting
    from namifax.services.modem import FaxModem

    modems, routes = FaxModem(db=request.dbsession), DIDRouting(db=request.dbsession)
    cache: dict = {}

    def name(row: dict) -> str:
        key = (row.get("modemdev"), row.get("didr_id"))
        if key not in cache:
            label = row.get("modemdev") or ""
            if label and modems.load_device(label) and modems.get_alias():
                label = f"{modems.get_alias()} ({label})"
            did = row.get("didr_id")
            if did and routes.loadbyid(did) and routes.get_alias():
                label = f"{label} · {routes.get_alias()}".strip(" ·")
            cache[key] = label
        return cache[key]

    return name


def _inbox_row(ab: NFAddressBook, r: dict) -> dict:
    who = _sender(ab, r)
    return {
        "id": r.get("fid"),
        "choices": who["choices"],
        "assign": who["assign"],
        "cid": who["cid"],
        "number_description": who["description"],
        "company": who["company"] if who["company"] != RESERVED_FAX_NUM else "",
        "origfaxnum": r.get("origfaxnum") or "-",
        "archstamp": r.get("archstamp") or "",
        "modemdev": r.get("modemdev") or "",
        "line": r.get("_line") or r.get("modemdev") or "",
        "pages": r.get("pages") or 1,
        "description": r.get("description") or "",
    }


MIN_PAGE_LIMIT = 10


def page_size(request, column: str = "faxperpageinbox", default: int | None = None) -> int:
    """The user's own page size ($faxesperpage of the original; the configured default when they have none), then the optional
    ``pagelimit`` (never below 10)."""
    from sqlalchemy import select

    from namifax.models import UserAccount

    if default is None:
        default = (settings.default_faxes_per_page_archive() if column == "faxperpagearchive"
                   else settings.default_faxes_per_page_inbox())
    size = default
    who = request.identity or {}
    uid = who.get("user_id") or who.get("uid")
    if uid:
        value = request.dbsession.execute(select(getattr(UserAccount, column)).where(UserAccount.uid == uid)).scalar()
        size = int(value) if value else default
    limit = (request.params.get("pagelimit") or "").strip()
    if limit.isdecimal():
        size = max(int(limit), MIN_PAGE_LIMIT)
    return size


def page_index(request, total: int, limit: int) -> tuple[int, int]:
    """(page index, number of pages) with an index out of range moved to the nearest page, as inbox.php does."""
    pages = -(-total // limit) if total > limit else 0
    raw = (request.params.get("pageindex") or "").strip()
    index = int(raw) if raw.isdecimal() else 0
    return max(min(index, pages - 1), 0), pages


@view_config(route_name="inbox", renderer="namifax:templates/inbox.jinja2", permission="view")
def inbox_view(request):
    """Render inbox list matching NamiFAX layout and action items."""
    identity = request.identity or {"username": "admin", "is_admin": True, "superuser": True}

    faxes = []
    total, limit, index, pages = 0, page_size(request), 0, 0
    if not request.params.get("empty"):
        arc = ArchiveIn(db=request.dbsession)
        access = fax_access(request)
        total = arc.get_num_faxes(devices=access.devices, faxcats=access.categories, enable_did_routing=access.did_routing)
        index, pages = page_index(request, total, limit)
        rows = arc.list_inbox(devices=access.devices, index=index, limit=limit, faxcats=access.categories,
                              enable_did_routing=access.did_routing, order_by_modem=settings.inbox_list_modem())
        if rows:
            ab = NFAddressBook(db=request.dbsession)
            names = _line_names(request, rows)
            for r in rows:
                r["_line"] = names(r)
                faxes.append(_inbox_row(ab, r))

    if "Authorization" in request.headers or "application/json" in request.headers.get("Accept", ""):
        return Response(json_body={"items": faxes, "total_count": total}, content_type="application/json")

    modem_list = get_all_admin_modems(request.dbsession)

    return {
        "title": "- NamiFAX - Inbox",
        "current_user": identity,
        "active_tab": "inbox",
        "faxes": faxes,
        "list_by_line": settings.inbox_list_modem(),
        "total_faxes": total,
        "num_inbox": total,
        "pages": pages,
        "page": index,
        "first_shown": index * limit + 1,
        "last_shown": index * limit + len(faxes),
        "page_limit_param": request.params.get("pagelimit") if (request.params.get("pagelimit") or "").isdecimal() else None,
        "modem_list": modem_list,
        "csrf_token": request.session.get_csrf_token(),
        "can_del": bool(fax_access(request).can_del or fax_access(request).superuser),
    }


@view_config(route_name="viewfax", renderer="namifax:templates/viewfax.jinja2", permission="view")
def viewfax_view(request):
    """The fax viewer (the original viewfax.php): the page images, the previous and next fax, and the fax's actions.

    A fax that is not (or no longer) in the inbox, does not exist or is not the user's goes back to the inbox.
    """
    identity = request.identity or {"username": "admin", "is_admin": True}
    fid = (request.params.get("fid") or "").strip()
    def back():
        return HTTPFound(location=request.route_url("inbox"))

    if not fid.isdecimal():
        return back()

    access = fax_access(request)
    arc = ArchiveIn(db=request.dbsession)
    arc.viewable_devices(access.devices, access.categories, access.did_routing)
    if not load_fax(request, arc, fid, action="viewfax") or not arc.get_inbox():
        return back()

    who = _sender(NFAddressBook(db=request.dbsession),
                  {"companyid": arc.get_companyid(), "faxnumid": arc.get_faxnumid(), "origfaxnum": arc.get_origfaxnum()})
    prev_fid, next_fid = arc.get_fid_prev(), arc.get_fid_next()
    pages = arc.get_pages() or 1
    return {
        "title": "NamiFAX - View Fax",
        "current_user": identity,
        "active_tab": "inbox",
        "fid": fid,
        "pages": pages,
        "archstamp": arc.get_archstamp() or "",
        "modemdev": arc.get_modemdev() or "",
        "company": who["company"] if who["company"] != RESERVED_FAX_NUM else "",
        "origfaxnum": arc.get_origfaxnum() or "",
        "assign": who["assign"], "cid": who["cid"], "choices": who["choices"],
        "prev_fid": prev_fid, "next_fid": next_fid,
        "after": next_fid or prev_fid or -1,                     # where to go once this fax is archived or deleted
        "can_del": bool(access.can_del or access.superuser),
        "csrf_token": request.session.get_csrf_token(),
    }


DOWNLOAD_FORMATS = ("pdf", "tif", "tiff")


@view_config(route_name="fax_download", permission="view")
def fax_download_view(request):
    """Stream PDF or TIFF binary file matching legacy file.php and pdf.php."""
    fid = request.matchdict.get("fid", "1")
    fmt = request.params.get("format", "pdf")
    if not (fid.isascii() and fid.isdecimal()) or fmt not in DOWNLOAD_FORMATS:      # both end up in a header: whole numbers and a list only
        raise HTTPBadRequest()
    if fmt != "pdf" and not settings.flag("ENABLE_DL_TIFF", False):        # the original shows the TIFF only when asked to
        raise HTTPNotFound()
    content_type = "application/pdf" if fmt == "pdf" else "image/tiff"

    # Attempt to locate actual archived fax file on disk
    file_bytes: bytes | None = None
    try:
        arc = ArchiveIn(db=request.dbsession)
        if load_fax(request, arc, fid, action="download"):
            file_path = arc.get_pdfpath() if fmt == "pdf" else arc.get_tiffpath()
            if file_path and os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
    except Exception:
        pass

    if file_bytes is None:
        raise HTTPNotFound("Fax document file not found")

    res = Response(body=file_bytes, content_type=content_type)
    res.headers["Content-Disposition"] = f'inline; filename="fax_{fid}.{fmt}"'
    return res


@view_config(route_name="fax_rotate", renderer="json", permission="view")
@view_config(route_name="rotate", renderer="json", permission="view")
def fax_rotate_view(request):
    """Rotate fax pages by 90 degrees (the original rotate.php).

    It changes the fax, so it is a POST with the session's CSRF token. (The original rotated through a link, which any
    other web page could make a signed-in user follow.)
    """
    if request.method != "POST":
        raise HTTPMethodNotAllowed("Rotating a fax needs a POST.", headers={"Allow": "POST"})
    check_csrf_token(request)                                  # raises a 400 for a missing or wrong token

    fid = request.matchdict.get("fid") or request.POST.get("fid", "")
    arc = ArchiveIn(db=request.dbsession)
    try:
        if fid and load_fax(request, arc, fid, action="rotate"):
            arc.rotate_fax()
    except Exception:
        pass

    back = request.POST.get("redirect")
    if back == "inbox":
        return HTTPFound(location=request.route_url("inbox"))
    if back == "viewfax" and str(fid).isdecimal():
        return HTTPFound(location=request.route_url("viewfax", _query={"fid": fid}))
    return {"status": "ok", "fid": str(fid), "rotation": 90}


@view_config(route_name="setcompany", permission="view")
def setcompany_view(request):
    """Assign a company (a fax number of the address book) to a received fax (the original setcompany.php).

    A POST with the session's CSRF token, like the original's form (the original asked for a POST too, but accepted
    nothing about where it came from).
    """
    if request.method != "POST":
        raise HTTPMethodNotAllowed("Assigning a company needs a POST.", headers={"Allow": "POST"})
    check_csrf_token(request)

    fid = request.POST.get("fid", "")
    faxnumid = request.POST.get("faxnumid")

    if fid and faxnumid:
        try:
            faxnumid = int(faxnumid)
        except ValueError:
            raise HTTPBadRequest("faxnumid must be a number.")
        arc = ArchiveIn(db=request.dbsession)
        ab = NFAddressBook(db=request.dbsession)
        # A database error is not caught here: it ends the request with a 500 and the transaction is rolled back,
        # instead of the page answering "done" for an assignment that did not happen.
        if load_fax(request, arc, fid, action="setcompany"):
            if not arc.set_faxnumid(faxnumid):
                avantfaxlog(f"setcompany> Could not assign fax number {faxnumid} to fax '{fid}': {arc.get_error()}",
                            session=request.dbsession)
            elif ab.loadbyfaxnumid(faxnumid):               # count the fax only when it was really assigned
                ab.inc_faxfrom()

    return HTTPFound(location=request.route_url("inbox"))
