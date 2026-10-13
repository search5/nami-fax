"""namifax.cli.create_thumbnails

Batch thumbnail generation matching legacy tools/create_thumbnails.php.
"""

from __future__ import annotations

import os
import sys

from typing import Any

from namifax.common.helpers import pdf_preview
from namifax.db.provider import cli_session
from namifax.services.archive_base import FaxPDFArchive, PREVIMG, PREVIMGSFX


def main(args=None, *, db: Any = None):
    if args is None:
        args = sys.argv[1:]

    if db is not None:
        return _create_thumbnails(db)
    with cli_session(ensure_schema=True) as opened:
        return _create_thumbnails(opened)


def _create_thumbnails(db: Any) -> int:
    criteria = {
        "start_date": None,
        "end_date": None,
        "keywords": None,
        "companyid": None,
        "sentrecvd": "*",
        "category": None,
        "faxid": None,
        "userid": None,
        "categories": None,
        "modemdevs": None,
        "didroutes": None,
        "superuser": True,
    }

    archive = FaxPDFArchive(db=db)
    results = archive.search_archive(criteria)

    if results:
        print(f"{results} faxes in Archive")
        fax = FaxPDFArchive(db=db)
        while True:
            fid = archive.next_archive_entry()
            if not fid:
                break

            fax.load_fax(fid)
            thumbnail = fax.get_thumbnail() or ""
            path = os.path.dirname(thumbnail)
            preview = os.path.join(path, f"{PREVIMG}0{PREVIMGSFX}")

            if os.path.isfile(thumbnail) and os.path.isfile(preview):
                continue

            print(f"Creating images in: {path}")
            pdf_preview(path)
    else:
        print("No faxes found")

    print("Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
