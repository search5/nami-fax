from __future__ import annotations

from typing import Any

from namifax.common.validators import is_valid_email
from namifax.db.repository import MDBOData

DEFAULT_LANG = {
    "REGWARN_MAIL": "Please enter a valid e-mail address.",
    "DIDROUTE_NOT_CREATED": "Route could not be created",
    "DIDROUTE_EXISTS": "DID route already exists",
    "DIDROUTE_NO_ROUTES": "No DID routes configured",
    "DIDROUTE_DOESNT_EXIST": "DID route '%s' doesn't exist",
}


class DIDRouting:
    """Service class for managing DID (Direct Inward Dialing) routing rules (DIDRoute table)."""

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
            self.didroute = repo
        else:
            self.didroute = MDBOData("DIDRoute", db=self.db)

        self.didr_id: int | None = None
        self.alias: str | None = None
        self.contact: str | None = None
        self.routecode: str | None = None
        self.faxcatid: int | None = None
        self.printer: str | None = None
        self.error: str | None = None
        self.all_data: dict[str, Any] = {}

        self._queried: bool = False
        self._list_results: list[dict[str, Any]] = []

    def create(
        self,
        route: str | None,
        alias: str | None,
        contact: str | None = None,
        printer: str | None = None,
        faxcatid: int | None = None,
    ) -> bool:
        """Create a new DID routing rule."""
        self.alias = alias
        self.routecode = route
        self.contact = contact
        self.printer = printer
        self.faxcatid = faxcatid

        if self.contact and not is_valid_email(self.contact):
            self.error = self.lang.get("REGWARN_MAIL", "Please enter a valid e-mail address.")
            return False

        if not self.alias or not self.routecode or self.routecode == "<NONE>":
            self.error = self.lang.get("DIDROUTE_NOT_CREATED", "Route could not be created")
            return False

        if self.didroute.find({"routecode": self.routecode}):
            self.error = self.lang.get("DIDROUTE_EXISTS", "DID route already exists")
            return False

        payload = {
            "routecode": self.routecode,
            "alias": self.alias,
            "contact": self.contact,
            "printer": self.printer,
            "faxcatid": self.faxcatid,
        }

        if self.didroute.new_entry(payload):
            self.didr_id = self.didroute.get_id()
            self.error = None
            return True

        self.error = self.lang.get("DIDROUTE_NOT_CREATED", "Route could not be created")
        return False

    def delete_route(self, didr_id: int) -> bool:
        """Delete routing rule by ID."""
        self.didroute.data.set_id(didr_id)
        ok = bool(self.didroute.delete_entry())
        if ok:
            self.error = None
        return ok

    def get_routes(self) -> list[int] | None:
        """Return array of all route IDs configured, prefixed with 0 (legacy convention)."""
        routes = self.didroute.select(columns=["didr_id"], order_by="alias")
        if routes:
            return [0] + [r["didr_id"] for r in routes if "didr_id" in r]

        self.error = self.lang.get("DIDROUTE_NO_ROUTES", "No DID routes configured")
        return None

    def list_all(self) -> list[dict[str, Any]]:
        """Return all DID routes ordered by alias."""
        return self.didroute.select(order_by="alias")

    def reset_list(self) -> None:
        """Reset internal cursor for list traversal."""
        self._queried = False
        self._list_results = []

    def list_routes_step(self) -> tuple[int, str, str] | None:
        """Step-by-step cursor emulation for legacy list_routes(&$didr_id, &$alias, &$routecode)."""
        if not self._queried:
            self._list_results = self.didroute.select(order_by="alias")
            self._queried = True

        if self._list_results:
            data = self._list_results.pop(0)
            return (
                data.get("didr_id", 0),
                data.get("alias", ""),
                data.get("routecode", ""),
            )

        self._queried = False
        self.error = self.lang.get("DIDROUTE_NO_ROUTES", "No DID routes configured")
        return None

    def load_route(self, routecode: str | None) -> bool:
        """Load route by routecode string."""
        if not routecode:
            self.error = "Route code not selected"
            return False

        data = self.didroute.find({"routecode": routecode})
        if data and isinstance(data, dict):
            self.alias = data.get("alias")
            self.routecode = data.get("routecode")
            self.contact = data.get("contact")
            self.printer = data.get("printer")
            self.didr_id = data.get("didr_id")
            self.faxcatid = data.get("faxcatid")
            self.all_data = data
            self.error = None
            return True

        template = self.lang.get("DIDROUTE_DOESNT_EXIST", "DID route '%s' doesn't exist")
        self.error = template % routecode if "%s" in template else f"DID route '{routecode}' doesn't exist"
        return False

    def loadbyid(self, didr_id: int | None) -> bool:
        """Load route by primary key didr_id."""
        if not didr_id:
            self.error = "Route ID not selected"
            return False

        data = self.didroute.find({"didr_id": didr_id})
        if data and isinstance(data, dict):
            self.alias = data.get("alias")
            self.routecode = data.get("routecode")
            self.contact = data.get("contact")
            self.printer = data.get("printer")
            self.didr_id = data.get("didr_id")
            self.faxcatid = data.get("faxcatid")
            self.all_data = data
            self.error = None
            return True

        template = self.lang.get("DIDROUTE_DOESNT_EXIST", "DID route '%s' doesn't exist")
        self.error = template % didr_id if "%s" in template else f"DID route '{didr_id}' doesn't exist"
        return False

    def get_alias(self) -> str | None:
        return self.alias

    def get_contact(self) -> str | None:
        return self.contact

    def get_printer(self) -> str | None:
        return self.printer

    def get_faxcatid(self) -> int | None:
        return self.faxcatid

    def get_didr_id(self) -> int | None:
        return self.didr_id

    def get_route(self) -> str | None:
        return self.routecode

    def get_error(self) -> str | None:
        return self.error

    def set_alias(self, alias: str) -> bool:
        if not self.didr_id:
            self.error = "No entry loaded"
            return False
        self.alias = alias
        self.didroute.data.set_id(self.didr_id)
        self.all_data["alias"] = alias
        ok = bool(self.didroute.update_entry(self.all_data))
        if ok:
            self.error = None
        return ok

    def set_routecode(self, routecode: str) -> bool:
        if not self.didr_id:
            self.error = "No entry loaded"
            return False
        self.routecode = routecode
        self.didroute.data.set_id(self.didr_id)
        self.all_data["routecode"] = routecode
        ok = bool(self.didroute.update_entry(self.all_data))
        if ok:
            self.error = None
        return ok

    def set_contact(self, contact: str) -> bool:
        if not self.didr_id:
            self.error = "No entry loaded"
            return False
        self.contact = contact
        self.didroute.data.set_id(self.didr_id)
        self.all_data["contact"] = contact
        ok = bool(self.didroute.update_entry(self.all_data))
        if ok:
            self.error = None
        return ok

    def set_printer(self, printer: str) -> bool:
        if not self.didr_id:
            self.error = "No entry loaded"
            return False
        self.printer = printer
        self.didroute.data.set_id(self.didr_id)
        self.all_data["printer"] = printer
        ok = bool(self.didroute.update_entry(self.all_data))
        if ok:
            self.error = None
        return ok

    def set_faxcatid(self, faxcatid: int | None) -> bool:
        if not self.didr_id:
            self.error = "No entry loaded"
            return False
        self.faxcatid = faxcatid
        self.didroute.data.set_id(self.didr_id)
        self.all_data["faxcatid"] = faxcatid
        ok = bool(self.didroute.update_entry(self.all_data))
        if ok:
            self.error = None
        return ok


# Modern architectural alias
DIDRoutingService = DIDRouting
