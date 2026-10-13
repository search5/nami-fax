"""Files in the package's static folder that nothing refers to are removed (recorded in the wiki, known-gaps-and-decisions)."""

from __future__ import annotations

from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "src" / "namifax" / "static"


def test_theme_css_is_removed():
    assert not (STATIC / "theme.css").exists()
