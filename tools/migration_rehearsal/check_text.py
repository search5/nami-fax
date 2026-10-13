"""Do names that the legacy application stored come out as text? The legacy application stores accented letters as HTML entities
(``M&uuml;ller``) and relied on the browser to draw them. Prints, for each screen, how many entities are shown as letters of text.
Exit status 1 with --strict when any is."""
import os
import re
import sys

import webtest

from namifax import create_app

app = create_app(**{"sqlalchemy.url": os.environ["REH_URL"]})
client = webtest.TestApp(app, extra_environ={"HTTP_HOST": "example.com"})
client.post("/login", {"username": "carol", "password": "Carol#2013xy", "_submit_check": "1"})

shown = missing = 0
for label, path, wanted in (("address book", "/addressbook", "Müller &amp; Söhne GmbH"), ("e-mail book", "/emailbook", "Hans Müller"),
                            ("users", "/admin/users", "alice"), ("modems", "/admin/modems", "Soporte Línea 2 Müller"),
                            ("categories", "/admin/categories", "Vertrieb Müller")):
    page = client.get(path, expect_errors=True).text
    text = re.sub(r"<[^>]+>", " ", page)
    found = re.findall(r"&amp;[A-Za-z]+;|&amp;#\d+;", text)
    shown += len(found)
    has = wanted in page
    missing += not has
    print(f"{label:13} {'entities shown as text: ' + ', '.join(sorted(set(found))[:4]) if found else 'clean'}; "
          f"{'letters shown' if has else 'MISSING ' + repr(wanted)}")
print("RESULT:", "entities are shown as text" if shown else ("letters are missing" if missing else "clean"))
sys.exit(1 if (shown or missing) and "--strict" in sys.argv else 0)
