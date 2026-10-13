"""FOCUS_ON_NEW_FAX and FOCUS_ON_NEW_FAX_POPUP of the original's local_config.php (both off by default).

When a new fax arrives the inbox check brings the window forward only with FOCUS_ON_NEW_FAX, and announces the fax (a browser
notification instead of the original's alert) and plays the user's sound file only with FOCUS_ON_NEW_FAX_POPUP. Without them the
count in the page is updated and nothing else happens. The script is run under Node with a small stand-in for the page."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from namifax.common import settings

SCRIPT = Path(__file__).resolve().parents[2] / "src" / "namifax" / "static" / "js" / "notify.js"
NAMES = ("FOCUS_ON_NEW_FAX", "FOCUS_ON_NEW_FAX_POPUP")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)


# --- the switches ------------------------------------------------------------------------------------------------------------

def test_both_are_off_by_default():
    assert settings.focus_on_new_fax() is False and settings.focus_on_new_fax_popup() is False


@pytest.mark.parametrize("name,reader", [("FOCUS_ON_NEW_FAX", settings.focus_on_new_fax),
                                         ("FOCUS_ON_NEW_FAX_POPUP", settings.focus_on_new_fax_popup)])
def test_a_switch_is_set_from_the_environment(monkeypatch, name, reader):
    monkeypatch.setenv(name, "1")
    assert reader() is True


# --- what the page hands to the script ---------------------------------------------------------------------------------------

@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


def _body(client):
    return BeautifulSoup(client.get("/inbox").text, "html.parser").find("body")


def test_the_page_carries_no_switch_by_default(client):
    body = _body(client)
    assert not body.has_attr("data-focus-new-fax") and not body.has_attr("data-popup-new-fax")


def test_the_page_carries_the_switches_that_are_on(client, monkeypatch):
    monkeypatch.setenv("FOCUS_ON_NEW_FAX", "1")
    body = _body(client)
    assert body.has_attr("data-focus-new-fax") and not body.has_attr("data-popup-new-fax")
    monkeypatch.setenv("FOCUS_ON_NEW_FAX_POPUP", "1")
    assert _body(client).has_attr("data-popup-new-fax")


# --- the script --------------------------------------------------------------------------------------------------------------

NODE = shutil.which("node")

HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const flags = JSON.parse(process.argv[2]);
const answers = JSON.parse(process.argv[3]);                   // what /ajax/inbox says, one answer per check
const calls = { focus: 0, notifications: [], sounds: [], fetched: 0 };
const bodyAttrs = { 'data-new-fax': 'new fax' };
if (flags.focus) bodyAttrs['data-focus-new-fax'] = '1';
if (flags.popup) bodyAttrs['data-popup-new-fax'] = '1';
const badge = { textContent: '1' };
const timers = [];
const document = {
  title: 'Inbox',
  body: { getAttribute: n => (n in bodyAttrs ? bodyAttrs[n] : null), hasAttribute: n => n in bodyAttrs },
  querySelector: s => (s === '[data-inbox-count]' ? badge : null),
  querySelectorAll: s => (s === '[data-inbox-count]' ? [badge] : []),
  addEventListener() {}, removeEventListener() {},
};
function Notification(title, options) { calls.notifications.push(options.body); }
Notification.permission = 'granted';
function Audio(src) { this.addEventListener = () => {}; this.play = () => { calls.sounds.push(src); return Promise.resolve(); }; }
const window = { fetch: true, Notification, focus: () => { calls.focus++; } };
const fetch = () => { const text = answers[calls.fetched++]; return Promise.resolve({ ok: true, text: () => Promise.resolve(text) }); };
const ctx = vm.createContext({ window, document, Notification, Audio, fetch, DOMParser: function () {},
  setInterval: (f, ms) => { timers.push(f); }, parseInt, encodeURIComponent, Math, console });
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
(async () => {
  const check = timers[0];                                     // the inbox check is registered first
  for (let i = 0; i < answers.length; i++) { check(); await new Promise(r => setImmediate(r)); await new Promise(r => setImmediate(r)); }
  console.log(JSON.stringify({ focus: calls.focus, notifications: calls.notifications, sounds: calls.sounds,
                               count: String(badge.textContent), title: document.title }));
})();
"""


def _run(focus: bool, popup: bool, *answers: str) -> dict:
    if not NODE:
        pytest.skip("node is not installed")
    out = subprocess.run([NODE, "-e", HARNESS, str(SCRIPT), json.dumps({"focus": focus, "popup": popup}), json.dumps(list(answers))],
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_without_the_switches_a_new_fax_only_updates_the_count():
    assert _run(False, False, "3|beep.ogg") == {"focus": 0, "notifications": [], "sounds": [], "count": "3", "title": "(3) Inbox"}


def test_the_focus_switch_brings_the_window_forward_and_nothing_more():
    assert _run(True, False, "3|beep.ogg") == {"focus": 1, "notifications": [], "sounds": [], "count": "3", "title": "(3) Inbox"}


def test_the_popup_switch_announces_the_fax_and_plays_the_sound():
    assert _run(False, True, "3|beep.ogg") == {"focus": 0, "notifications": ["3 new fax"], "sounds": ["/audio/beep.ogg"],
                                               "count": "3", "title": "(3) Inbox"}


def test_both_switches_do_both():
    done = _run(True, True, "2")
    assert (done["focus"], done["notifications"], done["sounds"]) == (1, ["2 new fax"], [])


def test_a_lower_count_is_not_announced():
    done = _run(True, True, "0")
    assert (done["focus"], done["notifications"], done["count"]) == (0, [], "0")
