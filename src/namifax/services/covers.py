from __future__ import annotations

from typing import Any

from namifax.db.repository import MDBOData

DEFAULT_LANG = {
    "COVER_NOT_CREATED": "Cover page could not be created",
    "COVER_EXISTS": "Cover page already exists",
    "COVER_DOESNT_EXIST": "Cover page '%s' doesn't exist",
    "NO_COVERS_CONFIGURED": "No cover pages configured",
}


class Covers:
    """Service class for managing AvantFAX cover pages (CoverPages table).

    ``db`` is a SQLAlchemy ``Session`` (portable across databases) or the legacy ``Any``.
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
            self.covers = repo
        else:
            self.covers = MDBOData("CoverPages", db=self.db)

        self.cover_id: int | None = None
        self.title: str | None = None
        self.file: str | None = None
        self.all_data: dict[str, Any] = {}
        self.error: str | None = None

        self._queried: bool = False
        self._list_results: list[dict[str, Any]] = []

    def create(self, title: str | None, file: str | None) -> bool:
        """Create a new cover page record."""
        self.title = title
        self.file = file

        if not self.title or not self.file:
            self.error = self.lang.get("COVER_NOT_CREATED", "Cover page could not be created")
            return False

        # Check if cover already exists with same file
        if self.covers.find({"file": self.file}):
            self.error = self.lang.get("COVER_EXISTS", "Cover page already exists")
            return False

        # Add cover to DB
        if self.covers.new_entry({"file": self.file, "title": self.title}):
            self.cover_id = self.covers.get_id()
            return True

        self.error = self.lang.get("COVER_NOT_CREATED", "Cover page could not be created")
        return False

    def delete_cover(self, cover_id: int) -> bool:
        """Delete cover page by its ID."""
        self.covers.data.set_id(cover_id)
        return self.covers.delete_entry()

    def get_covers(self) -> list[str] | None:
        """Return list of all configured cover filenames ordered by filename."""
        covers = self.covers.select(columns=["file"], order_by="file")
        if covers:
            return [c["file"] for c in covers if "file" in c]

        self.error = self.lang.get("NO_COVERS_CONFIGURED", "No cover pages configured")
        return None

    def list_all(self) -> list[dict[str, Any]]:
        """Modern Python helper: returns all cover pages ordered by title."""
        return self.covers.select(order_by="title")

    def reset_list(self) -> None:
        """Reset the internal cursor for list_covers_step."""
        self._queried = False
        self._list_results = []

    def list_covers_step(self) -> tuple[str, str] | None:
        """Emulates legacy stateful list_covers(&$title, &$file) step-by-step."""
        if not self._queried:
            self._list_results = self.covers.select(order_by="title")
            self._queried = True

        if self._list_results:
            data = self._list_results.pop(0)
            return data.get("title", ""), data.get("file", "")

        self._queried = False
        self.error = self.lang.get("NO_COVERS_CONFIGURED", "No cover pages configured")
        return None

    def load_cover(self, file: str | None) -> bool:
        """Load cover record by filename."""
        if not file:
            self.error = "Cover page not selected"
            return False

        data = self.covers.find({"file": file})
        if data:
            self.cover_id = data.get("cover_id")
            self.title = data.get("title")
            self.file = data.get("file")
            self.all_data = data
            return True

        template = self.lang.get("COVER_DOESNT_EXIST", "Cover page '%s' doesn't exist")
        self.error = template % file if "%s" in template else f"Cover page '{file}' doesn't exist"
        return False

    def load_by_id(self, cover_id: int) -> bool:
        """Load cover record by primary key cover_id."""
        data = self.covers.find({"cover_id": cover_id})
        if data:
            self.cover_id = data.get("cover_id")
            self.title = data.get("title")
            self.file = data.get("file")
            self.all_data = data
            return True

        self.error = f"Cover page with ID {cover_id} doesn't exist"
        return False

    def get_cover_id(self) -> int | None:
        return self.cover_id

    def get_title(self) -> str | None:
        return self.title

    def get_file(self) -> str | None:
        return self.file

    def set_title(self, title: str) -> bool:
        """Update title of the currently loaded cover."""
        if not self.cover_id:
            self.error = "No cover page loaded"
            return False

        self.title = title
        self.covers.data.set_id(self.cover_id)
        self.all_data["title"] = self.title
        return self.covers.update_entry(self.all_data)

    def set_file(self, file: str) -> bool:
        """Update filename of the currently loaded cover."""
        if not self.cover_id:
            self.error = "No cover page loaded"
            return False

        self.file = file
        self.covers.data.set_id(self.cover_id)
        self.all_data["file"] = self.file
        return self.covers.update_entry(self.all_data)


CoverService = Covers
