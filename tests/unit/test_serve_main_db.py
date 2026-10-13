"""Spec 48 loop C5: serve_main ensures the schema through ensure_schema() and reports Pyramid startup failures."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import importlib

main_mod = importlib.import_module("namifax.main")  # `namifax.main` is also a function name in the package


def _serve(monkeypatch, make_app):
    monkeypatch.setenv("NAMIFAX_ENABLE_SCHEDULER", "0")
    calls = []

    def fake_ensure_schema(engine):
        calls.append(1)

    server = MagicMock()
    server.__enter__.return_value.serve_forever.side_effect = KeyboardInterrupt
    with patch.object(main_mod, "ensure_schema", fake_ensure_schema), \
            patch.object(main_mod, "make_server", return_value=server) as ms, \
            patch("namifax.create_app", make_app):
        code = main_mod.serve_main(["--port", "0"])
    return code, calls, ms


def test_serve_ensures_the_schema_without_a_global_engine(monkeypatch):
    pyramid_app = object()
    code, calls, ms = _serve(monkeypatch, MagicMock(return_value=pyramid_app))
    assert code == 0 and calls == [1]
    assert ms.call_args.args[2] is pyramid_app


def _ini(tmp_path, body="session.secret = from-ini\nsession.secure = true\ncsrf.trusted_origins = https://fax.example.com\nsecret.key = k\n"):
    path = tmp_path / "app.ini"
    path.write_text("[app:main]\nuse = egg:namifax\n" + body + "\n")
    return str(path)


def test_serve_without_config_calls_create_app_without_settings(monkeypatch):
    monkeypatch.delenv("NAMIFAX_INI", raising=False)
    make_app = MagicMock(return_value=object())
    _serve(monkeypatch, make_app)
    make_app.assert_called_once_with()


def test_serve_config_option_passes_the_ini_app_settings(monkeypatch, tmp_path):
    monkeypatch.delenv("NAMIFAX_INI", raising=False)
    make_app = MagicMock(return_value=object())
    monkeypatch.setenv("NAMIFAX_ENABLE_SCHEDULER", "0")
    server = MagicMock()
    server.__enter__.return_value.serve_forever.side_effect = KeyboardInterrupt
    with patch.object(main_mod, "ensure_schema"), patch.object(main_mod, "make_server", return_value=server), \
            patch("namifax.create_app", make_app):
        code = main_mod.serve_main(["--port", "0", "--config", _ini(tmp_path)])
    assert code == 0
    kwargs = make_app.call_args.kwargs
    assert kwargs["session.secret"] == "from-ini"
    assert kwargs["session.secure"] == "true"
    assert kwargs["csrf.trusted_origins"] == "https://fax.example.com"
    assert kwargs["secret.key"] == "k"


def test_serve_reads_the_ini_named_by_namifax_ini(monkeypatch, tmp_path):
    monkeypatch.setenv("NAMIFAX_INI", _ini(tmp_path))
    make_app = MagicMock(return_value=object())
    code, _calls, _ms = _serve(monkeypatch, make_app)
    assert code == 0
    assert make_app.call_args.kwargs["session.secret"] == "from-ini"


def test_serve_ini_sqlalchemy_url_is_used_for_the_schema(monkeypatch, tmp_path):
    monkeypatch.delenv("NAMIFAX_INI", raising=False)
    monkeypatch.setenv("NAMIFAX_ENABLE_SCHEDULER", "0")
    seen = {}

    def fake_resolve(settings, env):
        seen.update(settings)
        return "sqlite://"

    server = MagicMock()
    server.__enter__.return_value.serve_forever.side_effect = KeyboardInterrupt
    with patch.object(main_mod, "resolve_database_url", fake_resolve), patch.object(main_mod, "ensure_schema"), \
            patch.object(main_mod, "make_server", return_value=server), patch("namifax.create_app", MagicMock()):
        main_mod.serve_main(["--config", _ini(tmp_path, "sqlalchemy.url = sqlite:///x.db\n")])
    assert seen["sqlalchemy.url"] == "sqlite:///x.db"


def test_serve_missing_ini_fails_with_a_message(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("NAMIFAX_INI", raising=False)
    code = main_mod.serve_main(["--config", str(tmp_path / "nope.ini")])
    assert code == 1
    assert "nope.ini" in capsys.readouterr().err
