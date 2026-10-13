from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timedelta
from typing import Any

from namifax.services.archive_base import FaxPDFArchive, PREVIMG, PREVIMGSFX, THUMBNAIL, TIFFNAME


class ArchiveIn(FaxPDFArchive):
    """Inbound Fax Domain Service managing inbox storage, rotation, and archiving."""

    def __init__(
        self,
        db: Any = None,
        installdir: str = "",
    ) -> None:
        super().__init__(db=db, installdir=installdir)

    def create(
        self,
        path: str,
        faxnid: int,
        faxnumber: str,
        modem: str,
        pages: int,
        date: str | None = None,
        didr_id: int | None = None,
    ) -> bool:
        """Create new inbound fax in inbox."""
        if not self.create_fax(path, faxnid, faxnumber, pages, date, didr_id):
            return False
        return self.set_modemdev(modem)

    def set_modemdev(self, modemdev: str) -> bool:
        """Assign modem device and set inbox=True."""
        if not modemdev:
            self.error = "Modem missing"
            return False

        self.dbdata["modemdev"] = modemdev
        self.dbdata["inbox"] = 1
        return bool(self.faxarchive.update_entry(self.dbdata))

    def set_archivebox(self, faxid: int) -> bool:
        """Move fax from inbox to archive (inbox=0)."""
        if not faxid or not self.load_fax(faxid):
            self.error = "No faxid to set archivebox"
            return False

        self.dbdata["inbox"] = 0
        if self.faxarchive.update_entry(self.dbdata):
            return True

        self.error = "Invalid faxid"
        return False

    def rotate_fax(self) -> bool:
        """Rotate received fax TIFF images and thumbnails by 180 degrees."""
        if "fid" not in self.dbdata:
            self.error = "No fid loaded"
            return False

        if not self.dbdata.get("inbox"):
            self.error = "Not in inbox"
            return False

        full_dir = self._on_disk(self.dbdata.get("faxpath", ""))
        tiff_file = os.path.join(full_dir, TIFFNAME)
        thumb_file = os.path.join(full_dir, THUMBNAIL)

        # Attempt rotating TIFF using PIL or convert CLI if files exist
        if os.path.exists(tiff_file):
            rotated = False
            try:
                from PIL import Image

                with Image.open(tiff_file) as img:
                    rot = img.rotate(180, expand=True)
                    rot.save(tiff_file)
                    rotated = True
            except Exception:
                pass

            if not rotated and shutil.which("convert"):
                try:
                    subprocess.run(["convert", "-rotate", "180", tiff_file, tiff_file], check=False)
                except Exception:
                    pass

        if os.path.exists(thumb_file):
            try:
                from PIL import Image

                with Image.open(thumb_file) as img:
                    rot = img.rotate(180, expand=True)
                    rot.save(thumb_file)
            except Exception:
                pass

        pages = self.dbdata.get("pages") or 0
        for i in range(pages):
            prev_file = os.path.join(full_dir, f"{PREVIMG}{i}{PREVIMGSFX}")
            if os.path.exists(prev_file):
                try:
                    from PIL import Image

                    with Image.open(prev_file) as img:
                        rot = img.rotate(180, expand=True)
                        rot.save(prev_file)
                except Exception:
                    pass

        return True

    def prune_inbox(self, days: int, should_stop=None) -> int:
        """Archive inbox faxes older than given number of days (``should_stop()`` is asked between faxes)."""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
        archived = 0
        for fid in self._fids_older_than(cutoff, inbox=1):
            if should_stop and should_stop():
                break
            if fid and self.set_archivebox(fid):
                archived += 1
        return archived
