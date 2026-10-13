"""The fax archive page (the original archive.php): search form, numbered results, paging and the row actions."""

from __future__ import annotations

import calendar
import datetime
from typing import Any, Optional
from urllib.parse import urlencode

from pyramid.response import Response
from pyramid.view import view_config

from namifax.i18n import _
from namifax.services.addressbook import NFAddressBook
from namifax.services.archive_base import FaxPDFArchive
from namifax.services.categories import FaxPDFCategory
from namifax.services.user_account import NFUserAccount
from namifax.views.admin import get_all_admin_modems
from namifax.views.fax_rights import fax_access
from namifax.views.inbox import _sender, page_size

DATE_FIELDS = ("start_day", "start_month", "start_year", "end_day", "end_month", "end_year")
SENTRECVD = ("*", "s", "r")


def _number(value: Optional[str]) -> Optional[int]:
    value = (value or "").strip()
    return int(value) if value.isdecimal() else None


def _bounds(p) -> tuple[Optional[str], Optional[str]]:
    """The start and end of the search from the day/month/year drop-downs ('*' = any), as archive.php works them out."""
    def part(name):
        return _number(p.get(name))                      # '*' and '' both mean "not chosen"

    sd, sm, sy, ed, em, ey = (part(n) for n in DATE_FIELDS)
    end = None
    if ed and em and ey:
        end = datetime.date(ey, em, min(ed, calendar.monthrange(ey, em)[1])).strftime("%Y-%m-%d 23:59:59")
    elif not ed and em and ey:
        end = f"{ey:04d}-{em:02d}-{calendar.monthrange(ey, em)[1]:02d} 23:59:59"
    elif not ed and not em and ey:
        end = f"{ey:04d}-12-31 23:59:59"
    start = None
    if sy:
        if sd and sm:
            day = datetime.date(sy, sm, min(sd, calendar.monthrange(sy, sm)[1]))
            start = day.strftime("%Y-%m-%d") if not end else day.strftime("%Y-%m-%d 00:00:00")
        elif sm:
            start = f"{sy:04d}-{sm:02d}" if not end else f"{sy:04d}-{sm:02d}-01 00:00:00"
        else:
            start = f"{sy:04d}" if not end else f"{sy:04d}-01-01 00:00:00"
    return start, end


def _months() -> list[tuple[str, str]]:
    names = [_("January"), _("February"), _("March"), _("April"), _("May"), _("June"), _("July"), _("August"),
             _("September"), _("October"), _("November"), _("December")]
    return [("*", "")] + [(str(i + 1), str(n)) for i, n in enumerate(names)]


@view_config(route_name="opensearch", request_method="GET", permission="public")
def opensearch_view(request):
    """The OpenSearch description that lets a browser search the archive from its search box (the original's search.php)."""
    base = request.application_url.rstrip("/")
    body = ('<?xml version="1.0"?>\n<OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/"\n'
            '                       xmlns:moz="http://www.mozilla.org/2006/browser/search/">\n'
            '<ShortName>NamiFAX Archive</ShortName>\n<Description>NamiFAX Archive search</Description>\n'
            '<InputEncoding>utf-8</InputEncoding>\n'
            f'<Image height="16" width="16" type="image/x-icon">{base}/static/favicon.ico</Image>\n'
            f'<Url type="text/html" method="GET" template="{base}/archive?opensearch&amp;kw={{searchTerms}}"></Url>\n'
            '</OpenSearchDescription>\n')
    return Response(body, content_type="application/opensearchdescription+xml", charset="utf-8")


@view_config(route_name="archive", renderer="namifax:templates/archive.jinja2", permission="view")
def archive_view(request):
    """Search the archive; without a search the faxes of today are listed."""
    identity = request.identity or {"username": "admin", "is_admin": True}
    access = fax_access(request)
    db = request.dbsession
    params = request.params
    today = datetime.date.today()

    searched = "kw" in params
    limit = page_size(request, "faxperpagearchive")
    pageindex = max(_number(params.get("pageindex")) or 0, 0)
    userid = _number(params.get("userid")) if access.superuser else access.uid

    criteria: dict[str, Any] = {
        "faxid": _number(params.get("faxid")), "userid": userid,
        "pagelimit": limit, "pageindex": pageindex, **access.search_rights(),
    }
    form = {"kw": "", "regexp": "", "faxid": params.get("faxid", ""), "companyid": "", "category": "",
            "userid": str(userid or "") if access.superuser else "", "sentrecvd": "*",
            **{n: str(getattr(today, n.split("_")[1])) for n in DATE_FIELDS}}
    if searched:
        start, end = _bounds(params)
        if "opensearch" in params:                              # the browser's search box looks through every date
            start = end = None
            for name in DATE_FIELDS:
                form[name] = "*"
        sentrecvd = params.get("sentrecvd") if params.get("sentrecvd") in SENTRECVD else "*"
        criteria.update(start_date=start, end_date=end, keywords=(params.get("kw") or "").strip() or None,
                        companyid=_number(params.get("companyid")), sentrecvd=sentrecvd,
                        category=_number(params.get("category")))
        form.update({k: params.get(k, "") for k in ("kw", "regexp", "category", "companyid", *DATE_FIELDS)}, sentrecvd=sentrecvd)
    else:
        criteria.update(start_date=today.strftime("%Y-%m-%d 00:00:00"), end_date=today.strftime("%Y-%m-%d 23:59:59"),
                        keywords=None, companyid=None, sentrecvd="*", category=None)

    arc = FaxPDFArchive(db=db)
    total = arc.search_archive(criteria)
    pages = -(-total // limit) if total > limit else 0
    pageindex = max(min(pageindex, pages - 1), 0)

    ab = NFAddressBook(db=db)
    cats = FaxPDFCategory(db=db)
    names = {c["catid"]: c["name"] for c in cats.get_categories() or []}
    users = {u["uid"]: u["username"] for u in NFUserAccount(db=db).list_accounts()} if access.superuser else {}
    can_del = bool(access.can_del or access.superuser)

    rows = []
    while True:
        fid = arc.next_archive_entry()
        if not fid:
            break
        fax = FaxPDFArchive(db=db)
        if not fax.load_fax(fid):
            continue
        who = _sender(ab, {"companyid": fax.get_companyid(), "faxnumid": fax.get_faxnumid(), "origfaxnum": fax.get_origfaxnum()})
        rows.append({
            "id": fid, "pages": fax.get_pages() or 1, "userid": fax.get_userid(), "received": bool(fax.get_modemdev()),
            "modemdev": fax.get_modemdev(), "description": fax.get_description() or "", "archstamp": fax.get_archstamp() or "",
            "category": names.get(fax.get_faxcatid()) or "", "user": users.get(fax.get_userid()) or "",
            "company": who["company"], "assign": who["assign"], "cid": who["cid"], "choices": who["choices"],
            "origfaxnum": fax.get_origfaxnum() or "",
        })

    # categories one may pick: all for a superuser, otherwise those on the account
    if access.superuser:
        category_list = [(str(cid), name) for cid, name in names.items()]
    else:
        category_list = [(str(c), names[c]) for c in (int(x) for x in access.faxcats or [] if str(x).isdecimal()) if c in names]

    # a company the form is set to is offered even before the list is fetched
    companies = []
    regexp = form["regexp"].strip()
    selected_company = _number(form["companyid"])
    for row in (ab.search_companies(regexp) if regexp else []):
        companies.append((str(row["abook_id"]), row["company"]))
    if selected_company and str(selected_company) not in [c for c, _n in companies] and ab.loadbycid(selected_company):
        companies.append((str(selected_company), ab.get_company()))

    keep = [(k, v) for k, v in params.items() if k != "pageindex"] if searched else []
    base = urlencode(keep)

    def link(i):
        return "/archive?" + (base + "&" if base else "") + f"pageindex={i}"

    return {
        "title": "- NamiFAX - Archive",
        "current_user": identity,
        "active_tab": "archive",
        "form": form, "rows": rows, "total": total, "searched": searched,
        "pages": pages, "page": pageindex, "first_shown": pageindex * limit + 1, "last_shown": pageindex * limit + len(rows),
        "links": [link(i) for i in range(pages)],
        "category_list": category_list, "companies": companies,
        "user_list": [("", "")] + [(str(k), v) for k, v in users.items()],
        "days": [("*", "")] + [(str(i), str(i)) for i in range(1, 32)],
        "months": _months(),
        "years": [("*", "")] + [(str(y), str(y)) for y in range(2004, today.year + 2)],
        "sentrecvd_list": [("*", _("Both sent and received faxes")), ("s", _("Only sent faxes")), ("r", _("Only received faxes"))],
        "start_number": pageindex * limit + 1,
        "can_del": can_del, "superuser": access.superuser,
        "modem_list": get_all_admin_modems(db),
    }
