import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from namifax.db.repository import MDBOData
from namifax.services import archive_orm


PDFNAME = "fax.pdf"
THUMBNAIL = "thumb.png"
TIFFNAME = "fax.tif"
PREVIMG = "page"
PREVIMGSFX = ".png"
DEFAULT_ARCHIVE_DATE_FORMAT = "%Y-%m-%d %H:%M"


def clean_faxnum(num: Optional[str]) -> str:
    if not num:
        return ""
    return re.sub(r"[^\d+]", "", str(num))


class FaxPDFArchive:
    """Core Archive Domain Service managing fax metadata, inbox/archive search, permissions, and file pruning."""

    def __init__(
        self,
        db: Any = None,
        installdir: str = "",
        date_format: str = DEFAULT_ARCHIVE_DATE_FORMAT,
    ) -> None:
        self.db = db
        self._route_filters: List[Any] = []
        # Faxes of an installation made by the original AvantFAX are stored relative to its web root (``/faxes/2012/...``);
        # AVANTFAX_INSTALLDIR says where that is. Without it a stored path is used as it is.
        self.installdir = (installdir or os.environ.get("AVANTFAX_INSTALLDIR", "")).rstrip("/")
        self.date_format = date_format

        self.faxarchive = MDBOData("FaxArchive", db=self.db)
        self.dbdata: Dict[str, Any] = {}

        self.thumbnail: Optional[str] = None
        self.tiffpath: Optional[str] = None
        self.pdfpath: Optional[str] = None
        self.faximages: List[str] = []
        self.m_archstamp: Optional[str] = None
        self.m_lastmoddate: Optional[str] = None
        self.m_lastoperation: Optional[str] = None
        self.error: Optional[str] = None

        self.archive_results: Optional[List[Dict[str, Any]]] = None

    def get_error(self) -> Optional[str]:
        return self.error

    def get_faxcatid(self) -> Optional[int]:
        if "fid" not in self.dbdata:
            self.error = "No fid loaded"
            return None
        return self.dbdata.get("faxcatid")

    def user_has_rights(
        self,
        userid: int,
        modems: Optional[List[Any]] = None,
        routes: Optional[List[Any]] = None,
        faxcat: Optional[List[Any]] = None,
    ) -> bool:
        if "fid" not in self.dbdata:
            self.error = "No fid loaded"
            return False

        modems = self.check_empty_array(modems or [])
        routes = self.check_empty_array(routes or [])
        faxcat = self.check_empty_array(faxcat or [])

        # User matches
        if userid and self.dbdata.get("userid") == userid:
            return True

        # Modem matches
        if modems and self.dbdata.get("modemdev") in modems:
            return True

        # Fax category matches
        if faxcat and self.dbdata.get("faxcatid") in faxcat:
            return True

        # Route matches
        if routes:
            didr_id = self.dbdata.get("didr_id")
            # Handle int and str representations
            if didr_id in routes or str(didr_id) in [str(r) for r in routes]:
                return True

        return False

    @staticmethod
    def check_empty_array(a: List[Any]) -> List[Any]:
        if a and (a[0] is None or a[0] == ""):
            return a[1:]
        return a

    def viewable_devices(
        self,
        devices: Optional[List[Any]] = None,
        faxcats: Optional[List[Any]] = None,
        enable_did_routing: bool = False,
    ) -> None:
        """Remember which inbox faxes the user may see (their modems/DID routes and fax categories)."""
        self._route_filters = archive_orm.inbox_filters(devices, faxcats, enable_did_routing)

    def get_num_faxes(
        self,
        devices: Optional[List[Any]] = None,
        faxcats: Optional[List[Any]] = None,
        enable_did_routing: bool = False,
    ) -> int:
        self.viewable_devices(devices, faxcats, enable_did_routing)
        return archive_orm.count_inbox(self.db, self._route_filters)

    def get_fid_prev(self) -> Optional[int]:
        if "fid" not in self.dbdata:
            self.error = "No fid loaded"
            return None

        results = self._inbox_fids()
        fid = None

        if isinstance(results, list):
            for info in results:
                if info["fid"] == self.dbdata["fid"]:
                    return fid
                else:
                    fid = info["fid"]
        return None

    def get_fid_next(self) -> Optional[int]:
        if "fid" not in self.dbdata:
            self.error = "No fid loaded"
            return None

        results = self._inbox_fids()
        is_next = False

        if isinstance(results, list):
            for info in results:
                if is_next:
                    return info["fid"]
                if info["fid"] == self.dbdata["fid"]:
                    is_next = True
        return None

    def _inbox_fids(self) -> List[Dict[str, Any]]:
        """Visible inbox fids, newest first, as ``[{"fid": n}]``."""
        return [{"fid": f} for f in archive_orm.inbox_fids(self.db, self._route_filters)]

    def search_archive(self, criteria: Dict[str, Any]) -> int:
        """Search the archive; the page of ids is read with ``next_archive_entry``. Returns the number of matches."""
        numrows, self.archive_results = archive_orm.search(self.db, criteria)
        return numrows

    def next_archive_entry(self) -> Optional[int]:
        if isinstance(self.archive_results, list) and self.archive_results:
            row = self.archive_results.pop(0)
            return row.get("fid")
        self.archive_results = None
        return None

    def list_inbox(
        self,
        devices: Optional[List[Any]] = None,
        index: int = 0,
        limit: int = 25,
        faxcats: Optional[List[Any]] = None,
        enable_did_routing: bool = False,
        order_by_modem: bool = False,
    ) -> List[Dict[str, Any]]:
        self.viewable_devices(devices, faxcats, enable_did_routing)
        if index < 0:
            index = 0
        offset = index * limit

        rows = archive_orm.list_inbox(self.db, self._route_filters, offset, limit, order_by_modem)
        if not isinstance(rows, list):
            return []

        for r in rows:
            self._format_row_dates(r)
        return rows

    def load_fax(self, faxid: int) -> bool:
        if not faxid:
            self.error = "No faxid to load"
            return False

        row = self.faxarchive.find({"fid": faxid}, reduce_single=True)
        if isinstance(row, dict):
            self.load_vals(row)
            return True
        elif isinstance(row, list) and row:
            self.load_vals(row[0])
            return True

        self.error = f"load_fax error: {faxid} didn't load"
        return False

    def set_category(self, catid: Optional[int], userid: int = 0) -> bool:
        if "fid" not in self.dbdata:
            self.error = "No fid loaded"
            return False

        self.dbdata["faxcatid"] = catid
        self.dbdata["lastmoduser"] = userid
        return bool(self.faxarchive.update_entry(self.dbdata))

    def remove_category(self, catid: int) -> bool:
        if not catid:
            self.error = "No valid catid sent"
            return False

        self.faxarchive.update_where({"faxcatid": catid}, {"faxcatid": None})
        return True

    def set_note(self, description: str, category: Optional[int], userid: int) -> bool:
        if "fid" not in self.dbdata:
            self.error = "No fid loaded"
            return False

        self.dbdata["faxcatid"] = category
        self.dbdata["description"] = description
        self.dbdata["lastmoduser"] = userid
        self.dbdata["lastmoddate"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.faxarchive.update_entry(self.dbdata)
        return True

    def set_faxcontent(self, faxcontent: str) -> bool:
        if "fid" not in self.dbdata:
            self.error = "No fid loaded"
            return False

        self.dbdata["faxcontent"] = faxcontent
        self.faxarchive.update_entry(self.dbdata)
        return True

    def delete_fax(self, fid: Optional[int] = None) -> bool:
        if fid:
            if not self.load_fax(fid):
                self.error = "Invalid fid"
                return False
        elif "fid" not in self.dbdata:
            self.error = "No fid loaded"
            return False

        # Delete database entry
        self.faxarchive.delete_entry({"fid": self.dbdata["fid"]})

        # Remove preview images
        faxpath = self.dbdata.get("faxpath", "")
        pages = self.dbdata.get("pages") or 0
        if self.dbdata.get("inbox"):
            for i in range(pages):
                img_path = os.path.join(self._on_disk(faxpath), f"{PREVIMG}{i}{PREVIMGSFX}")
                if os.path.exists(img_path):
                    try:
                        os.remove(img_path)
                    except OSError:
                        pass

        # Remove thumbnail, tiff, pdf
        for fpath in [self.thumbnail, self.tiffpath, self.pdfpath]:
            if fpath:
                full_p = fpath
                if os.path.exists(full_p):
                    try:
                        os.remove(full_p)
                    except OSError:
                        pass

        # Remove directory if empty
        if faxpath:
            full_dir = self._on_disk(faxpath)
            if os.path.exists(full_dir):
                try:
                    os.rmdir(full_dir)
                except OSError:
                    pass

        return True

    def _on_disk(self, path: str) -> str:
        """The file system location of a stored path.

        With an install directory the stored path is relative to it. Without one (faxrcvd stores the
        absolute archive path) it is used as it is; joining it onto an empty directory turned
        ``/var/spool/...`` into the relative ``var/spool/...``, so deleting a fax never removed its files.
        """
        return os.path.join(self.installdir, path.lstrip("/")) if self.installdir else path

    def prune_archive(self, days: int) -> int:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
        count = 0
        for fid in self._fids_older_than(cutoff):
            if fid:
                self.delete_fax(fid)
                count += 1
        return count

    def _fids_older_than(self, cutoff: str, inbox: Optional[int] = None) -> List[int]:
        return archive_orm.fids_older_than(self.db, cutoff, inbox)

    def set_faxnumid(self, id: int) -> bool:
        if "fid" not in self.dbdata:
            self.error = "No fid loaded"
            return False

        self.dbdata["faxnumid"] = id
        if not self.faxarchive.update_entry(self.dbdata):
            self.error = "faxnumid not updated"
            return False
        return True

    def set_companyid(self, id: int) -> bool:
        if "fid" not in self.dbdata:
            self.error = "No fid loaded"
            return False

        self.dbdata["companyid"] = id
        if not self.faxarchive.update_entry(self.dbdata):
            self.error = "companyid not updated"
            return False
        return True

    def reassign(self, oldcid: int, newcid: int) -> bool:
        if not newcid or not oldcid:
            return False

        self.faxarchive.update_where({"companyid": oldcid}, {"companyid": newcid})
        return True

    def create_fax(
        self,
        path: str,
        faxnid: int,
        faxnumber: str,
        pages: int,
        date: Optional[str] = None,
        didr_id: Optional[int] = None,
    ) -> bool:
        # Normalize relative path from installdir
        rel_path = path
        if self.installdir and path.startswith(self.installdir):
            rel_path = path[len(self.installdir) :]

        self.dbdata = {
            "faxpath": rel_path,
            "faxnumid": faxnid,
            "origfaxnum": clean_faxnum(faxnumber),
            "pages": pages,
            "didr_id": didr_id,
            "archstamp": date or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        if self.faxarchive.new_entry(self.dbdata):
            self.dbdata["fid"] = self.faxarchive.get_id()
            self.load_vals(self.dbdata)
            return True

        self.error = "No id created"
        return False

    def load_vals(self, data: Dict[str, Any]) -> None:
        raw = dict(data)
        self._format_row_dates(raw)
        self.m_archstamp = raw.pop("m_archstamp", None)
        self.m_lastmoddate = raw.pop("m_lastmoddate", None)
        self.m_lastoperation = raw.pop("m_lastoperation", None)

        self.dbdata = raw
        faxpath = self.dbdata.get("faxpath") or ""
        folder = self._on_disk(faxpath) if faxpath else ""          # where the files really are

        self.pdfpath = os.path.join(folder, PDFNAME)
        self.thumbnail = os.path.join(folder, THUMBNAIL)
        self.tiffpath = os.path.join(folder, TIFFNAME)

        self.faximages = []
        pages = self.dbdata.get("pages") or 0
        for i in range(pages):
            self.faximages.append(os.path.join(folder, f"{PREVIMG}{i}{PREVIMGSFX}"))

    def _format_row_dates(self, row: Dict[str, Any]) -> None:
        for col in ["archstamp", "lastmoddate", "lastoperation"]:
            val = row.get(col)
            formatted = None
            if val:
                val_str = str(val)
                try:
                    dt = datetime.fromisoformat(val_str)
                    formatted = dt.strftime(self.date_format)
                except ValueError:
                    formatted = val_str[:16]
            row[f"m_{col}"] = formatted

    # Getters
    def get_fid(self) -> Optional[int]:
        return self.dbdata.get("fid")

    def get_userid(self) -> Optional[int]:
        return self.dbdata.get("userid")

    def get_description(self) -> Optional[str]:
        return self.dbdata.get("description")

    def get_lastmoduser(self) -> Optional[int]:
        return self.dbdata.get("lastmoduser")

    def get_faxnumid(self) -> Optional[int]:
        return self.dbdata.get("faxnumid")

    def get_origfaxnum(self) -> Optional[str]:
        return self.dbdata.get("origfaxnum")

    def get_pages(self) -> Optional[int]:
        return self.dbdata.get("pages")

    def get_inbox(self) -> Optional[int]:
        return self.dbdata.get("inbox")

    def get_companyid(self) -> Optional[int]:
        return self.dbdata.get("companyid")

    def get_didr_id(self) -> Optional[int]:
        return self.dbdata.get("didr_id")

    def get_modemdev(self) -> Optional[str]:
        return self.dbdata.get("modemdev")

    def get_tiffpath(self) -> Optional[str]:
        return self.tiffpath

    def get_pdfpath(self) -> Optional[str]:
        return self.pdfpath

    def get_thumbnail(self) -> Optional[str]:
        return self.thumbnail

    def get_faximages(self) -> List[str]:
        return self.faximages

    def get_archstamp(self) -> Optional[str]:
        return self.m_archstamp

    def get_lastmoddate(self) -> Optional[str]:
        return self.m_lastmoddate
