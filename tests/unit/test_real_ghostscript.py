"""With a real Ghostscript: PostScript becomes PDF pages, a sent fax's PDF gets a thumbnail and page images. Skipped without gs."""

from __future__ import annotations

import shutil

import pytest
from PIL import Image
from pypdf import PdfReader

from namifax.common.helpers import convert2pdf, pdf_preview

pytestmark = pytest.mark.skipif(shutil.which("gs") is None, reason="Ghostscript is not installed")

PS = "%!PS\n/Helvetica findfont 24 scalefont setfont 72 700 moveto ({}) show showpage\n"


def test_postscript_files_become_pdf_pages(tmp_path):
    first, second = tmp_path / "a.ps", tmp_path / "b.ps"
    first.write_text(PS.format("one"))
    second.write_text(PS.format("two"))
    assert convert2pdf(str(tmp_path / "out"), [str(first), str(second)]) is True
    assert len(PdfReader(str(tmp_path / "out" / "fax.pdf")).pages) == 2


def test_postscript_and_tiff_together(tmp_path):
    ps = tmp_path / "a.ps"
    ps.write_text(PS.format("cover"))
    tif = tmp_path / "b.tif"
    frames = [Image.new("1", (400, 600), 1) for _ in range(2)]
    frames[0].save(tif, save_all=True, append_images=frames[1:], format="TIFF", compression="group4")
    assert convert2pdf(str(tmp_path / "out"), [str(ps), str(tif)]) is True
    assert len(PdfReader(str(tmp_path / "out" / "fax.pdf")).pages) == 3


def test_a_broken_postscript_fails_the_call(tmp_path):
    ps = tmp_path / "bad.ps"
    ps.write_text("%!PS\nthis is not (postscript\n")
    assert convert2pdf(str(tmp_path / "out"), [str(ps)]) is False


def test_a_sent_fax_gets_real_page_images_and_a_thumbnail(tmp_path):
    ps = tmp_path / "a.ps"
    ps.write_text(PS.format("page") + PS.format("two"))
    folder = tmp_path / "sent"
    assert convert2pdf(str(folder), [str(ps)]) is True
    assert pdf_preview(str(folder)) is True
    assert Image.open(folder / "thumb.png").width == 80
    assert (folder / "page0.png").exists() and (folder / "page1.png").exists()
    assert Image.open(folder / "page0.png").getbbox() is not None
