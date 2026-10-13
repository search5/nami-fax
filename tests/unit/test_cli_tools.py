"""Unit tests for administrative batch CLI tools."""

import io
import sys
from unittest.mock import patch
import pytest

from namifax.cli import (
    ocr_import,
    create_thumbnails,
    import_users,
    import_blacklist,
    reroute,
)


def test_ocr_import_disabled_exit():
    """Verify ocr_import exits with config warning when OCR support is not enabled."""
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        code = ocr_import.main([])
    assert code == 0
    assert "You must enable ENABLE_OCR_SUPPORT in local_config.php first" in captured.getvalue()


def test_create_thumbnails_empty_archive(seeded_db):
    """Verify create_thumbnails handles empty archive and reports Done."""
    seeded_db.query("DELETE FROM FaxArchive")
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        code = create_thumbnails.main([], db=seeded_db)
    assert code == 0
    assert "No faxes found" in captured.getvalue()
    assert "Done" in captured.getvalue()


def test_import_users_no_args_usage():
    """Verify import_users without arguments displays usage text."""
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        code = import_users.main([])
    assert code == 0
    assert "usage: import_users.php filename" in captured.getvalue()
    assert "John Doe\tjohndoe\tpassw0rd\tjohn.doe@mycompany.com" in captured.getvalue()


def test_import_blacklist_no_args_usage():
    """Verify import_blacklist without arguments displays usage text."""
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        code = import_blacklist.main([])
    assert code == 0
    assert "usage: import_blacklist.php filename [device]" in captured.getvalue()
    assert "One CallID (fax number) per line" in captured.getvalue()


def test_reroute_no_args_usage():
    """Verify reroute without arguments displays usage text."""
    captured = io.StringIO()
    with patch("sys.stdout", captured):
        code = reroute.main([])
    assert code == 0
    assert "Usage: reroute.php [device | DIDnum] email-address" in captured.getvalue()
