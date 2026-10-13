"""The fax viewer like viewfax.php: the real page images, previous/next fax, the fax's actions, and inbox-only access."""

from __future__ import annotations

from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from PIL import Image
from sqlalchemy import update

from namifax.models import FaxArchive
from test_fax_access_control import _fax, _login, world  # noqa: F401


@pytest.fixture
def view(world):
    """dan (ttyS0, can_del) sees A and two newer faxes N1, N2; A has 3 pages."""
    folder = Path(world.db.get(FaxArchive, world.fax["A"]).faxpath)
    frames = [Image.new("1", (1728, 2200), color=1) for _ in range(3)]
    frames[0].save(folder / "fax.tif", save_all=True, append_images=frames[1:], compression="group4")
    world.db.execute(update(FaxArchive).where(FaxArchive.fid == world.fax["A"]).values(pages=3))
    for name in ("N1", "N2"):
        world.fax[name] = _fax(world.db, folder.parent, name, modemdev="ttyS0")
    world.db.flush()
    return world


def _page(world, fid, user="dan", **kw):
    return BeautifulSoup(_login(world, user).get(f"/viewfax?fid={fid}", **kw).text, "html.parser")


def test_every_page_has_its_image_and_a_thumbnail(view):
    soup = _page(view, view.fax["A"])
    fid = view.fax["A"]
    main = [i["src"] for i in soup.select("#viewfaximage img")]
    assert f"/faxes/image/{fid}/1" in main
    thumbs = [i["src"] for i in soup.select("#faxesmenu img")]
    assert thumbs == [f"/faxes/image/{fid}/{n}" for n in (1, 2, 3)]
    assert "High-Resolution Raster Preview" not in soup.get_text()


def test_previous_and_next_fax_follow_the_inbox_order(view):
    a, n1, n2 = view.fax["A"], view.fax["N1"], view.fax["N2"]
    order = sorted([a, n1, n2], reverse=True)               # newest first
    soup = _page(view, order[1])
    hrefs = [x["href"] for x in soup.select("#sidemenu a")]
    assert f"/viewfax?fid={order[0]}" in hrefs and f"/viewfax?fid={order[2]}" in hrefs
    first = [x["href"] for x in _page(view, order[0]).select("#sidemenu a")]
    assert not any(h == f"/viewfax?fid={order[0]}" for h in first) and f"/viewfax?fid={order[1]}" in first


def test_the_actions_of_the_original_are_there(view):
    fid = view.fax["A"]
    soup = _page(view, fid)
    hrefs = " ".join(x.get("href", "") for x in soup.select("#sidemenu a"))
    for needle in (f"/faxes/download/{fid}?format=pdf", f"/refax?fid={fid}", f"/email?fid={fid}", f"/note?fid={fid}", f"/delete?fid={fid}"):
        assert needle in hrefs, needle
    rotate = soup.select_one('#sidemenu form[action^="/faxes/rotate/"]')
    assert rotate["method"].lower() == "post" and rotate.find("input", {"name": "csrf_token"})["value"]
    archive = soup.select_one('#sidemenu form[action="/ajax/archivefax"]')
    assert archive.find("input", {"name": "fids"})["value"] == str(fid)


def test_someone_who_cannot_delete_gets_no_delete_link(view):
    soup = _page(view, view.fax["A"], user="alice")
    assert "/delete?fid=" not in " ".join(x.get("href", "") for x in soup.select("#sidemenu a"))


def test_the_sender_and_the_numbers_are_shown(view):
    text = _page(view, view.fax["A"]).get_text(" ", strip=True)
    assert "Pages" in text and f"FaxID" in text and str(view.fax["A"]) in text


def test_a_fax_that_is_not_in_the_inbox_goes_back_to_the_inbox(view):
    res = _login(view, "alice").get(f"/viewfax?fid={view.fax['S']}")
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox")


def test_a_fax_the_user_may_not_see_goes_back_to_the_inbox(view):
    res = _login(view, "bob").get(f"/viewfax?fid={view.fax['A']}")
    assert res.status_int == 302 and res.headers["Location"].endswith("/inbox")
    assert _login(view, "bob").get("/viewfax?fid=99999").status_int == 302


def test_archiving_from_the_viewer_moves_on_to_the_next_fax(view):
    n1 = view.fax["N1"]
    res = _login(view, "dan").post("/ajax/archivefax", {"fids": str(n1), "next": str(view.fax["A"])})
    assert res.status_int == 302 and res.headers["Location"].endswith(f"/viewfax?fid={view.fax['A']}")
    res = _login(view, "dan").post("/ajax/archivefax", {"fids": str(view.fax["N2"]), "next": "-1"})
    assert res.headers["Location"].endswith("/inbox")
