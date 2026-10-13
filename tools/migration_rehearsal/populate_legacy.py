"""Fill a running legacy AvantFAX 3.3.5 through its own web pages, like an administrator and its users would have for years."""
import html
import http.cookiejar
import sys
import urllib.parse
import urllib.request

BASE = sys.argv[1]


class Site:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def post(self, path, pairs):
        data = urllib.parse.urlencode(pairs, doseq=True).encode("utf-8")
        with self.opener.open(BASE + path, data, timeout=60) as res:
            return res.status, res.geturl(), res.read().decode("utf-8", "replace")

    def get(self, path):
        with self.opener.open(BASE + path, timeout=60) as res:
            return res.status, res.geturl(), res.read().decode("utf-8", "replace")


def check(label, ok, extra=""):
    print(("OK   " if ok else "FAIL ") + label + (" " + extra if extra else ""))
    if not ok:
        sys.exit(1)


# 1. the installer's admin must change the password, then use the admin area
admin = Site()
admin.get("/index.php")
st, url, body = admin.post("/index.php", [("username", "admin"), ("password", "password"), ("_submit_check", "1")])
check("admin logs in and is sent to the password change", "pwdexpired" in url, url)
st, url, body = admin.post("/pwdexpired.php", [("oldpwd", "password"), ("newpwd", "Adm1nPass13"), ("conpwd", "Adm1nPass13"), ("_submit_check", "1")])
check("admin changes the password", "pwdexpired" not in url, url)

adm = Site()
adm.get("/admin/index.php")
st, url, body = adm.post("/admin/index.php", [("username", "admin"), ("password", "Adm1nPass13"), ("_submit_check", "1")])
check("admin area login", "/admin/" in url, url)

# 2. modems, categories
for dev, alias, contact in (("ttyS0", "영업팀 수신 Sales", "sales@corp.example"), ("ttyS1", "Soporte Línea 2 Müller", "")):
    st, url, body = adm.post("/admin/conf_modems_edit.php", [("device", dev), ("alias", alias), ("printer", ""), ("faxcatid", ""),
                                                           ("contact", contact), ("create", "Create"), ("_submit_check", "1")])
for name in ("Invoices", "Legal 법무", "Vertrieb Müller"):
    adm.post("/admin/fax_cat_edit.php", [("name", name), ("create", "Create"), ("_submit_check", "1")])

# 3. users
USERS = [
    dict(name="Alice Müller 김", username="alice", email="alice@corp.example", password="Alice#2013x", can_del="1", any_modem="0",
         modemdevs=["ttyS0"], faxcats=["1", "2"], language="de", faxperpageinbox="15", faxperpagearchive="30"),
    dict(name="Bob Restricted", username="bob", email="bob@corp.example", password="Bob#2013xyz", can_del="0", any_modem="0",
         modemdevs=["ttyS1"], faxcats=["3"], language="en"),
    dict(name="Carol Super", username="carol", email="carol@corp.example", password="Carol#2013xy", superuser="1", is_admin="1",
         can_del="1", any_modem="1", language="en"),
]
for u in USERS:
    pairs = [("_submit_check", "1"), ("acc_enabled", "1"), ("pwd_reuse", "0"), ("pwdcycle", "0"), ("email_sig", "-- \n서명 Müller"),
             ("from_company", "Corp 주식회사"), ("from_location", "Seoul"), ("from_voicenumber", "+82-2-555-0100"),
             ("from_faxnumber", "+82-2-555-0199"), ("user_tsi", "CORP"), ("coverpage_id", ""), ("audiofile", "")]
    for k, v in u.items():
        if isinstance(v, list):
            pairs += [(k + "[]", x) for x in v]
        else:
            pairs.append((k, v))
    st, url, body = adm.post("/admin/users.php", pairs)
st, url, body = adm.get("/admin/users_list.php")
for u in USERS:
    check(f"user {u['username']} is listed", u["username"] in body)

# 4. address book, e-mail book, distribution list (as the first user would)
alice = Site()
alice.get("/index.php")
st, url, body = alice.post("/index.php", [("username", "alice"), ("password", "Alice#2013x"), ("_submit_check", "1")])
print("alice first login ->", url)
if "pwdexpired" in url:
    alice.post("/pwdexpired.php", [("oldpwd", "Alice#2013x"), ("newpwd", "Alice#2014y"), ("conpwd", "Alice#2014y"), ("_submit_check", "1")])

root = Site()
root.get("/index.php")
root.post("/index.php", [("username", "admin"), ("password", "Adm1nPass13"), ("_submit_check", "1")])
for company, nums in (("Müller & Söhne GmbH", [("+49-30-5550101", "Zentrale", "Hans Müller"), ("+49-30-5550102", "Buchhaltung", "")]),
                      ("서울상사 Seoul Trading", [("+82-2-5550200", "대표 번호", "홍길동")]),
                      ("Acme Corp", [("+1-555-0100", "", "")])):
    first = nums[0]
    st, url, body = root.post("/addressbook_edit.php", [
        ("company", company), ("new_faxnum", first[0]), ("new_desc", first[1]), ("new_to_person", first[2]), ("newfaxcatid", ""),
        ("new_address", "Hauptstraße 1"), ("new_city", "Berlin"), ("new_to_zip", "10115"), ("new_to_location", ""), ("new_to_voicenumber", ""),
        ("create", "Create"), ("_submit_check", "1")])
for name, email in (("Hans Müller", "hans@mueller.example"), ("홍길동", "hong@seoul.example")):
    root.post("/emailbook_edit.php", [("contact_name", name), ("contact_email", email), ("create", "Create"), ("_submit_check", "1")])
# (the lists are filled by AJAX in the page, so ask the AJAX endpoints that the page uses)
st, url, body = root.get("/ajax/archivebook.php?q=M")
check("address book finds the German company", "Müller" in html.unescape(body), body[:80].replace("\n", " "))
st, url, body = root.get("/ajax/ajaxemailbook.php?q=Hans")
check("e-mail book finds the German contact", "Müller" in html.unescape(body), body[:80].replace("\n", " "))
print("legacy world created")
