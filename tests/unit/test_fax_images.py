"""Page images and thumbnails of a fax are served to people who may see the fax, and made from the TIFF when missing."""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import update

from namifax.models import FaxArchive
from namifax.services import fax_images
from test_fax_access_control import _fax, _login, world  # noqa: F401


def _tiff(folder: Path, pages=3, size=(1728, 2200)):
    frames = [Image.new("1", size, color=1 if i % 2 else 0) for i in range(pages)]
    frames[0].save(folder / "fax.tif", save_all=True, append_images=frames[1:], compression="group4")


@pytest.fixture
def faxes(world, tmp_path):
    folder = Path(world.db.get(FaxArchive, world.fax["A"]).faxpath)
    _tiff(folder)
    world.db.execute(update(FaxArchive).where(FaxArchive.fid == world.fax["A"]).values(pages=3))
    world.db.flush()
    world.folder = folder
    return world


def test_previews_are_rendered_at_the_original_sizes(tmp_path):
    _tiff(tmp_path, pages=2)
    assert fax_images.render_previews(str(tmp_path)) == 2
    assert Image.open(tmp_path / "page0.png").width == 750 and Image.open(tmp_path / "page1.png").width == 750
    assert Image.open(tmp_path / "thumb.png").width == 80


def test_a_missing_page_is_made_on_demand(tmp_path):
    _tiff(tmp_path, pages=2)
    assert fax_images.ensure_page(str(tmp_path), 1) and (tmp_path / "page1.png").exists()
    assert fax_images.ensure_page(str(tmp_path), 5) is None and fax_images.ensure_page(str(tmp_path), -1) is None


def test_the_page_image_is_served(faxes):
    res = _login(faxes, "alice").get(f"/faxes/image/{faxes.fax['A']}/1")
    assert res.content_type == "image/png" and Image.open(io.BytesIO(res.body)).width == 750


def test_a_page_that_does_not_exist_is_a_404(faxes):
    assert _login(faxes, "alice").get(f"/faxes/image/{faxes.fax['A']}/9", expect_errors=True).status_int == 404
    assert _login(faxes, "alice").get(f"/faxes/image/{faxes.fax['A']}/0", expect_errors=True).status_int == 404
    assert _login(faxes, "alice").get(f"/faxes/image/{faxes.fax['A']}/x", expect_errors=True).status_int == 404


def test_somebody_without_the_right_gets_no_image(faxes):
    for user in ("bob", "carl"):
        assert _login(faxes, user).get(f"/faxes/image/{faxes.fax['A']}/1", expect_errors=True).status_int in (403, 404), user
        assert _login(faxes, user).get(f"/faxes/thumbnail/{faxes.fax['A']}", expect_errors=True).status_int in (403, 404), user


def test_the_thumbnail_is_served_and_falls_back_to_the_blank_one(faxes):
    res = _login(faxes, "alice").get(f"/faxes/thumbnail/{faxes.fax['A']}")
    assert res.content_type == "image/png" and Image.open(io.BytesIO(res.body)).width == 80
    res = _login(faxes, "dan").get(f"/faxes/thumbnail/{faxes.fax['C']}")          # C has no TIFF at all
    assert res.status_int == 200 and res.content_type.startswith("image/")


def test_the_images_need_a_login(faxes):
    import webtest
    anon = webtest.TestApp(faxes.app, extra_environ=faxes.env)
    assert anon.get(f"/faxes/image/{faxes.fax['A']}/1", expect_errors=True).status_int in (302, 303, 401, 403)


def test_the_thumbnail_is_not_a_path_to_other_files(faxes):
    assert _login(faxes, "alice").get("/faxes/image/../../etc/passwd/1", expect_errors=True).status_int == 404
