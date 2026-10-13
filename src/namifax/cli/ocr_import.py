"""namifax.cli.ocr_import

OCR import batch tool matching legacy tools/ocr_import.php.
"""

from __future__ import annotations

import os
import sys

from typing import Any

from namifax.common.helpers import ocr_faxcontent
from namifax.db.provider import cli_session
from namifax.services.archive_base import FaxPDFArchive

ENABLE_OCR_SUPPORT = os.environ.get("ENABLE_OCR_SUPPORT", "0") in ("1", "true", "True")


def main(args=None, *, db: Any = None):
    if args is None:
        args = sys.argv[1:]

    if not ENABLE_OCR_SUPPORT:
        print("You must enable ENABLE_OCR_SUPPORT in local_config.php first")
        return 0

    if db is not None:
        return _ocr_import(db)
    with cli_session(ensure_schema=True) as opened:
        return _ocr_import(opened)


def _ocr_import(db: Any) -> int:

    criteria = {
        "start_date": None,
        "end_date": None,
        "keywords": None,
        "companyid": None,
        "sentrecvd": None,
        "category": None,
        "userid": None,
        "categories": None,
        "modemdevs": None,
        "didroutes": None,
        "superuser": True,
    }

    archive = FaxPDFArchive(db=db)
    num_results = archive.search_archive(criteria)
    print(f"{num_results} faxes in the Archive")

    if num_results:
        while True:
            fid = archive.next_archive_entry()
            if not fid:
                break
            if archive.load_fax(fid):
                print(f"Processing faxid {fid}")
                path = archive.get_tiffpath()
                if path:
                    ocr_data = ocr_faxcontent(path)
                    if ocr_data:
                        archive.set_faxcontent(ocr_data)

    return 0


if __name__ == "__main__":
    sys.exit(main())
