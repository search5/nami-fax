"""NamiFAX in-memory login session management."""

from __future__ import annotations

import datetime
import secrets
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class Session:
    """Active user session representation."""
    token: str
    user_id: int
    username: str
    is_admin: bool = False
    superuser: bool = False
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    last_accessed: datetime.datetime = field(default_factory=datetime.datetime.now)

    def is_expired(self, ttl_seconds: int = 7200) -> bool:
        """Check if session has expired based on inactivity timeout."""
        now = datetime.datetime.now()
        return (now - self.last_accessed).total_seconds() > ttl_seconds

    def touch(self) -> None:
        """Update last accessed timestamp."""
        self.last_accessed = datetime.datetime.now()


class SessionManager:
    """Thread-safe in-memory session manager with TTL eviction."""

    def __init__(self, ttl_seconds: int = 7200) -> None:
        self.ttl_seconds = ttl_seconds
        self._sessions: Dict[str, Session] = {}

    def create_session(
        self,
        user_id: int,
        username: str,
        is_admin: bool = False,
        superuser: bool = False,
    ) -> Session:
        """Generate and store new active session."""
        token = secrets.token_hex(32)
        sess = Session(
            token=token,
            user_id=user_id,
            username=username,
            is_admin=is_admin,
            superuser=superuser,
        )
        self._sessions[token] = sess
        return sess

    def get_session(self, token: Optional[str]) -> Optional[Session]:
        """Retrieve active session by token, updating last access time."""
        if not token or token not in self._sessions:
            return None

        sess = self._sessions[token]
        if sess.is_expired(self.ttl_seconds):
            del self._sessions[token]
            return None

        sess.touch()
        return sess

    def destroy_session(self, token: Optional[str]) -> bool:
        """Destroy existing session by token."""
        if token and token in self._sessions:
            del self._sessions[token]
            return True
        return False
