"""P4: the avantfax copy and the JSON fallback web app are gone; startup failures are not masked."""

from __future__ import annotations

import importlib
import importlib.util
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

main_mod = importlib.import_module("namifax.main")  # `namifax.main` is also a function name in the package


def test_avantfax_copy_is_removed():
    assert importlib.util.find_spec("avantfax") is None


def test_json_fallback_web_app_is_removed():
    assert importlib.util.find_spec("namifax.web") is None


@pytest.mark.parametrize("name", ["ocr_import", "create_thumbnails", "import_users", "import_blacklist", "reroute"])
def test_batch_tools_live_in_namifax_cli(name):
    assert importlib.util.find_spec(f"namifax.cli.{name}") is not None


def test_serve_main_does_not_fall_back_when_pyramid_app_fails(monkeypatch, capsys):
    monkeypatch.setenv("NAMIFAX_ENABLE_SCHEDULER", "0")

    with patch.object(main_mod, "ensure_schema", lambda engine: None), \
            patch.object(main_mod, "make_server") as make_server, \
            patch("namifax.create_app", MagicMock(side_effect=RuntimeError("db is down"))):
        code = main_mod.serve_main(["--port", "0"])

    assert code == 1
    make_server.assert_not_called()
    err = capsys.readouterr().err
    assert "db is down" in err
