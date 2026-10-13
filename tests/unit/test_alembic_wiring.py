"""B0-3: Alembic is wired to the application's database URL resolution and metadata."""

from __future__ import annotations

import re
import shutil
import sqlite3
from pathlib import Path

import alembic.command
import alembic.config
import pytest

ROOT = Path(__file__).resolve().parents[2]
PKG_ALEMBIC = ROOT / "src" / "namifax" / "alembic"


def _make_cfg(tmp_path: Path, app_url: str | None = None) -> alembic.config.Config:
    """Copy development.ini next to a private copy of the migration environment."""
    scripts = tmp_path / "alembic"
    shutil.copytree(PKG_ALEMBIC, scripts)
    ini = (ROOT / "development.ini").read_text()
    ini = re.sub(r"(?m)^script_location\s*=.*$", f"script_location = {scripts}", ini)
    if app_url:
        ini = ini.replace("[app:main]\n", f"[app:main]\nsqlalchemy.url = {app_url}\n", 1)
    ini_path = tmp_path / "test.ini"
    ini_path.write_text(ini)
    return alembic.config.Config(str(ini_path))


def _tables(db_file: Path) -> set[str]:
    con = sqlite3.connect(db_file)
    try:
        return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()


def test_migration_environment_files_exist():
    assert (PKG_ALEMBIC / "env.py").is_file()
    assert (PKG_ALEMBIC / "script.py.mako").is_file()
    assert (PKG_ALEMBIC / "versions").is_dir()


@pytest.mark.parametrize("ini", ["development.ini", "production.ini"])
def test_ini_files_point_alembic_at_the_package(ini):
    text = (ROOT / ini).read_text()
    assert "[alembic]" in text
    assert re.search(r"(?m)^script_location\s*=\s*namifax:alembic\s*$", text)


def test_upgrade_runs_against_the_database_url_from_the_environment(tmp_path, monkeypatch):
    db_file = tmp_path / "env.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    cfg = _make_cfg(tmp_path)

    alembic.command.revision(cfg, message="smoke", autogenerate=False)
    alembic.command.upgrade(cfg, "head")

    assert "alembic_version" in _tables(db_file)


def test_application_setting_beats_the_environment(tmp_path, monkeypatch):
    env_file, app_file = tmp_path / "env.db", tmp_path / "app.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{env_file}")
    cfg = _make_cfg(tmp_path, app_url=f"sqlite:///{app_file}")

    alembic.command.revision(cfg, message="smoke", autogenerate=False)
    alembic.command.upgrade(cfg, "head")

    assert app_file.exists() and "alembic_version" in _tables(app_file)
    assert not env_file.exists()


def test_target_metadata_is_the_application_base_metadata():
    from namifax.models.meta import Base

    env_src = (PKG_ALEMBIC / "env.py").read_text()
    assert "target_metadata = Base.metadata" in env_src
    assert "resolve_database_url" in env_src
