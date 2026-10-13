from unittest.mock import MagicMock, patch
import os
import pytest
from PIL import Image, ImageDraw

from namifax.services.ocr import OcrService

def test_ocr_service_init():
    svc = OcrService(lang="eng")
    assert svc.lang == "eng"

def test_extract_text_from_image_mock():
    svc = OcrService()
    with patch("pytesseract.image_to_string") as mock_tess:
        mock_tess.return_value = "CONFIDENTIAL FAX TRANSMISSION\nPage 1 of 1"
        img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        text = svc.extract_text_from_image(img)
        assert "CONFIDENTIAL" in text
        mock_tess.assert_called_once()

def test_extract_text_from_image_fail_safe():
    svc = OcrService()
    with patch("pytesseract.image_to_string", side_effect=RuntimeError("Tesseract failed")):
        img = Image.new("RGB", (50, 50))
        text = svc.extract_text_from_image(img)
        assert text == ""

def test_extract_text_from_tiff(tmp_path):
    svc = OcrService()
    tiff_file = str(tmp_path / "sample.tif")
    img1 = Image.new("RGB", (100, 100), color=(255, 255, 255))
    img2 = Image.new("RGB", (100, 100), color=(200, 200, 200))
    img1.save(tiff_file, save_all=True, append_images=[img2], format="TIFF")

    with patch("pytesseract.image_to_string", side_effect=["First Page Content", "Second Page Invoice"]):
        result = svc.extract_text_from_tiff(tiff_file)
        assert result["success"] is True
        assert result["pages"] == 2
        assert "First Page Content" in result["text"]
        assert "Second Page Invoice" in result["text"]

# indexing and searching run against a real session in test_ocr_orm.py


def test_ocr_is_kept_only_in_faxcontent_not_in_a_second_table():
    """Like the original: no FaxOCR table, no model, no second copy of the recognised text."""
    import namifax.models as models
    from namifax.models.meta import Base

    assert not hasattr(models, "FaxOCR") and "FaxOCR" not in Base.metadata.tables
    assert not hasattr(OcrService, "index_fax") and not hasattr(OcrService, "search_faxes")
