"""The web server rules that send the old AvantFAX 3.x addresses to the new ones (deploy/legacy-redirects/) must not drift from the
application: every address they send people to is a page of the application, and the Apache and nginx files cover the same
old pages. (The rules themselves are tried against real Apache and nginx servers when they are changed.)"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RULES = Path(__file__).resolve().parents[2] / "deploy" / "legacy-redirects"

# old address -> new address, as the rule files promise (the query string of the old address is kept)
MAP = {
    "index.php": "/login", "inbox.php": "/inbox", "archive.php": "/archive", "sendfax.php": "/sendfax", "outbox.php": "/outbox",
    "addressbook.php": "/addressbook", "emailbook.php": "/emailbook", "distrolist.php": "/distrolist", "settings.php": "/settings",
    "logout.php": "/logout", "forgot.php": "/forgot", "pwdexpired.php": "/pwdexpired", "txreport.php": "/txreport",
    "viewfax.php": "/viewfax", "email.php": "/email", "assign.php": "/assign", "assignx.php": "/assignx", "rotate.php": "/rotate",
    "setcompany.php": "/setcompany", "search.php": "/search",
    "addressbook_edit.php": "/addressbook/edit", "emailbook_edit.php": "/emailbook/edit", "distrolist_edit.php": "/distrolist/edit",
    "pdf.php": "/faxes/download/12?format=pdf", "refax.php": "/sendfax?refax=12",
    "admin/admin.php": "/admin", "admin/users.php": "/admin/users", "admin/deluser.php": "/admin/users/delete",
    "admin/conf_modems.php": "/admin/modems", "admin/conf_didroute.php": "/admin/routing/did",
    "admin/conf_barcoderoute.php": "/admin/barcodes", "admin/conf_covers.php": "/admin/covers", "admin/conf_dynconf.php": "/admin/dynconf",
    "admin/fax_categories.php": "/admin/categories", "admin/fax2email.php": "/admin/fax2email",
    "admin/system_func.php": "/admin/system_func", "admin/system_logs.php": "/admin/system_logs",
}


@pytest.mark.parametrize("old,new", sorted(MAP.items()))
def test_a_redirect_leads_to_a_page_of_the_application(testapp, old, new):
    assert testapp.get(new, expect_errors=True).status_int != 404, f"{old} -> {new}"


@pytest.mark.parametrize("name", ["apache.conf", "nginx.conf"])
def test_each_rule_file_covers_every_old_page(name):
    text = (RULES / name).read_text(encoding="utf-8")
    missing = []
    for old in MAP:
        stem = Path(old).stem                                        # inbox, conf_modems, users, ...
        base = stem[:-5] if stem.endswith("_edit") else stem
        if base not in text and not (old == "index.php" and "index" in text):
            missing.append(old)
    assert missing == [], f"{name} has no rule for {missing}"


@pytest.mark.parametrize("name", ["apache.conf", "nginx.conf"])
def test_the_two_parameter_changes_are_handled(name):
    text = (RULES / name).read_text(encoding="utf-8")
    assert "/faxes/download/" in text and "format=pdf" in text          # pdf.php?fid=N
    assert "/sendfax?refax=" in text                                   # refax.php?fid=N
