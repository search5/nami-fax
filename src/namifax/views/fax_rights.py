"""Rights checks the fax views share (see ``namifax.services.fax_access``)."""

from __future__ import annotations

from typing import Any

from namifax.common.helpers import avantfaxlog
from namifax.services.fax_access import FaxAccess


def fax_access(request: Any) -> FaxAccess:
    """The signed-in user's rights, read once per request."""
    cached = getattr(request, "_fax_access", None)
    if cached is None:
        cached = FaxAccess.for_request(request)
        try:
            request._fax_access = cached
        except AttributeError:
            pass
    return cached


def load_fax(request: Any, archive: Any, fid: Any, *, action: str, delete: bool = False) -> bool:
    """Load fax ``fid`` into ``archive`` if it exists and the user may use it (or delete it, with ``delete``).

    A refusal is written to the log, like the original's "Access denied to ..." entries, and answers False.
    """
    try:
        fid = int(fid)
    except (TypeError, ValueError):
        return False
    if not archive.load_fax(fid):
        return False
    access = fax_access(request)
    if (access.may_delete(archive) if delete else access.may_use(archive)):
        return True
    avantfaxlog(f"{action}> Access denied to {'delete' if delete else 'use'} fax '{fid}' by {access.username}",
                session=request.dbsession)
    return False
