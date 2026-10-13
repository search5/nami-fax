from __future__ import annotations

import logging
import os
from typing import Any
from PIL import Image
import pytesseract

log = logging.getLogger("namifax")

class OcrService:
    """Fax OCR text extraction (Tesseract). The text is stored in FaxArchive.faxcontent by the callers."""

    def __init__(self, lang: str = "eng") -> None:
        self.lang = lang

    def extract_text_from_image(self, image: Image.Image | str) -> str:
        """Extract text from a single image or file path using Tesseract."""
        try:
            if isinstance(image, str):
                if not os.path.exists(image):
                    return ""
                with Image.open(image) as img:
                    return pytesseract.image_to_string(img, lang=self.lang).strip()
            else:
                return pytesseract.image_to_string(image, lang=self.lang).strip()
        except Exception:
            log.exception("OCR failed for %s", image if isinstance(image, str) else "an image")
            return ""

    def extract_text_from_tiff(self, tiff_path: str) -> dict[str, Any]:
        """Extract combined text across all pages of a multi-page TIFF."""
        if not os.path.exists(tiff_path):
            return {"success": False, "error": f"File not found: {tiff_path}", "text": "", "pages": 0}

        try:
            extracted_pages = []
            with Image.open(tiff_path) as img:
                n_frames = getattr(img, "n_frames", 1)
                for frame_idx in range(n_frames):
                    img.seek(frame_idx)
                    page_text = self.extract_text_from_image(img.copy())
                    if page_text:
                        extracted_pages.append(page_text)

            combined_text = "\n\n--- Page Break ---\n\n".join(extracted_pages)
            return {
                "success": True,
                "text": combined_text,
                "pages": n_frames,
            }
        except Exception as e:
            log.exception("OCR failed for %s", tiff_path)
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "pages": 0,
            }
