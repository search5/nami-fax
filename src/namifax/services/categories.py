from __future__ import annotations

from typing import Any

from namifax.db.repository import MDBOData

DEFAULT_LANG = {
    "FAXCAT_ALREADY_EXISTS": "Category '%s' already exists",
    "FAXCAT_NOT_CREATED": "Category '%s' could not be created",
}


class FaxPDFCategory:
    """Service class for managing fax categories (FaxCategory table).

    ``db`` is a SQLAlchemy ``Session`` (portable across SQLite, MySQL, MariaDB and PostgreSQL) or the
    legacy ``Any`` (still used by the FFI bridge).
    """

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
            self.faxcategory = repo
        else:
            self.faxcategory = MDBOData("FaxCategory", db=self.db)

        self.error: str | None = None
        self._queried: bool = False
        self._list_results: list[dict[str, Any]] = []

    def create(self, name: str) -> bool:
        """Create a new fax category."""
        if not name:
            template = self.lang.get("FAXCAT_NOT_CREATED", "Category '%s' could not be created")
            self.error = template % "" if "%s" in template else "Category could not be created"
            return False

        # Check if category already exists
        if self.faxcategory.find({"name": name}):
            template = self.lang.get("FAXCAT_ALREADY_EXISTS", "Category '%s' already exists")
            self.error = template % name if "%s" in template else f"Category '{name}' already exists"
            return False

        # Add category to DB
        if self.faxcategory.new_entry({"name": name}):
            self.error = None
            return True

        template = self.lang.get("FAXCAT_NOT_CREATED", "Category '%s' could not be created")
        self.error = template % name if "%s" in template else f"Category '{name}' could not be created"
        return False

    def set_name(self, name: str, catid: int) -> bool:
        """Update category name by catid."""
        if not name or not catid:
            self.error = "No name or catid to set"
            return False

        self.faxcategory.data.set_id(catid)
        ok = bool(self.faxcategory.update_entry({"name": name}))
        if ok:
            self.error = None
        return ok

    def reset_list(self) -> None:
        """Reset internal cursor for list traversal."""
        self._queried = False
        self._list_results = []

    def get_list_step(self) -> tuple[int, str] | None:
        """Step-by-step cursor emulation for legacy get_list(&$catid, &$name)."""
        if not self._queried:
            self._list_results = self.faxcategory.select(order_by="name")
            self._queried = True

        if self._list_results:
            data = self._list_results.pop(0)
            return data.get("catid", 0), data.get("name", "")

        self._queried = False
        return None

    def get_categories(self) -> list[dict[str, Any]] | None:
        """Return all categories ordered by name."""
        return self.faxcategory.select(order_by="name")

    def get_error(self) -> str | None:
        """Return the last error message."""
        return self.error

    def get_name(self, catid: int | None) -> str | None:
        """Get category name by catid."""
        if not catid:
            self.error = "No catid sent"
            return None

        results = self.faxcategory.find({"catid": catid})
        if results and isinstance(results, dict):
            self.error = None
            return results.get("name")
        return None

    def delete_category(self, catid: int | None) -> bool:
        """Delete category by catid."""
        if not catid:
            self.error = "No catid sent"
            return False

        self.faxcategory.data.set_id(catid)
        ok = bool(self.faxcategory.delete_entry())
        if ok:
            self.error = None
        return ok


# Alias for modern architecture
CategoryService = FaxPDFCategory
