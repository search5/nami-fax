"""Distribution lists (the original distrolist.php, distrolist_edit.php and distrolist_helper.php).

A list holds address-book fax numbers as ``<abookfax_id>|<number>`` entries; the page shows them as "Company - number".
"""

from __future__ import annotations

from typing import Any

from pyramid.httpexceptions import HTTPFound
from pyramid.renderers import render_to_response
from pyramid.view import view_config

from namifax.i18n import _
from namifax.services.addressbook import RESERVED_FAX_NUM, NFAddressBook
from namifax.services.distro import DistributionList


def _members(db: Any, entries: list[str]) -> list[dict[str, str]]:
    """Each ``fnid|number`` entry as ``{"value", "label"}``, sorted by label; an entry whose number is gone is left out."""
    book = NFAddressBook(db=db)
    found = []
    for entry in entries:
        fnid = entry.split("|", 1)[0]
        if fnid.isdecimal() and book.loadbyfaxnumid(int(fnid)):
            company = book.get_company() or RESERVED_FAX_NUM
            found.append({"value": entry, "label": f"{company} - {book.get_faxnumber()}",
                          "company": company, "faxnumber": book.get_faxnumber()})
    return sorted(found, key=lambda m: m["label"])


def get_all_distrolists(db: Any = None) -> list[dict[str, Any]]:
    """Every list with its members."""
    try:
        dl = DistributionList(db=db)
        result = []
        for row in dl.get_distrolists() or []:
            members: list[dict[str, str]] = []
            if dl.load_list(row.get("dl_id")):
                members = _members(db, dl.list_entries())
            result.append({"dl_id": row.get("dl_id"), "listname": row.get("listname", ""),
                           "members_count": len(members), "members": members})
        return result
    except Exception:
        return []


def _page(request, selected_id, *, error=None, message=None):
    lists = get_all_distrolists(request.dbsession)
    selected = next((d for d in lists if str(d["dl_id"]) == str(selected_id)), None) if selected_id else None
    return {
        "title": "- NamiFAX - Distribution Lists",
        "current_user": request.identity or {"username": "admin", "is_admin": True, "superuser": True},
        "active_tab": "addressbook", "distrolists": lists, "selected_list": selected, "dl_id": selected_id,
        "error": error, "message": message,
    }


@view_config(route_name="distrolist", renderer="namifax:templates/distrolist.jinja2", permission="view")
def distrolist_view(request):
    """The lists, and the members of the chosen one. (Deleting is a POST to the edit page.)"""
    selected = request.params.get("dl_id")
    lists = get_all_distrolists(request.dbsession)
    if not selected and lists:
        selected = lists[0]["dl_id"]
    return _page(request, selected)


@view_config(route_name="distrolist_edit", renderer="namifax:templates/distrolist_edit.jinja2", permission="view")
def distrolist_edit_view(request):
    """Create, rename, empty or delete a list; the plain GET is the new-list form."""
    dl_id = (request.params.get("dl_id") or "").strip()
    page = _page(request, dl_id or None)
    if request.method != "POST":
        return page

    post = request.POST
    dl = DistributionList(db=request.dbsession)
    who = (request.identity or {}).get("user_id") or (request.identity or {}).get("uid")
    dl.set_moduser(int(who) if who else None)
    here = lambda i: HTTPFound(location=request.route_url("distrolist", _query={"dl_id": i}))      # noqa: E731

    if post.get("delete") and dl_id.isdecimal():
        dl.delete_list(int(dl_id))
        return HTTPFound(location=request.route_url("distrolist"))

    name = (post.get("listname") or "").strip()
    if not dl_id.isdecimal():                                                       # a new list
        if dl.create(name):
            return here(dl.get_dl_id())
        return render_to_response("namifax:templates/distrolist_edit.jinja2", {**page, "error": dl.get_error()}, request=request)

    if not dl.load_list(int(dl_id)):
        return HTTPFound(location=request.route_url("distrolist"))
    if post.get("remove"):
        dl.remove_entries(post.getall("dl_list[]") or post.getall("dl_list"))
    elif name and (post.get("savename") or post.get("save") or not post.get("refresh")):
        dl.set_listname(name)
    return here(dl_id)
