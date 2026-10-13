from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from namifax.services.archive_base import clean_faxnum, FaxPDFArchive


class ArchiveOut(FaxPDFArchive):
    """Outbound Fax Domain Service managing sent fax archiving and metadata."""

    def __init__(
        self,
        db: Any = None,
        installdir: str = "",
    ) -> None:
        super().__init__(db=db, installdir=installdir)

    def create(
        self,
        path: str,
        userid: int,
        cid: Optional[int],
        origfaxnum: str,
        pages: int,
    ) -> bool:
        """Create new outbound sent fax record in archive (inbox=0)."""
        rel_path = path
        if self.installdir and path.startswith(self.installdir):
            rel_path = path[len(self.installdir) :]

        cleaned_num = clean_faxnum(origfaxnum)

        entry = {
            "userid": userid,
            "faxpath": rel_path,
            "companyid": cid,
            "archstamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "inbox": 0,
            "origfaxnum": cleaned_num,
            "pages": pages,
        }

        if self.faxarchive.new_entry(entry):
            self.dbdata = entry
            self.dbdata["fid"] = self.faxarchive.get_id()
            self.load_vals(self.dbdata)
            return True

        self.error = "No fid created"
        return False
