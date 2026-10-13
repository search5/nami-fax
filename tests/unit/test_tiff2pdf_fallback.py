"""tiff2pdf without HylaFAX's or libtiff's own tool (the original ran ``tiff2ps | gs``): the received fax still becomes a PDF of
the right paper size that is not larger than the fax itself.

A fax is a black-and-white picture with its own resolution (204 x 196 dpi "fine", 204 x 98 dpi "normal"). The picture is kept
black and white and the PDF page is as many inches as the fax is, so that the PDF prints at the size of the page."""

from __future__ import annotations

import os

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader

from namifax.common import helpers


@pytest.fixture(autouse=True)
def _no_tiff_tool(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("tiff2pdf")

    monkeypatch.setattr("subprocess.run", missing)


def _fax(path, size=(1728, 2200), dpi=(204, 196), pages=3):
    frames = []
    for _ in range(pages):
        page = Image.new("1", size, 1)
        draw = ImageDraw.Draw(page)
        for y in range(60, size[1] - 40, 40):
            draw.text((100, y), "The quick brown fox jumps over the lazy dog " * 3, fill=0)
        frames.append(page)
    frames[0].save(path, save_all=True, append_images=frames[1:], compression="group4", dpi=dpi)
    return str(path)


def _page_inches(pdf):
    box = PdfReader(pdf).pages[0].mediabox
    return float(box.width) / 72, float(box.height) / 72


def test_a_fine_fax_is_a_page_of_its_real_size(tmp_path):
    pdf = str(tmp_path / "fax.pdf")
    assert helpers.tiff2pdf(_fax(tmp_path / "fine.tif"), pdf) is True
    width, height = _page_inches(pdf)
    assert (round(width, 1), round(height, 1)) == (8.5, 10.8)
    assert len(PdfReader(pdf).pages) == 3


def test_a_normal_fax_keeps_its_proportions(tmp_path):
    pdf = str(tmp_path / "fax.pdf")
    assert helpers.tiff2pdf(_fax(tmp_path / "normal.tif", size=(1728, 1100), dpi=(204, 98)), pdf) is True
    width, height = _page_inches(pdf)
    assert (round(width, 1), round(height, 1)) == (8.5, 11.2)


def test_the_pdf_is_not_much_larger_than_the_fax(tmp_path):
    tiff = _fax(tmp_path / "fine.tif")
    pdf = str(tmp_path / "fax.pdf")
    assert helpers.tiff2pdf(tiff, pdf) is True
    assert os.path.getsize(pdf) < 2 * os.path.getsize(tiff)


def test_a_colour_picture_still_converts(tmp_path):
    tiff = str(tmp_path / "colour.tif")
    Image.new("P", (200, 300), 3).save(tiff, dpi=(100, 100))
    pdf = str(tmp_path / "colour.pdf")
    assert helpers.tiff2pdf(tiff, pdf) is True
    assert _page_inches(pdf) == (2.0, 3.0)


def test_a_file_that_is_no_picture_fails(tmp_path):
    bad = tmp_path / "bad.tif"
    bad.write_bytes(b"not a tiff")
    assert helpers.tiff2pdf(str(bad), str(tmp_path / "bad.pdf")) is False


def test_a_fax_without_a_resolution_is_taken_as_a_fine_fax(tmp_path):
    tiff = str(tmp_path / "plain.tif")
    Image.new("1", (1728, 2200), 1).save(tiff, format="TIFF")          # (no resolution tags: Pillow reads them as 1 x 1)
    pdf = str(tmp_path / "plain.pdf")
    assert helpers.tiff2pdf(tiff, pdf) is True
    width, height = _page_inches(pdf)
    assert (round(width, 1), round(height, 1)) == (8.5, 10.8)
