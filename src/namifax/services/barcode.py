from __future__ import annotations

from typing import Any

from namifax.common.validators import is_valid_email
from namifax.db.repository import MDBOData

DEFAULT_LANG = {
    "REGWARN_MAIL": "Please enter a valid e-mail address.",
    "BARCODEROUTE_NOT_CREATED": "Route could not be created",
    "BARCODEROUTE_EXISTS": "Barcode route already exists",
    "BARCODEROUTE_NO_ROUTES": "No barcode routes configured",
    "BARCODEROUTE_DOESNT_EXIST": "Barcode route '%s' doesn't exist",
}


class BarcodeRouting:
    """Service class for managing barcode-based routing rules (BarcodeRoute table)."""

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
            self.barcoderoute = repo
        else:
            self.barcoderoute = MDBOData("BarcodeRoute", db=self.db)

        self.barcode_id: int | None = None
        self.alias: str | None = None
        self.contact: str | None = None
        self.barcode: str | None = None
        self.faxcatid: int | None = None
        self.printer: str | None = None
        self.error: str | None = None

        self._queried: bool = False
        self._list_results: list[dict[str, Any]] = []

    def create(
        self,
        barcode: str | None,
        alias: str | None,
        contact: str | None = None,
        printer: str | None = None,
        faxcatid: int | None = None,
    ) -> bool:
        """Create a new barcode routing rule."""
        self.alias = alias
        self.barcode = barcode
        self.contact = contact
        self.printer = printer
        self.faxcatid = faxcatid

        if self.contact and not is_valid_email(self.contact):
            self.error = self.lang.get("REGWARN_MAIL", "Please enter a valid e-mail address.")
            return False

        if not self.alias or not self.barcode or self.barcode == "<NONE>":
            self.error = self.lang.get("BARCODEROUTE_NOT_CREATED", "Route could not be created")
            return False

        if self.barcoderoute.find({"barcode": self.barcode}):
            self.error = self.lang.get("BARCODEROUTE_EXISTS", "Barcode route already exists")
            return False

        payload = {
            "barcode": self.barcode,
            "alias": self.alias,
            "contact": self.contact,
            "printer": self.printer,
            "faxcatid": self.faxcatid,
        }

        if self.barcoderoute.new_entry(payload):
            self.barcode_id = self.barcoderoute.get_id()
            self.error = None
            return True

        self.error = self.lang.get("BARCODEROUTE_NOT_CREATED", "Route could not be created")
        return False

    def delete_route(self, barcode_id: int) -> bool:
        """Delete routing rule by ID."""
        self.barcoderoute.data.set_id(barcode_id)
        ok = bool(self.barcoderoute.delete_entry())
        if ok:
            self.error = None
        return ok

    def get_routes(self) -> list[int] | None:
        """Return array of all route IDs configured, prefixed with 0 (legacy convention)."""
        routes = self.barcoderoute.select(columns=["barcode_id"], order_by="alias")
        if routes:
            return [0] + [r["barcode_id"] for r in routes if "barcode_id" in r]

        self.error = self.lang.get("BARCODEROUTE_NO_ROUTES", "No barcode routes configured")
        return None

    def list_all(self) -> list[dict[str, Any]]:
        """Return all barcode routes ordered by alias."""
        return self.barcoderoute.select(order_by="alias")

    def reset_list(self) -> None:
        """Reset internal cursor for list traversal."""
        self._queried = False
        self._list_results = []

    def list_routes_step(self) -> tuple[int, str, str] | None:
        """Step-by-step cursor emulation for legacy list_routes(&$barcode_id, &$alias, &$barcode)."""
        if not self._queried:
            self._list_results = self.barcoderoute.select(order_by="alias")
            self._queried = True

        if self._list_results:
            data = self._list_results.pop(0)
            return (
                data.get("barcode_id", 0),
                data.get("alias", ""),
                data.get("barcode", ""),
            )

        self._queried = False
        self.error = self.lang.get("BARCODEROUTE_NO_ROUTES", "No barcode routes configured")
        return None

    def load_route(self, barcode: str | None) -> bool:
        """Load route by barcode string."""
        if not barcode:
            self.error = "Barcode not selected"
            return False

        data = self.barcoderoute.find({"barcode": barcode})
        if data and isinstance(data, dict):
            self.alias = data.get("alias")
            self.barcode = data.get("barcode")
            self.contact = data.get("contact")
            self.printer = data.get("printer")
            self.barcode_id = data.get("barcode_id")
            self.faxcatid = data.get("faxcatid")
            self.error = None
            return True

        template = self.lang.get("BARCODEROUTE_DOESNT_EXIST", "Barcode route '%s' doesn't exist")
        self.error = template % barcode if "%s" in template else f"Barcode route '{barcode}' doesn't exist"
        return False

    def loadbyid(self, barcode_id: int | None) -> bool:
        """Load route by primary key barcode_id."""
        if not barcode_id:
            self.error = "Barcode ID not selected"
            return False

        data = self.barcoderoute.find({"barcode_id": barcode_id})

        if data and isinstance(data, dict):
            self.alias = data.get("alias")
            self.barcode = data.get("barcode")
            self.contact = data.get("contact")
            self.printer = data.get("printer")
            self.barcode_id = data.get("barcode_id")
            self.faxcatid = data.get("faxcatid")
            self.error = None
            return True

        template = self.lang.get("BARCODEROUTE_DOESNT_EXIST", "Barcode route '%s' doesn't exist")
        self.error = template % barcode_id if "%s" in template else f"Barcode route '{barcode_id}' doesn't exist"
        return False

    def get_alias(self) -> str | None:
        return self.alias

    def get_contact(self) -> str | None:
        return self.contact

    def get_printer(self) -> str | None:
        return self.printer

    def get_faxcatid(self) -> int | None:
        return self.faxcatid

    def get_barcode_id(self) -> int | None:
        return self.barcode_id

    def get_barcode(self) -> str | None:
        return self.barcode

    def get_error(self) -> str | None:
        return self.error

    def set_alias(self, alias: str) -> bool:
        if not self.barcode_id:
            self.error = "No entry loaded"
            return False
        self.alias = alias
        self.barcoderoute.data.set_id(self.barcode_id)
        ok = bool(self.barcoderoute.update_entry({"alias": alias}))
        if ok:
            self.error = None
        return ok

    def set_barcode(self, barcode: str) -> bool:
        if not self.barcode_id:
            self.error = "No entry loaded"
            return False
        self.barcode = barcode
        self.barcoderoute.data.set_id(self.barcode_id)
        ok = bool(self.barcoderoute.update_entry({"barcode": barcode}))
        if ok:
            self.error = None
        return ok

    def set_contact(self, contact: str) -> bool:
        if not self.barcode_id:
            self.error = "No entry loaded"
            return False
        self.contact = contact
        self.barcoderoute.data.set_id(self.barcode_id)
        ok = bool(self.barcoderoute.update_entry({"contact": contact}))
        if ok:
            self.error = None
        return ok

    def set_printer(self, printer: str) -> bool:
        if not self.barcode_id:
            self.error = "No entry loaded"
            return False
        self.printer = printer
        self.barcoderoute.data.set_id(self.barcode_id)
        ok = bool(self.barcoderoute.update_entry({"printer": printer}))
        if ok:
            self.error = None
        return ok

    def set_faxcatid(self, faxcatid: int | None) -> bool:
        if not self.barcode_id:
            self.error = "No entry loaded"
            return False
        self.faxcatid = faxcatid
        self.barcoderoute.data.set_id(self.barcode_id)
        ok = bool(self.barcoderoute.update_entry({"faxcatid": faxcatid}))
        if ok:
            self.error = None
        return ok


# Modern architectural alias
BarcodeRoutingService = BarcodeRouting
