"""The page images and thumbnails of a fax (what the original's file.php handed out), only to people who may see the fax."""

from __future__ import annotations

import os

from pyramid.httpexceptions import HTTPNotFound
from pyramid.response import FileResponse
from pyramid.view import view_config

from namifax.services import fax_images
from namifax.services.archive_in import ArchiveIn
from namifax.views.fax_rights import load_fax

NOTHUMB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "images", "nothumb.gif")


def _folder(request, fid) -> str:
    """The folder of fax ``fid`` on disk, or a 404 when there is no such fax or the user may not use it."""
    arc = ArchiveIn(db=request.dbsession)
    if not str(fid).isdecimal() or not load_fax(request, arc, fid, action="image"):
        raise HTTPNotFound()
    return os.path.dirname(arc.get_pdfpath() or "")


def _send(path: str, content_type: str) -> FileResponse:
    response = FileResponse(path, request=None, content_type=content_type)
    response.cache_control.private = True
    response.cache_control.max_age = 0
    return response


@view_config(route_name="fax_image", permission="view")
def fax_image_view(request):
    """One page of the fax as a PNG; pages are counted from 1."""
    page = request.matchdict.get("page", "")
    if not page.isdecimal() or int(page) < 1:
        raise HTTPNotFound()
    path = fax_images.ensure_page(_folder(request, request.matchdict["fid"]), int(page) - 1)
    if not path:
        raise HTTPNotFound()
    return _send(path, "image/png")


@view_config(route_name="fax_thumbnail", permission="view")
def fax_thumbnail_view(request):
    """The thumbnail of the fax; a fax with no picture gets the blank one."""
    path = fax_images.ensure_thumbnail(_folder(request, request.matchdict["fid"]))
    if path:
        return _send(path, "image/png")
    return _send(NOTHUMB, "image/gif")
