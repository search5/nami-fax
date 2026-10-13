"""NamiFAX Interaction Modals and Dialog Views matching legacy NamiFAX popups."""

from __future__ import annotations

import re

from pyramid.csrf import check_csrf_token
from pyramid.httpexceptions import HTTPFound, HTTPForbidden
from pyramid.view import view_config

from namifax.common import settings
from namifax.i18n import _
from namifax.services.addressbook import NFAddressBook
from namifax.services.archive_in import ArchiveIn
from namifax.services.faxqueue import FaxQueue
import os

from namifax.common.helpers import send_mail, split_emails
from namifax.common.validators import is_valid_email
from namifax.services.categories import FaxPDFCategory
from namifax.services.user_account import NFUserAccount
from namifax.views.fax_rights import fax_access, load_fax


def _company_name(request, fax) -> str:
    """What the fax is called in a mail: its company, else the number it came from (the original's company_name)."""
    book = NFAddressBook(db=request.dbsession)
    if fax.get_faxnumid() and book.loadbyfaxnumid(fax.get_faxnumid()):
        return book.get_company() or ""
    if fax.get_companyid() and book.loadbycid(fax.get_companyid()):
        return book.get_company() or ""
    return fax.get_origfaxnum() or ""


def _categories_for(request, access) -> dict:
    """The categories the user may put a fax in: all for a superuser, otherwise those on their account."""
    cats = FaxPDFCategory(db=request.dbsession)
    if access.superuser:
        return {str(c["catid"]): c["name"] for c in cats.get_categories() or []}
    return {str(c): cats.get_name(int(c)) for c in access.faxcats if str(c).isdecimal() and cats.get_name(int(c))}


@view_config(route_name="modal_email", renderer="namifax:templates/modal_email.jinja2", permission="view")
def modal_email_view(request):
    """E-mail a fax as a PDF (the original email.php).

    The fax must exist and the user must have the right to it, else the user is sent to the inbox. After a successful
    mail the new addresses go into the e-mail book, and an inbox fax can be given a category and archived.
    """
    params = request.POST if request.method == "POST" else request.params
    fid = (params.get("fid") or "").strip()
    arc = ArchiveIn(db=request.dbsession)
    if not fid.isdecimal() or not load_fax(request, arc, fid, action="email"):
        return HTTPFound(location=request.route_url("inbox"))

    access = fax_access(request)
    account = NFUserAccount(db=request.dbsession)
    account.load_username(access.username)
    name, email = account.get_name() or access.username, (account.dbdata.get("email") or "")
    company = _company_name(request, arc)
    default_name = f"fax-{company}.pdf".replace(":", "").replace(" ", "-")
    in_inbox = bool(arc.get_inbox())
    categories = _categories_for(request, access) if in_inbox else {}

    values = {
        "fid": fid,
        "emails": params.get("emails", ""), "cc_emails": params.get("cc_emails", ""), "bcc_emails": params.get("bcc_emails", ""),
        "subject": params.get("subject", company)[:45], "filename": params.get("filename", default_name),
        "msg": params.get("msg", "\n\n\n" + (account.dbdata.get("email_sig") or "")),
        "category": params.get("category", ""), "archive": request.method != "POST" or bool(params.get("archive")),
        "url": params.get("url") or request.headers.get("Referer") or request.route_url("inbox"),
    }

    def page(error=None, message=None):
        return {"title": "- NamiFAX - Send Fax via Email", "values": values, "error": error, "message": message,
                "from_display": f"{name} <{email}>", "categories": categories, "in_inbox": in_inbox}

    if request.method != "POST":
        return page()

    recipients = split_emails(values["emails"])
    wrong = [r for r in recipients if not is_valid_email(r)] + \
            [r for r in split_emails(values["cc_emails"]) + split_emails(values["bcc_emails"]) if not is_valid_email(r)]
    if not recipients or wrong:
        return page(_("Please enter a valid e-mail address.") + (": " + ", ".join(wrong) if wrong else ""))
    pdf = arc.get_pdfpath()
    if not pdf or not os.path.exists(pdf):
        return page(_("The fax document was not found."))

    sent = send_mail(values["emails"], f'"{name}" <{email}>', values["subject"], values["msg"], file=pdf,
                     altname=values["filename"] or None, embedd=arc.get_thumbnail(), cc=values["cc_emails"] or None,
                     bcc=values["bcc_emails"] or None, session=request.dbsession)
    if not sent:
        return page(_("The email failed to send."))

    NFAddressBook(db=request.dbsession).create_contacts(values["emails"])
    if in_inbox and values["category"] in categories:
        arc.set_category(int(values["category"]), account.get_uid() or 0)
    if in_inbox and values["archive"]:
        arc.set_archivebox(int(fid))
    return page(message=_("The email was sent successfully."))


@view_config(route_name="modal_assign", renderer="namifax:templates/modal_assign.jinja2", permission="view")
def modal_assign_view(request):
    """Name a company that is only its number, or fold it into another one (the original assign.php).

    Typing a name renames the company; choosing another company moves this one's numbers and faxes to it and removes
    this one. An unknown company goes back to the inbox, like the original.
    """
    identity = request.identity or {"username": "admin", "uid": 1, "is_admin": True}
    raw = request.params.get("abook_id") or request.params.get("cid") or ""
    ab = NFAddressBook(db=request.dbsession)
    if not raw.isdecimal() or not ab.loadbycid(int(raw)):
        return HTTPFound(location=request.route_url("inbox"))
    cid = int(raw)
    message = error = None

    if request.method == "POST":
        myselect = (request.POST.get("myselect") or "").strip()
        regexp = (request.POST.get("regexp") or "").strip()
        if myselect.isdecimal() and int(myselect) != cid:
            old = ab.get_companyid()
            if ab.reassign(int(myselect)):
                ArchiveIn(db=request.dbsession).reassign(old, int(myselect))
                return HTTPFound(location=request.route_url("inbox"))
            error = ab.get_error()
        elif regexp:
            if ab.set_company(regexp):
                return HTTPFound(location=request.route_url("inbox"))
            error = ab.get_error()
        else:
            error = _("You must enter a company name")

    companies = [{"id": c.get("abook_id"), "name": c.get("company")}
                 for c in ab.get_companies() or [] if c.get("company") and c.get("abook_id") != cid]
    company = ab.get_company() or ""
    lookup = company if re.fullmatch(r"[0-9]+", company) else ""      # a company that is only a number (the original's rule)
    return {"title": "- NamiFAX - Assign Company", "current_user": identity, "abook_id": cid,
            "company": company, "companies": companies, "message": message, "error": error,
            "whitepages_url": settings.whitepages_url() + lookup if lookup else ""}


@view_config(route_name="assignx", renderer="namifax:templates/assignx.jinja2", permission="view")
def assignx_view(request):
    """Name the sender of a fax nobody knows (the original assignx.php): pick an existing company or type a new one.

    The fax gets the company (its number link is cleared, as the original did). Unlike the original the user needs the
    right to the fax, and the POST carries the session's CSRF token.
    """
    fid = (request.params.get("fid") or "").strip()
    arc = ArchiveIn(db=request.dbsession)
    if not fid.isdecimal() or not load_fax(request, arc, fid, action="assignx"):
        return HTTPFound(location=request.route_url("inbox"))

    book = NFAddressBook(db=request.dbsession)
    error = None
    if request.method == "POST":
        check_csrf_token(request)
        chosen = (request.POST.get("abook_id") or "").strip()
        name = (request.POST.get("regexp") or "").strip()
        cid = None
        if chosen.isdecimal() and book.loadbycid(int(chosen)):
            cid = int(chosen)
        elif name:
            if book.create(name):
                cid = book.get_companyid()
            else:
                error = book.get_error()
        else:
            error = _("You must enter a company name")
        if cid:
            arc.set_faxnumid(0)                       # no longer tied to the reserved number
            arc.set_companyid(cid)
            return HTTPFound(location=request.route_url("inbox"))

    companies = [(c.get("abook_id"), c.get("company")) for c in book.get_companies() or [] if c.get("company")]
    return {"title": "- NamiFAX - Name the sender", "fid": fid, "companies": companies, "error": error,
            "origfaxnum": arc.get_origfaxnum() or "", "csrf_token": request.session.get_csrf_token()}


@view_config(route_name="modal_note", renderer="namifax:templates/modal_note.jinja2", permission="view")
def modal_note_view(request):
    """Render add note dialog and update fax description."""
    identity = request.identity or {"username": "admin", "uid": 1, "is_admin": True}
    fid = request.params.get("fid", "1")
    desc = request.params.get("description", "Reviewed and verified by operator.")
    message = None

    if request.method == "POST":
        desc = request.params.get("description", "").strip()
        arc = ArchiveIn(db=request.dbsession)
        try:
            if fid and load_fax(request, arc, fid, action="set_note"):
                arc.set_note(description=desc, category=None, userid=identity.get("uid", 1))
                message = "Note saved successfully"
        except (ValueError, TypeError):
            pass

    return {
        "title": "- NamiFAX - Add Note",
        "current_user": identity,
        "fid": fid,
        "description": desc,
        "message": message,
    }


@view_config(route_name="modal_delete", renderer="namifax:templates/modal_delete.jinja2", permission="view")
def modal_delete_view(request):
    """Render delete fax confirmation dialog and delete fax record and assets."""
    identity = request.identity or {"username": "admin", "uid": 1, "is_admin": True}
    fid = request.params.get("fid", "1")
    status = None

    if not fax_access(request).can_del and not fax_access(request).superuser:
        raise HTTPForbidden("You may not delete faxes.")

    if request.method == "POST":
        arc = ArchiveIn(db=request.dbsession)
        try:
            if fid and load_fax(request, arc, fid, action="delete", delete=True) and arc.delete_fax():
                status = "deleted"
        except (ValueError, TypeError):
            pass
        following = (request.params.get("next") or "").strip()            # from the viewer: on to the next fax
        if status == "deleted" and following:
            if following.isdecimal():
                return HTTPFound(location=request.route_url("viewfax", _query={"fid": following}))
            return HTTPFound(location=request.route_url("inbox"))

    return {
        "title": "- NamiFAX - Delete Fax",
        "current_user": identity,
        "fid": fid,
        "status": status,
        "next": (request.params.get("next") or "").strip(),
    }


@view_config(route_name="modal_refax", permission="view")
def modal_refax_view(request):
    """The original's refax.php?fid=N: the reply to a received fax is the Send Fax page (``sendfax?refax=N``)."""
    fid = (request.params.get("fid") or "").strip()
    if fid.isdecimal():
        return HTTPFound(location=request.route_url("sendfax", _query={"refax": fid}))
    return HTTPFound(location=request.route_url("sendfax"))


@view_config(route_name="modal_txreport", renderer="namifax:templates/modal_txreport.jinja2", permission="view")
def modal_txreport_view(request):
    """Render transmission report dialog."""
    identity = request.identity or {"username": "admin", "uid": 1, "is_admin": True}
    fid = request.params.get("fid", "1")
    company = ""
    date_val = ""
    pages_val = 0
    faxnum = ""
    has_image = False

    arc = ArchiveIn(db=request.dbsession)
    try:
        if fid and str(fid).isdecimal() and load_fax(request, arc, fid, action="txreport"):
            date_val = arc.get_archstamp() or ""
            pages_val = arc.get_pages() or 0
            faxnum = arc.get_origfaxnum() or ""
            has_image = True
            cid = arc.get_companyid()
            if cid:
                ab = NFAddressBook(db=request.dbsession)
                if ab.loadbycid(cid):
                    company = ab.get_company() or ""
            elif arc.get_origfaxnum():
                company = arc.get_origfaxnum()
    except Exception:
        pass

    return {
        "title": "- NamiFAX - Transmission Report",
        "current_user": identity,
        "fid": fid,
        "company": company,
        "date": date_val,
        "pages": pages_val,
        "faxnum": faxnum,
        "has_image": has_image,
    }
