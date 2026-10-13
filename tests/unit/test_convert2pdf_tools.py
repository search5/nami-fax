"""convert2pdf (the original's, which ran ``tiff2ps | gs`` and Ghostscript with ``-sPAPERSIZE=$PAPERSIZE``): PostScript is converted
for the configured paper size (PAPERSIZE, a4 by default), and a TIFF becomes pages of its real size that stay black and white."""

from __future__ import annotations

import os
import subprocess

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader

from namifax.common import helpers


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("PAPERSIZE", raising=False)


@pytest.fixture
def ghostscript_calls(monkeypatch):
    calls = []

    def fake(argv, *args, **kwargs):
        calls.append(list(argv))
        return subprocess.CompletedProcess(argv, 1, b"", b"")                 # (fails: only the command line is looked at)

    monkeypatch.setattr(helpers, "settings_binary", lambda name: "/usr/bin/gs")
    monkeypatch.setattr(helpers.subprocess, "run", fake)
    return calls


def _postscript(tmp_path):
    path = tmp_path / "doc.ps"
    path.write_text("%!PS\n/Helvetica findfont 24 scalefont setfont 72 700 moveto (hello) show showpage\n")
    return str(path)


def test_postscript_is_converted_for_a4_by_default(tmp_path, ghostscript_calls):
    helpers.convert2pdf(str(tmp_path / "out"), [_postscript(tmp_path)])
    assert "-sPAPERSIZE=a4" in ghostscript_calls[0]


def test_the_paper_size_can_be_changed(tmp_path, ghostscript_calls, monkeypatch):
    monkeypatch.setenv("PAPERSIZE", "letter")
    helpers.convert2pdf(str(tmp_path / "out"), [_postscript(tmp_path)])
    assert "-sPAPERSIZE=letter" in ghostscript_calls[0]


def _fax_tiff(path, pages=3):
    frames = []
    for _ in range(pages):
        page = Image.new("1", (1728, 2200), 1)
        draw = ImageDraw.Draw(page)
        for y in range(60, 2160, 40):
            draw.text((100, y), "The quick brown fox jumps over the lazy dog " * 3, fill=0)
        frames.append(page)
    frames[0].save(path, save_all=True, append_images=frames[1:], compression="group4", dpi=(204, 196))
    return str(path)


def test_a_tiff_keeps_its_real_page_size_and_stays_black_and_white(tmp_path, monkeypatch):
    monkeypatch.setattr("subprocess.run", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("tiff2pdf")))
    tiff = _fax_tiff(tmp_path / "fax.tif")
    assert helpers.convert2pdf(str(tmp_path / "out"), [tiff]) is True
    pdf = str(tmp_path / "out" / "fax.pdf")
    reader = PdfReader(pdf)
    box = reader.pages[0].mediabox
    assert len(reader.pages) == 3 and (round(float(box.width) / 72, 1), round(float(box.height) / 72, 1)) == (8.5, 10.8)
    assert os.path.getsize(pdf) < 2 * os.path.getsize(tiff)
