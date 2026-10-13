import http.cookiejar, os, re, sys, urllib.parse, urllib.request, urllib.error
import webtest
from namifax import create_app

LEGACY = sys.argv[1]
app = create_app(**{"sqlalchemy.url": os.environ["REH_URL"]})

class Legacy:
    def __init__(self, user, pw):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.opener.open(LEGACY + "/index.php", timeout=30).read()
        data = urllib.parse.urlencode({"username": user, "password": pw, "_submit_check": "1"}).encode()
        self.opener.open(LEGACY + "/index.php", data, timeout=30).read()
    def get(self, path):
        try:
            with self.opener.open(LEGACY + path, timeout=60) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

def port_client(user, pw):
    c = webtest.TestApp(app, extra_environ={"HTTP_HOST": "example.com"})
    c.post("/login", {"username": user, "password": pw, "_submit_check": "1"})
    return c

users = (("alice", "Alice#2013x"), ("bob", "Bob#2013xyz"), ("carol", "Carol#2013xy"))
bad = 0
for user, pw in users:
    lg, pt = Legacy(user, pw), port_client(user, pw)
    l_inbox = sorted(set(re.findall(rb'id="faxid_(\d+)"', lg.get("/inbox.php")[1])), key=int)
    p_inbox = sorted(set(re.findall(r'id="faxid_(\d+)"', pt.get("/inbox").text)), key=int)
    l_inbox = [x.decode() for x in l_inbox]
    same = l_inbox == p_inbox
    bad += not same
    print(f"{user:6} inbox legacy={l_inbox} port={p_inbox} {'SAME' if same else 'DIFFERENT'}")
    l_pdf, p_pdf = [], []
    for fid in range(1, 7):
        st, body = lg.get(f"/pdf.php?fid={fid}")
        l_pdf.append(fid if body[:4] == b"%PDF" else None)
        r = pt.get(f"/faxes/download/{fid}?format=pdf", expect_errors=True)
        p_pdf.append(fid if r.status_int == 200 and r.body[:4] == b"%PDF" else None)
    same = l_pdf == p_pdf
    bad += not same
    print(f"{user:6} pdf    legacy={[x for x in l_pdf if x]} port={[x for x in p_pdf if x]} {'SAME' if same else 'DIFFERENT'}")
    # thumbnails and page images of fax 3 (3 pages), when the user may see it
    if 3 in p_pdf:
        t = pt.get("/faxes/thumbnail/3", expect_errors=True)
        i = pt.get("/faxes/image/3/2", expect_errors=True)
        print(f"{user:6} thumbnail {t.status_int} {t.content_type} {len(t.body)}B | page2 {i.status_int} {i.content_type} {len(i.body)}B")
print("MISMATCHES:", bad)
