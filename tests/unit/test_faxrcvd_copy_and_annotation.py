"""faxrcvd stops when the TIFF cannot be copied, can store it recompressed as Group 4 (TIFF_TO_G4), and can stamp "FaxID: N" on every
page of the PDF (ENABLE_FAX_ANNOTATION, at ANN_GRAVITY)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from pypdf import PdfReader

from namifax.common import helpers
from namifax.cli import faxrcvd as hook


def _tiff(path, pages=2, compression=None):
    frames = [Image.new("1", (400, 600), 1) for _ in range(pages)]
    kw = {"compression": compression} if compression else {}
    frames[0].save(path, save_all=True, append_images=frames[1:], format="TIFF", **kw)
    return str(path)


def test_recompression_to_group4_keeps_the_pages(tmp_path):
    src = _tiff(tmp_path / "in.tif", 3)
    dst = tmp_path / "out.tif"
    assert helpers.copy_tiff(src, str(dst), group4=True) is True
    with Image.open(dst) as img:
        assert img.n_frames == 3 and img.tag_v2.get(259) == 4          # 4 = CCITT Group 4


def test_a_plain_copy_is_byte_for_byte(tmp_path):
    src = _tiff(tmp_path / "in.tif", 2)
    dst = tmp_path / "out.tif"
    assert helpers.copy_tiff(src, str(dst)) is True and dst.read_bytes() == open(src, "rb").read()


def test_a_copy_that_cannot_be_made_is_reported(tmp_path):
    assert helpers.copy_tiff(str(tmp_path / "missing.tif"), str(tmp_path / "out.tif")) is False


@pytest.mark.parametrize("gravity", ["south", "southeast", "north", "northwest"])
def test_the_annotation_writes_a_pdf_with_every_page(tmp_path, gravity):
    src = _tiff(tmp_path / "in.tif", 3)
    out = tmp_path / "fax.pdf"
    assert helpers.annotate_fax(src, "FaxID: 42", str(out), gravity=gravity) is True
    assert len(PdfReader(str(out)).pages) == 3


def test_the_annotation_leaves_a_mark_where_asked(tmp_path):
    src = _tiff(tmp_path / "in.tif", 1)
    helpers.annotate_fax(src, "FaxID: 42", str(tmp_path / "se.pdf"), gravity="southeast")
    marked = helpers.annotated_pages(src, "FaxID: 42", gravity="southeast")[0]
    box = marked.convert("L").point(lambda v: 255 if v < 128 else 0).getbbox()
    assert box is not None and box[0] > 200 and box[1] > 300            # dark pixels in the lower right quarter only


def _run_hook(tmp_path, **flags):
    tiff = tmp_path / "fax00123.tif"
    _tiff(tiff, 1)
    session = object()
    modem = MagicMock(get_printer=MagicMock(return_value=None), get_contact=MagicMock(return_value=None),
                      get_faxcatid=MagicMock(return_value=None))
    book = MagicMock()
    book.find_or_create_number.return_value = (1, 1, "found")
    book.get_printer.return_value = book.get_category.return_value = book.get_email.return_value = None
    inbox = MagicMock()
    inbox.create.return_value = True
    inbox.get_fid.return_value = 77
    with patch.multiple(hook, FaxModem=MagicMock(return_value=modem), NFAddressBook=MagicMock(return_value=book),
                        ArchiveIn=MagicMock(return_value=inbox), DIDRouting=MagicMock(), BarcodeRouting=MagicMock(), ARCHIVE=str(tmp_path / "arch"),
                        **flags), \
            patch.object(hook, "faxinfo", return_value={"Sender": "1", "Pages": "1", "Received": "2026:10:01 10:00:00"}), \
            patch.object(hook, "static_preview"), patch.object(hook, "send_mail"), patch.object(hook, "bardecode", return_value=None), \
            patch("namifax.services.ocr.OcrService"):
        code = hook.run_faxrcvd(["faxrcvd.py", str(tiff), "ttyS0", "comm01", "none"], session=session)
    return code, inbox


def test_the_hook_stops_when_the_copy_fails(tmp_path):
    with patch.object(hook, "copy_tiff", return_value=False):
        code, inbox = _run_hook(tmp_path)
    assert code == 0 and not inbox.create.called


def test_the_hook_stamps_the_fax_id_when_asked(tmp_path):
    code, inbox = _run_hook(tmp_path, ENABLE_FAX_ANNOTATION=True)
    pdfs = [os.path.join(r, f) for r, _d, fs in os.walk(tmp_path / "arch") for f in fs if f == "fax.pdf"]
    assert pdfs and len(PdfReader(pdfs[0]).pages) == 1
