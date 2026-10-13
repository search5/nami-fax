"""A company and an e-mail contact written by each side must be readable by the other."""
import http.cookiejar
import os
import re
import sys
import urllib.parse
import urllib.request

import webtest

from namifax import create_app

BASE = sys.argv[1]
app = create_app(**{"sqlalchemy.url": os.environ["REH_URL"]})
port = webtest.TestApp(app, extra_environ={"HTTP_HOST": "example.com"})
port.post("/login", {"username": "carol", "password": "Carol#2013xy", "_submit_check": "1"})
legacy = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
legacy.open(BASE + "/index.php").read()
legacy.open(BASE + "/index.php", urllib.parse.urlencode({"username": "carol", "password": "Carol#2013xy", "_submit_check": "1"}).encode()).read()


def legacy_xml(path):
    return legacy.open(BASE + path).read().decode("utf-8", "replace")


bad = 0
# the legacy application writes, the port reads
legacy.open(BASE + "/addressbook_edit.php", urllib.parse.urlencode({
    "company": "Brüder Ñandú AG", "new_faxnum": "+41-44-5550300", "new_desc": "Zürich", "new_to_person": "", "newfaxcatid": "",
    "new_address": "", "new_city": "", "new_to_zip": "", "new_to_location": "", "new_to_voicenumber": "", "create": "Create",
    "_submit_check": "1"}).encode()).read()
page = port.get("/addressbook").text
print("legacy wrote a company  -> the port lists it:", bool(re.search(r"Br(?:ü|&amp;uuml;|&uuml;)der", page)))
bad += not re.search(r"Br(?:ü|&amp;uuml;|&uuml;)der", page)

# the port writes, the legacy application reads
res = port.post("/addressbook/edit", {"_submit_check": "1", "company": "Schäfer & Söhne 한글 GmbH", "faxnumber": "+43-1-5550400"},
                expect_errors=True)
port.post("/emailbook/edit", {"_submit_check": "1", "contact_name": "Zoë Ångström 김", "contact_email": "zoe@example.org"},
          expect_errors=True)
found = "Schäfer &amp; Söhne 한글 GmbH" in legacy_xml("/ajax/archivebook.php?q=Sch")
print("port wrote a company    -> the legacy application lists it:", found, f"(port answered {res.status_int})")
bad += not found
found = "Zoë Ångström 김" in legacy_xml("/ajax/ajaxemailbook.php?q=Zo")
print("port wrote a contact    -> the legacy application lists it:", found)
bad += not found
print("MISMATCHES:", bad)
sys.exit(1 if bad else 0)
