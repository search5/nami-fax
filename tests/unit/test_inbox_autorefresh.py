"""The inbox list follows the count (the original's performInboxCheck): on the Inbox page a change of the unread count reloads the
page, after the new-fax announcement and, while the user's sound is playing, after it has ended. Other pages only update their
count. The script is run under Node with a small stand-in for the page."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

SCRIPT = Path(__file__).resolve().parents[2] / "src" / "namifax" / "static" / "js" / "notify.js"
NODE = shutil.which("node")


@pytest.fixture
def client(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    return testapp


def test_the_page_tells_the_script_which_page_it_is(client):
    for url, page in (("/inbox", "inbox"), ("/archive", "archive")):
        assert BeautifulSoup(client.get(url).text, "html.parser").find("body")["data-page"] == page


HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const opts = JSON.parse(process.argv[2]);
const answers = JSON.parse(process.argv[3]);
const log = { reloads: 0, sounds: 0, ended: null, order: [] };
const attrs = { 'data-page': opts.page, 'data-new-fax': 'new fax' };
if (opts.popup) attrs['data-popup-new-fax'] = '1';
const badge = { textContent: '1' };
const timers = [];
const document = { title: 'x', body: { getAttribute: n => (n in attrs ? attrs[n] : null) },
  querySelector: s => (s === '[data-inbox-count]' ? badge : null), querySelectorAll: s => (s === '[data-inbox-count]' ? [badge] : []),
  addEventListener() {}, removeEventListener() {} };
function Notification(t, o) { log.order.push('notify'); }
Notification.permission = 'granted';
function Audio(src) { this.addEventListener = (t, f) => { if (t === 'ended') log.ended = f; };
                      this.play = () => { log.sounds++; log.order.push('play'); return Promise.resolve(); }; }
let n = 0;
const fetch = () => Promise.resolve({ ok: true, text: () => Promise.resolve(answers[n++]) });
const window = { fetch: true, Notification, focus() {}, location: { reload: () => { log.reloads++; log.order.push('reload'); } } };
const ctx = vm.createContext({ window, document, Notification, Audio, fetch, DOMParser: function () {}, parseInt, encodeURIComponent,
  Math, console, setInterval: f => timers.push(f), setTimeout: (f, ms) => { log.timeout = ms; } });
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
const tick = () => new Promise(r => setImmediate(r));
(async () => {
  for (let i = 0; i < answers.length; i++) { timers[0](); await tick(); await tick(); }
  const before = log.reloads;
  if (log.ended) { log.ended(); }
  console.log(JSON.stringify({ reloadsBeforeSoundEnded: before, reloads: log.reloads, sounds: log.sounds, order: log.order }));
})();
"""


def _run(page: str, popup: bool, *answers: str) -> dict:
    if not NODE:
        pytest.skip("node is not installed")
    out = subprocess.run([NODE, "-e", HARNESS, str(SCRIPT), json.dumps({"page": page, "popup": popup}), json.dumps(list(answers))],
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_inbox_reloads_when_a_fax_arrives():
    done = _run("inbox", False, "3")
    assert (done["reloads"], done["sounds"]) == (1, 0)


def test_the_inbox_reloads_when_the_count_falls():
    assert _run("inbox", False, "0")["reloads"] == 1


def test_the_inbox_does_not_reload_when_nothing_changed():
    assert _run("inbox", False, "1")["reloads"] == 0


def test_another_page_only_updates_its_count():
    assert _run("archive", False, "5")["reloads"] == 0


def test_a_playing_sound_is_not_cut_off_by_the_reload():
    done = _run("inbox", True, "3|beep.ogg")
    assert (done["reloadsBeforeSoundEnded"], done["reloads"]) == (0, 1)
    assert done["order"] == ["notify", "play", "reload"]


def test_the_notification_comes_before_the_reload():
    assert _run("inbox", True, "3")["order"] == ["notify", "reload"]
