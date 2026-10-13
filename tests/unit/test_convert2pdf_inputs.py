"""convert2pdf like the original: PDFs, PostScript and TIFFs all end up in fax.pdf (cover page first), a file it cannot convert
makes the whole call fail instead of being dropped silently, and the result is a PDF with the right pages."""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter

from namifax.common.helpers import convert2pdf


def _pdf(path, pages=1, size=(200, 300)):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=size[0], height=size[1])
    with open(path, "wb") as out:
        writer.write(out)
    return str(path)


def _tiff(path, pages=2):
    frames = [Image.new("1", (200, 300), color=1) for _ in range(pages)]
    frames[0].save(path, save_all=True, append_images=frames[1:], format="TIFF", compression="group4")
    return str(path)


def _pages(path):
    return len(PdfReader(str(path)).pages)


def test_pdfs_are_merged(tmp_path):
    out = tmp_path / "out"
    assert convert2pdf(str(out), [_pdf(tmp_path / "a.pdf", 2), _pdf(tmp_path / "b.pdf", 1)]) is True
    assert _pages(out / "fax.pdf") == 3


def test_pdf_and_tiff_are_merged(tmp_path):
    out = tmp_path / "out"
    assert convert2pdf(str(out), [_pdf(tmp_path / "a.pdf", 1), _tiff(tmp_path / "b.tif", 2)]) is True
    assert _pages(out / "fax.pdf") == 3


def test_the_cover_page_comes_first(tmp_path):
    out = tmp_path / "out"
    cover = _pdf(tmp_path / "faxcover.pdf", 1, size=(100, 100))
    body = _pdf(tmp_path / "body.pdf", 1, size=(200, 300))
    assert convert2pdf(str(out), [body, cover]) is True
    first = PdfReader(str(out / "fax.pdf")).pages[0]
    assert float(first.mediabox.width) == 100


def test_postscript_goes_through_ghostscript(tmp_path):
    ps = tmp_path / "doc.ps"
    ps.write_text("%!PS\nshowpage\n")
    out = tmp_path / "out"

    def fake_gs(argv, **kw):
        target = next(a for a in argv if a.startswith("-sOutputFile=")).split("=", 1)[1]
        _pdf(target, 2)
        return MagicMock(returncode=0)

    with patch("shutil.which", side_effect=lambda n: "/usr/bin/gs" if n == "gs" else None), patch("subprocess.run", side_effect=fake_gs):
        assert convert2pdf(str(out), [str(ps)]) is True
    assert _pages(out / "fax.pdf") == 2


def test_postscript_without_ghostscript_fails_instead_of_being_dropped(tmp_path):
    ps = tmp_path / "doc.ps"
    ps.write_text("%!PS\nshowpage\n")
    with patch("shutil.which", return_value=None):
        assert convert2pdf(str(tmp_path / "out"), [str(ps)]) is False
    assert not (tmp_path / "out" / "fax.pdf").exists()


def test_an_unreadable_file_makes_the_call_fail(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"garbage")
    assert convert2pdf(str(tmp_path / "out"), [_pdf(tmp_path / "a.pdf"), str(bad)]) is False


def test_a_missing_file_is_skipped_like_the_original_but_nothing_at_all_fails(tmp_path):
    assert convert2pdf(str(tmp_path / "out"), []) is False
    assert convert2pdf(str(tmp_path / "out"), [str(tmp_path / "ghost.tif")]) is False
    assert convert2pdf(str(tmp_path / "out2"), [str(tmp_path / "ghost.tif"), _pdf(tmp_path / "a.pdf")]) is True
