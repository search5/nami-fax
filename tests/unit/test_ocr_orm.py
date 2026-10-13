"""B track, group 3d-2: FaxOCR index stored through a Session (indexing never wrote a row before)."""

from __future__ import annotations

from unittest.mock import patch

import alembic.command
import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import mysql, postgresql, sqlite
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable


def test_model_maps_the_table():
    from namifax.models import FaxOCR

    t = FaxOCR.__table__
    assert t.name == "FaxOCR" and [c.name for c in t.primary_key.columns] == ["id"]
    assert set(t.c.keys()) == {"id", "fax_id", "fax_file", "ocr_text", "page_count", "confidence", "created_at"}
    assert not t.c.fax_file.nullable and not t.c.ocr_text.nullable
    assert "LONGTEXT" in str(CreateTable(t).compile(dialect=mysql.dialect()))
    for d in (sqlite.dialect(), postgresql.dialect()):
        assert "PRIMARY KEY (id)" in str(CreateTable(t).compile(dialect=d))


@pytest.fixture
def ocr(dbsession):
    from namifax.services.ocr import OcrService

    return OcrService(db=dbsession)


def _index(ocr, name, text, pages=1, fax_id=None):
    with patch.object(ocr, "extract_text_from_tiff", return_value={"success": True, "text": text, "pages": pages}):
        return ocr.index_fax(fax_file=name, tiff_path="/x.tif", fax_id=fax_id)


def test_index_inserts_then_updates_the_same_file(ocr):
    assert _index(ocr, "fax1.tif", "hello world", 2, fax_id=5) is True
    assert ocr.get_ocr_text("fax1.tif") == "hello world"
    assert _index(ocr, "fax1.tif", "changed text", 3) is True
    assert ocr.get_ocr_text("fax1.tif") == "changed text"
    rows = ocr.search_faxes("changed")
    assert len(rows) == 1 and rows[0]["page_count"] == 3 and rows[0]["fax_id"] is None and rows[0]["created_at"]


def test_failed_extraction_stores_nothing(ocr):
    with patch.object(ocr, "extract_text_from_tiff", return_value={"success": False}):
        assert ocr.index_fax("f.tif", "/x.tif") is False
    assert ocr.get_ocr_text("f.tif") is None


def test_search_is_case_insensitive_newest_first_and_wildcards_are_literal(ocr):
    _index(ocr, "a.tif", "Invoice 100% paid for ACME")
    _index(ocr, "b.tif", "invoice 1000 unpaid")
    assert [r["fax_file"] for r in ocr.search_faxes("INVOICE")] == ["b.tif", "a.tif"]
    assert [r["fax_file"] for r in ocr.search_faxes("100%")] == ["a.tif"]        # % is not a wildcard
    assert ocr.search_faxes("a_me") == [] and ocr.search_faxes("  ") == []
    hit = ocr.search_faxes("acme")[0]
    assert "ACME" in hit["snippet"] and hit["snippet"].startswith("...")
    assert len(ocr.search_faxes("invoice", limit=1)) == 1


def test_search_text_cannot_inject_sql(ocr):
    _index(ocr, "a.tif", "secret")
    assert ocr.search_faxes("x' OR '1'='1") == []


@pytest.mark.serverdb
def test_server_database(monkeypatch, server_db_url, alembic_cfg):
    from namifax.models import FaxOCR
    from namifax.services.ocr import OcrService

    monkeypatch.setenv("DATABASE_URL", server_db_url)
    alembic.command.upgrade(alembic_cfg, "head")
    engine = sa.create_engine(server_db_url)
    try:
        with Session(engine) as s:
            o = OcrService(db=s)
            big = "한글 " * 30000
            assert _index(o, "big.tif", big) and o.get_ocr_text("big.tif") == big      # beyond 64 KB: LONGTEXT
            assert _index(o, "big.tif", "small") and o.get_ocr_text("big.tif") == "small"
            assert len(o.search_faxes("SMALL")) == 1
            s.commit()
        with Session(engine) as s:
            assert s.execute(sa.select(sa.func.count()).select_from(FaxOCR)).scalar() == 1
    finally:
        engine.dispose()


def test_store_text_saves_recognised_text_without_reading_the_file_again(ocr):
    with patch.object(ocr, "extract_text_from_tiff") as extract:
        ocr.store_text("s.tif", "already read", 2, 7)
    extract.assert_not_called()
    assert ocr.get_ocr_text("s.tif") == "already read"


def test_a_tesseract_failure_is_logged(ocr, caplog):
    from PIL import Image

    with patch("namifax.services.ocr.pytesseract.image_to_string", side_effect=RuntimeError("no tesseract")), \
         caplog.at_level("ERROR", logger="namifax"):
        assert ocr.extract_text_from_image(Image.new("L", (1, 1))) == ""
    assert "OCR failed" in caplog.text
