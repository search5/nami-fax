from __future__ import annotations

from typing import Any

from namifax.common.passwords import hash_password, verify_password
from namifax.db.repository import MDBOData


class NFUserPasswords:
    """Service class for managing user password history (UserPasswords table)."""

    def __init__(
        self,
        db: Any = None,
        engine: Any = None,
        repo: MDBOData | None = None,
    ) -> None:
        self.db = db or engine
        if repo is not None:
            self.userpasswords = repo
        else:
            self.userpasswords = MDBOData("UserPasswords", db=self.db)

        self.upid: int | None = None
        self.uid: int | None = None
        self.pwdhash: str | None = None

    def log_password(self, pwd: str, uid: int) -> bool:
        """Hash and record password in UserPasswords history table."""
        if not pwd or uid is None:
            return False

        pwdhash = hash_password(pwd)
        return bool(self.userpasswords.new_entry({"uid": uid, "pwdhash": pwdhash}))

    def password_used(self, pwd: str, uid: int) -> bool:
        """Check if password hash already exists in history for user."""
        if not pwd or uid is None:
            return False

        rows = self.userpasswords.find({"uid": uid}, reduce_single=False) or []
        if isinstance(rows, dict):
            rows = [rows]
        return any(verify_password(row.get("pwdhash"), pwd) for row in rows)       # (salted hashes: compare one by one)

    def clear_hashes(self, uid: int) -> bool:
        """Clear all historical password records for user."""
        if uid is None:
            return False
        self.userpasswords.delete_where({"uid": uid})
        return True


# Modern architectural alias
PasswordHistoryService = NFUserPasswords
