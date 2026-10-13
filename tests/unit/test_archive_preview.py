"""Archive: the preview of a fax beside its row while the mouse is over it (the original's previewImage in avantfax.js).

The page marks every row with the address of its image and carries the hidden preview box; the script shows the box beside the
hovered row, highlights the row and puts both away again. The script itself is run under Node with a small stand-in for the page."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from namifax.models import FaxArchive
from test_fax_access_control import _fax, _login, world  # noqa: F401  (same users and helpers)

SCRIPT = Path(__file__).resolve().parents[2] / "src" / "namifax" / "static" / "js" / "archive.js"


@pytest.fixture
def page(world, tmp_path):
    world.db.execute(FaxArchive.__table__.delete())
    ids = [_fax(world.db, tmp_path, f"a{n}", inbox=0, modemdev="ttyS0") for n in range(3)]
    client = _login(world, "root")
    return BeautifulSoup(client.get("/archive?kw=&opensearch=1&sentrecvd=r").text, "html.parser"), ids, client


# --- the page ----------------------------------------------------------------------------------------------------------------

def test_every_row_names_the_image_of_its_fax(page):
    soup, ids, _ = page
    rows = {r["id"]: r.get("data-preview") for r in soup.select("tr[data-preview]")}
    assert rows == {f"faxid_{i}": f"/faxes/thumbnail/{i}" for i in ids}


def test_the_preview_box_starts_hidden(page):
    soup, _, _ = page
    box = soup.find(id="faxpreview")
    assert box is not None and "hidden" in box["class"] and box.find("img") is not None


def test_the_script_is_loaded_and_served(page):
    soup, _, client = page
    assert any(s.get("src") == "/static/js/archive.js" for s in soup.find_all("script"))
    assert "NamiPreview" in client.get("/static/js/archive.js").text


# --- the script --------------------------------------------------------------------------------------------------------------

NODE = shutil.which("node")

HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const log = [];
function el(name, attrs) {
  const handlers = {}, classes = new Set(attrs.classes || []);
  return { name, style: {}, attrs: Object.assign({}, attrs.attrs || {}), handlers,
    classList: { add: c => classes.add(c), remove: c => classes.delete(c), contains: c => classes.has(c),
                 toggle: (c, on) => (on ? classes.add(c) : classes.delete(c)) },
    getAttribute(n) { return this.attrs[n]; }, setAttribute(n, v) { this.attrs[n] = v; },
    addEventListener(t, f) { handlers[t] = f; }, querySelector() { return img; },
    getBoundingClientRect() { return { left: attrs.left || 0, top: attrs.top || 0 }; } };
}
const img = el('img', {});
const box = el('div', { classes: ['hidden'] });
const rows = [el('tr', { attrs: { 'data-preview': '/faxes/thumbnail/7' }, left: 300, top: 120 }),
              el('tr', { attrs: { 'data-preview': '/faxes/thumbnail/8' }, left: 300, top: 900 })];
const doc = { getElementById: id => (id === 'faxpreview' ? box : null), querySelectorAll: () => rows,
              documentElement: { scrollHeight: 1000 } };
const win = { pageXOffset: 0, pageYOffset: 0 };
const ctx = vm.createContext({ window: win, document: undefined, globalThis: {} });
vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
const lib = ctx.window.NamiPreview || ctx.globalThis.NamiPreview;
lib.init(doc, win);
const out = {};
rows[0].handlers.mouseover();
out.shown = { hidden: box.classList.contains('hidden'), src: img.attrs.src, rowBackground: rows[0].style.background,
              left: box.style.left, top: box.style.top };
rows[0].handlers.mouseout();
out.hidden = { hidden: box.classList.contains('hidden'), rowBackground: rows[0].style.background };
rows[1].handlers.mousemove();
out.lowRow = { left: box.style.left, top: box.style.top };
out.place = [lib.place(50, 10, 1000), lib.place(300, 500, 1000), lib.place(300, 900, 1000), lib.place(300, 870, 1000)];
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def run():
    if not NODE:
        pytest.skip("node is not installed")
    out = subprocess.run([NODE, "-e", HARNESS, str(SCRIPT)], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_hovering_a_row_shows_its_image_beside_it_and_highlights_the_row(run):
    assert run["shown"] == {"hidden": False, "src": "/faxes/thumbnail/7", "rowBackground": "#FFF0B6", "left": "190px", "top": "120px"}


def test_leaving_the_row_puts_the_box_and_the_highlight_away(run):
    assert run["hidden"] == {"hidden": True, "rowBackground": ""}


def test_the_box_is_lifted_when_the_page_ends_below_the_row(run):
    assert run["lowRow"] == {"left": "190px", "top": "860px"}


def test_the_box_never_leaves_the_left_edge_and_is_lifted_only_when_less_than_130_px_remain(run):
    assert run["place"] == [{"left": 0, "top": 10}, {"left": 190, "top": 500}, {"left": 190, "top": 860}, {"left": 190, "top": 870}]
