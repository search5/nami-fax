from __future__ import annotations

from typing import Any

from namifax.db.repository import MDBOData

DL_SEPARATOR = ":"

DEFAULT_LANG = {
    "DISTROLIST_ENTER_LISTNAME": "Please enter a list name",
    "DISTROLIST_EXISTS": "A distribution list by that name already exists",
    "DISTROLIST_NOT_CREATED": "Distribution list could not be created",
}


class DistributionList:
    """Service class for managing fax distribution lists (DistroList table)."""

    def __init__(
        self,
        db: Any = None,
        engine: Any = None,
        repo: MDBOData | None = None,
        lang: dict[str, str] | None = None,
    ) -> None:
        self.db = db or engine
        self.lang = lang or DEFAULT_LANG

        if repo is not None:
            self.distrolist = repo
        else:
            self.distrolist = MDBOData("DistroList", db=self.db)

        self.dl_id: int | None = None
        self.listname: str | None = None
        self.listdata: str | None = None
        self.lastmod_date: str | None = None
        self.lastmod_user: int | None = None
        self.error: str | None = None

    def get_dl_id(self) -> int | None:
        return self.dl_id

    def get_listname(self) -> str | None:
        return self.listname

    def get_lastmod(self) -> dict[str, Any]:
        return {"date": self.lastmod_date, "user": self.lastmod_user}

    def get_error(self) -> str | None:
        return self.error

    def set_moduser(self, moduser: int | None) -> None:
        self.lastmod_user = moduser

    def create(self, listname: str | None) -> bool:
        """Create a new distribution list."""
        self.listname = listname

        if not self.listname:
            self.error = self.lang.get("DISTROLIST_ENTER_LISTNAME", "Please enter a list name")
            return False

        if self.distrolist.find({"listname": self.listname}):
            self.error = self.lang.get("DISTROLIST_EXISTS", "A distribution list by that name already exists")
            return False

        payload = {"listname": self.listname, "lastmod_user": self.lastmod_user}
        if self.distrolist.new_entry(payload):
            self.dl_id = self.distrolist.get_id()
            self.error = None
            return True

        self.error = self.lang.get("DISTROLIST_NOT_CREATED", "Distribution list could not be created")
        return False

    def delete_list(self, list_id: int) -> bool:
        """Delete a distribution list by ID."""
        self.distrolist.data.set_id(list_id)
        ok = bool(self.distrolist.delete_entry())
        if ok:
            self.error = None
        return ok

    def get_distrolists(self) -> list[dict[str, Any]]:
        """Return all distribution lists ordered by listname."""
        return self.distrolist.select(columns=["dl_id", "listname"], order_by="listname")

    def load_list(self, list_id: int | None) -> bool:
        """Load distribution list by ID."""
        if not list_id:
            self.error = "DList not selected"
            return False

        if self.distrolist.load(list_id):
            data = self.distrolist.get_info()
            self.dl_id = data.get("dl_id")
            self.listname = data.get("listname")
            self.listdata = data.get("listdata")
            self.lastmod_date = data.get("lastmod_date")
            self.lastmod_user = data.get("lastmod_user")
            self.error = None
            return True

        self.error = f"List {list_id} doesn't exist."
        return False

    def set_listname(self, listname: str) -> bool:
        """Update listname of loaded distribution list."""
        if not self.dl_id:
            self.error = "No list loaded"
            return False

        self.listname = listname
        payload = {"listname": self.listname, "lastmod_user": self.lastmod_user}
        ok = bool(self.distrolist.update_entry(payload))
        if ok:
            self.error = None
        return ok

    def list_entries(self) -> list[str]:
        """Return array of entries in the loaded distribution list."""
        if not self.dl_id:
            self.error = "No list loaded"
            return []

        if not self.listdata:
            return []

        import re
        return [item.strip() for item in re.split(r"[:;]\s*", self.listdata) if item.strip()]

    def add_entries(self, entries: list[str]) -> bool:
        """Add new entries without duplicates to the loaded distribution list."""
        if not self.dl_id:
            self.error = "No list loaded"
            return False

        if not isinstance(entries, list):
            return False

        current = self.list_entries()
        for e in entries:
            if e and e not in current:
                current.append(e)

        self.listdata = DL_SEPARATOR.join(current)
        payload = {"listdata": self.listdata, "lastmod_user": self.lastmod_user}
        ok = bool(self.distrolist.update_entry(payload))
        if ok:
            self.error = None
        return ok

    def remove_entries(self, entries: list[str]) -> bool:
        """Remove entries from the loaded distribution list."""
        if not self.dl_id:
            self.error = "No list loaded"
            return False

        if not isinstance(entries, list):
            return False

        remove_set = set(entries)
        current = [e for e in self.list_entries() if e not in remove_set]

        self.listdata = DL_SEPARATOR.join(current)
        payload = {"listdata": self.listdata, "lastmod_user": self.lastmod_user}
        ok = bool(self.distrolist.update_entry(payload))
        if ok:
            self.error = None
        return ok


# Modern architectural alias
DistributionListService = DistributionList
