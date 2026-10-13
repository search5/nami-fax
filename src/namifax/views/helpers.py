"""NamiFAX popup helper dialogs and vCard upload views matching legacy NamiFAX."""

import html
import re
from pyramid.httpexceptions import HTTPFound
from pyramid.response import Response
from pyramid.view import view_config

from namifax.common import settings
from namifax.i18n import _
from namifax.services.addressbook import NFAddressBook
from namifax.services.categories import FaxPDFCategory
from namifax.services.distro import DistributionList


@view_config(route_name="popup_distrolist_helper", renderer="namifax:templates/distrolist_helper.jinja2", permission="view")
def popup_distrolist_helper(request):
    """Add address-book fax numbers to a distribution list (the original distrolist_helper.php).

    The search box lists the fax numbers of the companies that match; the chosen ones are added as ``<id>|<number>``.
    """
    import os

    dl_id = (request.params.get("dl_id") or "").strip()
    dl = DistributionList(db=request.dbsession)
    if not dl_id.isdecimal() or not dl.load_list(int(dl_id)):
        raise HTTPFound(location=request.route_url("distrolist"))

    added = False
    error = None
    if request.method == "POST":
        chosen = request.POST.getall("myselect[]") or request.POST.getall("myselect")
        who = (request.identity or {}).get("user_id") or (request.identity or {}).get("uid")
        dl.set_moduser(int(who) if who else None)
        if dl.add_entries([c for c in chosen if c.split("|", 1)[0].isdecimal()]):
            added = True
        else:
            error = dl.get_error()

    query = (request.params.get("regexp") or "").strip()
    options = []
    if settings.contact_lookup_allowed(query):
        book = NFAddressBook(db=request.dbsession)
        numbers = book.numbers_by_company()
        for company in (book.search_companies(query) if query else book.get_companies()):
            for number in numbers.get(company.get("abook_id"), []):
                options.append({"value": f"{number['abookfax_id']}|{number['faxnumber']}",
                                "label": f"{company.get('company')} - {number['faxnumber']}"})
    return {"title": "- NamiFAX - Distribution List Helper", "dl_id": dl_id, "query": query, "options": options,
            "added": added, "error": error}


def _target(request) -> str:
    """The id of the field to fill in the opening window; anything but a plain id is dropped."""
    value = (request.params.get("target") or "").strip()
    return value if re.fullmatch(r"[A-Za-z][A-Za-z0-9_\-]{0,40}", value) else ""


def _picker(request, *, title, heading, action, options, separator, fetch="", prefill=False):
    from pyramid.renderers import render_to_response

    return render_to_response("namifax:templates/contact_picker.jinja2", {
        "title": title, "heading": heading, "action": action, "options": options, "separator": separator, "fetch": fetch,
        "prefill": prefill,
        "target": _target(request), "query": (request.params.get("regexp") or "").strip()}, request=request)


@view_config(route_name="popup_distro_contacts", permission="view")
def popup_distro_contacts(request):
    """Pick distribution lists: their fax numbers are put into the field that opened this window (distrocontacts.php)."""
    query = (request.params.get("regexp") or "").strip().lower()
    options = []
    for group in DistributionList(db=request.dbsession).get_distrolists() or []:
        name = str(group.get("listname", ""))
        if not query or query in name.lower():
            options.append((group.get("dl_id"), name))
    return _picker(request, title="- NamiFAX - Distribution Contacts", heading=str(_("Distribution Lists")),
                   action="/helper/distrocontacts", options=options, separator="; ", fetch="/ajax/dlist?dl_id=")


@view_config(route_name="popup_fax_contacts", permission="view")
def popup_fax_contacts(request):
    """Pick fax numbers of the address book (faxcontacts.php), shown as "Company - number"."""
    query = (request.params.get("regexp") or "").strip()
    book = NFAddressBook(db=request.dbsession)
    allowed = settings.contact_lookup_allowed(query)
    numbers = book.numbers_by_company() if allowed else {}
    options = []
    for company in ((book.search_companies(query) if query else book.get_companies()) if allowed else []):
        for number in numbers.get(company.get("abook_id"), []):
            options.append((number["faxnumber"], f"{company.get('company')} - {number['faxnumber']}", number.get("abookfax_id")))
    return _picker(request, title="- NamiFAX - Fax Contacts", heading=str(_("Fax Contacts")), action="/helper/faxcontacts",
                   options=options, separator="; ", prefill=True)


@view_config(route_name="popup_email_contacts", permission="view")
def popup_email_contacts(request):
    """Pick e-mail contacts (emailcontacts.php), as ``"Name" <address>``."""
    query = (request.params.get("regexp") or "").strip().lower()
    options = [(entry, entry) for entry in (NFAddressBook(db=request.dbsession).get_contacts() or {}).values()
               if not query or query in entry.lower()]
    return _picker(request, title="- NamiFAX - Email Contacts", heading=str(_("Email Contacts")), action="/helper/emailcontacts",
                   options=options, separator=", ")


def _vcard_lines(request) -> tuple[list[str] | None, str | None]:
    """The lines of the uploaded vCard file, or ``(None, error)``; ``(None, None)`` when no file was sent."""
    upload = request.POST.get("upload")
    if upload is None or not hasattr(upload, "file"):
        return None, None
    from namifax.services import upload_check

    content = upload.file.read(upload_check.max_bytes() + 1)
    if len(content) > upload_check.max_bytes():
        return None, upload_check.OVER_LIMIT
    text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)
    if not text.strip():
        return None, None
    if "BEGIN:VCARD" not in text.upper():
        return None, "vCard file problem: this does not look like a vCard (.vcf) file"
    return [line.strip() for line in text.splitlines()], None


def _vcard_value(line: str) -> str:
    return line.split(":", 1)[1].strip()


def _is_card_start(line: str) -> bool:
    return line.upper().startswith("BEGIN:VCARD")


def _upload_page(title: str, intro: str, action: str, message: str | None, error: str | None, extra_field: str = "") -> Response:
    notice = ""
    if error:
        notice = f'<div class="mb-4 p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded text-sm">{html.escape(error)}</div>'
    elif message:
        notice = f'<div class="mb-4 p-3 bg-emerald-50 border border-emerald-200 text-emerald-700 rounded text-sm">{html.escape(message)}</div>'
    page = f"""<!DOCTYPE html>
<html>
<head><title>- NamiFAX - {html.escape(title)}</title></head>
<body class="bg-slate-50 text-slate-800 p-6">
  <div class="max-w-md mx-auto bg-white p-6 rounded shadow border border-slate-200">
    <h1 class="text-xl font-bold mb-4 text-sky-900">Upload Contacts</h1>
    {notice}
    <p class="text-sm text-slate-600 mb-4">{html.escape(intro)}</p>
    <form action="{action}" method="post" enctype="multipart/form-data" class="space-y-4">
{extra_field}      <div>
        <label class="block text-sm font-semibold mb-1">vCard file:</label>
        <input type="file" name="upload" class="w-full border border-slate-300 rounded p-1 text-sm" />
      </div>
      <input type="hidden" name="_submit_check" value="1" />
      <div class="pt-2 flex justify-end">
        <button type="submit" class="px-4 py-2 bg-sky-800 text-white rounded text-sm font-medium hover:bg-sky-700">Upload</button>
      </div>
    </form>
  </div>
</body>
</html>"""
    return Response(page, content_type="text/html")


@view_config(route_name="upload_contacts", permission="view")
def upload_email_contacts(request):
    """Upload a vCard to import e-mail contacts (the original upload_contacts.php).

    Every address line of a card that has a name is added to the e-mail book; the page says how many were new.
    """
    message = error = None
    if request.method == "POST":
        lines, error = _vcard_lines(request)
        count = 0
        if lines:
            book = NFAddressBook(db=request.dbsession)
            name = None
            for line in lines:
                if _is_card_start(line):
                    name = None                                  # a card without a name must not reuse the previous one's
                elif "FN:" in line:
                    name = _vcard_value(line)
                elif "EMAIL" in line and ":" in line and ("EMAIL;" in line or line.upper().startswith("EMAIL:")):
                    email = _vcard_value(line)
                    if name and email and book.create_contact(name, email):
                        count += 1
        if not error:
            message = f"Successfully uploaded {count} contacts"
    return _upload_page("Upload Email Contacts", "Select a vCard (.vcf) file to import email contacts.",
                        "/upload/contacts", message, error)


@view_config(route_name="upload_faxcontacts", permission="view")
def upload_fax_contacts(request):
    """Upload a vCard to import fax contacts (the original upload_faxcontacts.php).

    Each FAX line makes a company (the card's organisation, else its person) with that number, the person and the chosen
    category. E-mail lines go to the e-mail book and are not counted. Like the original, once an organisation has been
    used for a company it is not used again, so a following number or card falls back to its person's name.
    """
    message = error = None
    if request.method == "POST":
        catid = request.POST.get("catid")
        catid_int = int(catid) if catid and str(catid).isdecimal() else None
        lines, error = _vcard_lines(request)
        count = 0
        if lines:
            book = NFAddressBook(db=request.dbsession)
            name = org = None
            for line in lines:
                if _is_card_start(line):
                    name = org = None
                elif "FN:" in line:
                    name = _vcard_value(line)
                elif line.upper().startswith("ORG:"):
                    org = _vcard_value(line).replace(";", "").strip()
                elif "EMAIL;" in line or line.upper().startswith("EMAIL:"):
                    email = _vcard_value(line)
                    if name and email:
                        book.create_contact(name, email)
                elif "FAX:" in line or ("TEL" in line.upper() and "FAX" in line.upper() and ":" in line):
                    number = _vcard_value(line).replace(";", "").strip()
                    org = org or name
                    if org and number and book.create(org):
                        org = None
                        count += 1
                        if book.create_faxnumid(number):
                            book.save_settings({"description": None, "faxcatid": catid_int, "to_person": name,
                                                "to_location": None, "to_voicenumber": None})
        if not error:
            message = f"Successfully uploaded {count} contacts"

    category_options = []
    try:
        for cat in FaxPDFCategory(db=request.dbsession).get_categories() or []:
            category_options.append(f'          <option value="{cat.get("catid")}">{html.escape(str(cat.get("name", "")))}</option>')
    except Exception:
        pass
    field = ('''      <div>
        <label class="block text-sm font-semibold mb-1">Category:</label>
        <select name="catid" class="w-full border border-slate-300 rounded px-2 py-1.5 text-sm">
''' + "\n".join(category_options) + '''
        </select>
      </div>
''')
    return _upload_page("Upload Fax Contacts", "Select a vCard (.vcf) file to import fax contacts into address book.",
                        "/upload/faxcontacts", message, error, field)
