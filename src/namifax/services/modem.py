from __future__ import annotations

import re
import subprocess
from typing import Any

from namifax.db.repository import MDBOData

DEFAULT_LANG = {
    "MODEM_NOT_CREATED": "Modem could not be created",
    "MODEM_EXISTS": "Modem already exists",
    "NO_MODEMS_CONFIGURED": "No modems configured",
    "MODEM_DOESNT_EXIST": "Modem '%s' doesn't exist",
    "FAXFREE": "Running and idle",
    "FAXSEND": "Sending fax",
    "FAXRECV": "Receiving facsimile",
    "FAXRECVFROM": "Receiving from",
    "PLSWAIT": "Please wait",
}


def parse_faxstat_output(raw_output: str, lang: dict[str, str] | None = None) -> dict[str, dict[str, Any]]:
    """Parse raw output of HylaFAX faxstat command into status map per modem device."""
    lmap = lang or DEFAULT_LANG
    result: dict[str, dict[str, Any]] = {}

    for line in raw_output.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue

        # Look for pattern like: Modem ttyS0 (+1.234): Running and idle
        match = re.search(r"\bModem\s+([a-zA-Z0-9_-]+)", line)
        if not match:
            # Fallback search for device token
            match = re.search(r"\b(tty[a-zA-Z0-9_-]+)\b", line)

        if match:
            device_name = match.group(1)
            status_text = line.split(":", 1)[1].strip()

            prefix = status_text[:2]
            if prefix == "Ru":
                code = {"class": "modem-free", "status": lmap.get("FAXFREE", "Running and idle")}
            elif prefix == "Se":
                job_id = status_text.replace("Sending job ", "").strip()
                code = {
                    "class": "modem-send",
                    "status": f"{lmap.get('FAXSEND', 'Sending fax')} {{JID: {job_id}}}",
                }
            elif prefix == "Re":
                recv_from = re.sub(r"Receiving\s*(\[\d+\])?\s*from\s*", "", status_text)
                recv_from = recv_from.replace("Receiving facsimile", "").strip().strip('"')
                if recv_from:
                    code = {
                        "class": "modem-recv",
                        "status": f"{lmap.get('FAXRECVFROM', 'Receiving from')} {recv_from}",
                    }
                else:
                    code = {"class": "modem-recv", "status": lmap.get("FAXRECV", "Receiving facsimile")}
            else:
                code = {"class": "modem-wait", "status": lmap.get("PLSWAIT", "Please wait")}

            result[device_name] = code

    return result


class FaxModem:
    """Service class for managing modem configurations (Modems table) and device status."""

    def __init__(
        self,
        db: Any = None,
        engine: Any = None,
        repo: MDBOData | None = None,
        faxstat_cmd: str = "faxstat",
        lang: dict[str, str] | None = None,
    ) -> None:
        self.db = db or engine
        self.lang = lang or DEFAULT_LANG
        self.faxstat_cmd = faxstat_cmd

        if repo is not None:
            self.modems = repo
        else:
            self.modems = MDBOData("Modems", db=self.db)

        self.devid: int | None = None
        self.alias: str | None = None
        self.device: str | None = None
        self.printer: str | None = None
        self.faxcatid: int | None = None
        self.contact: str | None = None
        self.error: str | None = None
        self.all_data: dict[str, Any] = {}
        self.status: dict[str, dict[str, Any]] = {}

        self._queried: bool = False
        self._list_results: list[dict[str, Any]] = []

    def create(
        self,
        device: str | None,
        alias: str | None,
        contact: str | None = None,
        printer: str | None = None,
        faxcatid: int | None = None,
    ) -> bool:
        """Create a new modem record."""
        self.alias = alias
        self.device = device
        self.contact = contact
        self.printer = printer
        self.faxcatid = faxcatid

        if not self.alias or not self.device:
            self.error = self.lang.get("MODEM_NOT_CREATED", "Modem could not be created")
            return False

        if self.modems.find({"device": self.device}):
            self.error = self.lang.get("MODEM_EXISTS", "Modem already exists")
            return False

        payload = {
            "device": self.device,
            "alias": self.alias,
            "contact": self.contact,
            "printer": self.printer,
            "faxcatid": self.faxcatid,
        }

        if self.modems.new_entry(payload):
            self.devid = self.modems.get_id()
            self.error = None
            return True

        self.error = self.lang.get("MODEM_NOT_CREATED", "Modem could not be created")
        return False

    def delete_device(self, devid_or_device: int | str) -> bool:
        """Delete modem by devid or device name."""
        if isinstance(devid_or_device, int) or (isinstance(devid_or_device, str) and devid_or_device.isdecimal()):
            self.modems.data.set_id(int(devid_or_device))
            ok = bool(self.modems.delete_entry())
            if ok:
                self.error = None
            return ok

        # Lookup by device name
        rec = self.modems.find({"device": str(devid_or_device)})
        if rec and isinstance(rec, dict) and "devid" in rec:
            self.modems.data.set_id(rec["devid"])
            ok = bool(self.modems.delete_entry())
            if ok:
                self.error = None
            return ok
        return False

    def get_modems(self) -> list[str] | None:
        """Return list of all configured modem device names ordered by alias."""
        modems = self.modems.select(columns=["device"], order_by="alias")
        if modems:
            return [m["device"] for m in modems if "device" in m]

        self.error = self.lang.get("NO_MODEMS_CONFIGURED", "No modems configured")
        return None

    def list_all(self) -> list[dict[str, Any]]:
        """Return all modem records ordered by device."""
        return self.modems.select(order_by="device")

    def reset_list(self) -> None:
        """Reset internal cursor for list traversal."""
        self._queried = False
        self._list_results = []

    def list_modems_step(self) -> tuple[int, str, str] | None:
        """Step-by-step cursor emulation for legacy list_modems(&$devid, &$alias, &$device)."""
        if not self._queried:
            self._list_results = self.modems.select(order_by="device")
            self._queried = True

        if self._list_results:
            data = self._list_results.pop(0)
            return (
                data.get("devid", 0),
                data.get("alias", ""),
                data.get("device", ""),
            )

        self._queried = False
        self.error = self.lang.get("NO_MODEMS_CONFIGURED", "No modems configured")
        return None

    def load_device(self, device: str | None) -> bool:
        """Load modem record by device name."""
        if not device:
            self.error = "Modem not selected"
            return False

        data = self.modems.find({"device": device})
        if data and isinstance(data, dict):
            self.alias = data.get("alias")
            self.device = data.get("device")
            self.contact = data.get("contact")
            self.devid = data.get("devid")
            self.printer = data.get("printer")
            self.faxcatid = data.get("faxcatid")
            self.all_data = data
            self.error = None
            return True

        template = self.lang.get("MODEM_DOESNT_EXIST", "Modem '%s' doesn't exist")
        self.error = template % device if "%s" in template else f"Modem '{device}' doesn't exist"
        return False

    def loadbyid(self, devid: int | None) -> bool:
        """Load modem record by primary key devid."""
        if not devid:
            self.error = "Modem not selected"
            return False

        data = self.modems.find({"devid": devid})
        if data and isinstance(data, dict):
            self.alias = data.get("alias")
            self.device = data.get("device")
            self.contact = data.get("contact")
            self.devid = data.get("devid")
            self.printer = data.get("printer")
            self.faxcatid = data.get("faxcatid")
            self.all_data = data
            self.error = None
            return True

        template = self.lang.get("MODEM_DOESNT_EXIST", "Modem '%s' doesn't exist")
        self.error = template % devid if "%s" in template else f"Modem '{devid}' doesn't exist"
        return False

    def get_status(self, raw_output: str | None = None) -> dict[str, Any]:
        """Return runtime status for the loaded modem device."""
        if raw_output is not None:
            self.status = parse_faxstat_output(raw_output, self.lang)
        elif not self.status:
            try:
                proc = subprocess.run(
                    [self.faxstat_cmd],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                self.status = parse_faxstat_output(proc.stdout, self.lang)
            except Exception:
                self.status = {}

        if self.device and self.device in self.status:
            return self.status[self.device]

        return {"class": "modem-wait", "status": self.lang.get("PLSWAIT", "Please wait")}

    def get_alias(self) -> str | None:
        return self.alias

    def get_contact(self) -> str | None:
        return self.contact

    def get_printer(self) -> str | None:
        return self.printer

    def get_faxcatid(self) -> int | None:
        return self.faxcatid

    def get_devid(self) -> int | None:
        return self.devid

    def get_device(self) -> str | None:
        return self.device

    def get_error(self) -> str | None:
        return self.error

    def set_alias(self, alias: str) -> bool:
        if not self.devid:
            self.error = "No modem loaded"
            return False
        self.alias = alias
        self.modems.data.set_id(self.devid)
        self.all_data["alias"] = alias
        ok = bool(self.modems.update_entry(self.all_data))
        if ok:
            self.error = None
        return ok

    def set_contact(self, contact: str) -> bool:
        if not self.devid:
            self.error = "No modem loaded"
            return False
        self.contact = contact
        self.modems.data.set_id(self.devid)
        self.all_data["contact"] = contact
        ok = bool(self.modems.update_entry(self.all_data))
        if ok:
            self.error = None
        return ok

    def set_printer(self, printer: str) -> bool:
        if not self.devid:
            self.error = "No modem loaded"
            return False
        self.printer = printer
        self.modems.data.set_id(self.devid)
        self.all_data["printer"] = printer
        ok = bool(self.modems.update_entry(self.all_data))
        if ok:
            self.error = None
        return ok

    def set_faxcatid(self, faxcatid: int | None) -> bool:
        if not self.devid:
            self.error = "No modem loaded"
            return False
        self.faxcatid = faxcatid
        self.modems.data.set_id(self.devid)
        self.all_data["faxcatid"] = faxcatid
        ok = bool(self.modems.update_entry(self.all_data))
        if ok:
            self.error = None
        return ok


# Modern architectural alias
FaxModemService = FaxModem
