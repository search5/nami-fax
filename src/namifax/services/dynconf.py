from __future__ import annotations

from typing import Any

from namifax.db.repository import MDBOData

DEFAULT_LANG = {
    "DYNCONF_EXISTS": "Rule already exists",
    "DYNCONF_NOT_CREATED": "Rule could not be created",
}


class DynamicConfig:
    """Service class for managing HylaFAX RejectCall rules (DynConf table)."""

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
            self.dynamicconfig = repo
        else:
            self.dynamicconfig = MDBOData("DynConf", db=self.db)

        self.dynconf_id: int | None = None
        self.device: str | None = None
        self.callid: str | None = None
        self.error: str | None = None

    def get_dynconf_id(self) -> int | None:
        return self.dynconf_id

    def get_device(self) -> str | None:
        return self.device

    def get_callid(self) -> str | None:
        return self.callid

    def get_error(self) -> str | None:
        return self.error

    def lookup(self, device: str | None, callid: str) -> bool:
        """Search for a RejectCall rule for given callid and device."""
        res = self.dynamicconfig.find({"callid": callid}, reduce_single=False)
        if res and isinstance(res, list):
            for result in res:
                rule_dev = result.get("device")
                # Rule with empty device matches all devices
                if not rule_dev:
                    return True
                # Match specific device
                if rule_dev == device:
                    return True
        return False

    def list_rules(self) -> list[dict[str, Any]]:
        """Return all reject rules ordered by callid."""
        return self.dynamicconfig.select(columns=["dynconf_id", "device", "callid"], order_by="callid")

    def remove(self, dynconf_id: int) -> bool:
        """Remove a rule by ID."""
        if not dynconf_id:
            self.error = "DynConf not selected"
            return False

        self.dynamicconfig.data.set_id(dynconf_id)
        ok = bool(self.dynamicconfig.delete_entry())
        if ok:
            self.error = None
        return ok

    def create(self, device: str | None, callid: str) -> bool:
        """Create a new reject rule for device and callid."""
        self.callid = callid
        self.device = device
        rule = {"callid": callid, "device": device}

        # Check if rule already exists
        if self.dynamicconfig.find(rule):
            self.error = self.lang.get("DYNCONF_EXISTS", "Rule already exists")
            return False

        # Add to DB
        if self.dynamicconfig.new_entry(rule):
            self.dynconf_id = self.dynamicconfig.get_id()
            self.error = None
            return True

        self.error = self.lang.get("DYNCONF_NOT_CREATED", "Rule could not be created")
        return False

    def load_rule(self, dynconf_id: int) -> bool:
        """Load a rule by ID."""
        if not dynconf_id:
            self.error = "DynConf not selected"
            return False

        if self.dynamicconfig.load(dynconf_id):
            data = self.dynamicconfig.get_info()
            self.dynconf_id = data.get("dynconf_id")
            self.device = data.get("device")
            self.callid = data.get("callid")
            self.error = None
            return True

        self.error = f"Rule {dynconf_id} doesn't exist"
        return False

    def save_rule(self, device: str | None, callid: str) -> bool:
        """Update the currently loaded rule."""
        if not self.dynconf_id:
            self.error = "DynConf not loaded"
            return False

        self.device = device
        self.callid = callid
        self.dynamicconfig.data.set_id(self.dynconf_id)
        ok = bool(self.dynamicconfig.update_entry({"device": device, "callid": callid}))
        if ok:
            self.error = None
        return ok


# Modern architectural alias
DynamicConfigService = DynamicConfig
