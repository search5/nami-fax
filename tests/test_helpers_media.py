"""Unit tests for media processing helpers (tiff2pdf, faxinfo, static_preview)."""

import os
import tempfile
import pytest
from PIL import Image

from namifax.common.helpers import (
    faxinfo,
    tiff2pdf,
    static_preview,
    pdf_preview,
    convert2pdf,
)


@pytest.fixture
def sample_multipage_tiff():
    """Create a temporary 2-page TIFF file for testing."""
    fd, path = tempfile.mkstemp(suffix=".tif")
    os.close(fd)

    img1 = Image.new("1", (200, 300), color=1)
    img2 = Image.new("1", (200, 300), color=0)
    img1.save(path, save_all=True, append_images=[img2], format="TIFF")

    yield path

    if os.path.exists(path):
        os.remove(path)


def test_faxinfo_parses_multipage_tiff(sample_multipage_tiff):
    info = faxinfo(sample_multipage_tiff)
    assert info is not None
    assert int(info["Pages"]) == 2
    assert "Received" in info
    assert "Sender" in info


def test_faxinfo_nonexistent_file():
    assert faxinfo("/tmp/definitely_not_existing_file_12345.tif") is None


def test_tiff2pdf_creates_valid_pdf(sample_multipage_tiff):
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "output.pdf")
        ret = tiff2pdf(sample_multipage_tiff, pdf_path)

        assert ret is True
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 100

        # Verify it starts with standard PDF magic bytes
        with open(pdf_path, "rb") as f:
            header = f.read(5)
            assert header == b"%PDF-"


def test_static_preview_generates_thumbnails(sample_multipage_tiff):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Place fax.tif in tmpdir
        dest_tif = os.path.join(tmpdir, "fax.tif")
        with open(sample_multipage_tiff, "rb") as src, open(dest_tif, "wb") as dst:
            dst.write(src.read())

        ret = static_preview(tmpdir, pages=2)
        assert ret is True

        thumb_path = os.path.join(tmpdir, "thumb.png")
        assert os.path.exists(thumb_path)
        assert os.path.getsize(thumb_path) > 50

        # Verify preview files
        prev0 = os.path.join(tmpdir, "page0.png")
        assert os.path.exists(prev0)
        assert os.path.getsize(prev0) > 50


def test_pdf_preview_fallback(sample_multipage_tiff):
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "fax.pdf")
        tiff2pdf(sample_multipage_tiff, pdf_path)

        ret = pdf_preview(tmpdir)
        assert ret is True
        thumb_path = os.path.join(tmpdir, "thumb.png")
        assert os.path.exists(thumb_path)
