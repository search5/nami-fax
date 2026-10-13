from __future__ import annotations

import logging
import os
from typing import Any
from PIL import Image
import pytesseract

from datetime import datetime

from sqlalchemy import func, select

from namifax.db.missing import resolve_db
from namifax.db.textsearch import ESCAPE_CHAR, like_pattern
from namifax.models.faxocr import FaxOCR

log = logging.getLogger("namifax")

class OcrService:
    """Enterprise Fax OCR Text Extraction & Full-Text Search service."""

    def __init__(self, lang: str = "eng", db: Any = None) -> None:
        self.lang = lang
        self.db = resolve_db(db, "OcrService")

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

    def index_fax(self, fax_file: str, tiff_path: str, fax_id: int | None = None) -> bool:
        """Extract text from fax TIFF and index in FaxOCR table."""
        res = self.extract_text_from_tiff(tiff_path)
        if not res.get("success"):
            return False

        self.store_text(fax_file, res.get("text", ""), int(res.get("pages", 1)), fax_id)
        return True

    def store_text(self, fax_file: str, text: str, pages: int = 1, fax_id: int | None = None) -> None:
        """Save already-recognised text in the FaxOCR table (one row per file; a second call updates it)."""
        row = self.db.execute(select(FaxOCR).where(FaxOCR.fax_file == fax_file)).scalars().first()
        if row is None:
            row = FaxOCR(fax_file=fax_file, created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            self.db.add(row)
        row.ocr_text, row.page_count = text, int(pages)
        row.fax_id = int(fax_id) if fax_id is not None else None
        self.db.flush()

    def get_ocr_text(self, fax_file: str) -> str | None:
        """Retrieve stored OCR text for a fax file."""
        return self.db.execute(select(FaxOCR.ocr_text).where(FaxOCR.fax_file == fax_file)).scalars().first()

    def search_faxes(self, keyword: str, limit: int = 50) -> list[dict[str, Any]]:
        """Search indexed faxes by text keyword."""
        keyword = keyword.strip()
        if not keyword:
            return []

        rows = self.db.execute(
            select(FaxOCR).where(func.lower(FaxOCR.ocr_text).like(like_pattern(keyword), escape=ESCAPE_CHAR))
            .order_by(FaxOCR.id.desc()).limit(int(limit))
        ).scalars().all()

        results = []
        for r in rows:
            full_text = r.ocr_text or ""
            idx = full_text.lower().find(keyword.lower())
            if idx >= 0:
                start = max(0, idx - 40)
                end = min(len(full_text), idx + len(keyword) + 40)
                snippet = f"...{full_text[start:end]}..."
            else:
                snippet = full_text[:80] + ("..." if len(full_text) > 80 else "")
            results.append({
                "id": r.id,
                "fax_id": r.fax_id,
                "fax_file": r.fax_file,
                "snippet": snippet,
                "page_count": r.page_count if r.page_count is not None else 1,
                "created_at": str(r.created_at),
            })
        return results
