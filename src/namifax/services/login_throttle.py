"""Limit repeated failed password sign-ins.

An account is locked after ``NAMIFAX_LOGIN_MAX_FAILURES`` (default 5) wrong passwords in a row: from the next attempt on the password
is not even looked at, so the right one does not help either, and **the lock does not end with time**. Only an administrator lifts
it (the user list of the administration, or ``namifax unlock-user`` on the server). The failures of an account are counted from its
last successful sign-in; they do not expire.

Failures are counted per user name whether or not the account exists, so the answer never reveals which names are real. They are
also counted per client address, with a higher limit (``IP_FACTOR`` times), because an address can be a whole office or a proxy: an
address is locked for ``NAMIFAX_LOGIN_LOCK_MINUTES`` (default 15) only and then tried again. The counters live in ``SystemConfig`` so
every worker process sees the same state.

An attempt is counted before its password is looked at (``begin_attempt``), under the row locks of both counters, so attempts that
arrive together are counted one after the other and cannot all be checked. A success clears the user-name counter and gives the
address the count of that attempt back (an office is not locked by its successful sign-ins).
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any, Iterable

IP_FACTOR = 10                                # an address may fail this many times more than a single user name (5 x 10 = 50)


def _now() -> float:                          # a seam for tests
    return time.time()


def _int_env(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, "") or default)
    except ValueError:
        return default
    return value if value > 0 else default


def max_failures() -> int:
    return _int_env("NAMIFAX_LOGIN_MAX_FAILURES", 5)


def lock_seconds() -> int:
    """How long an address stays locked (an account stays locked until an administrator unlocks it)."""
    return _int_env("NAMIFAX_LOGIN_LOCK_MINUTES", 15) * 60


def _key(kind: str, value: str) -> str:
    return f"login_throttle:{kind}:" + hashlib.sha256((value or "").strip().lower().encode()).hexdigest()[:32]


class LoginThrottle:
    def __init__(self, session: Any) -> None:
        from namifax.services.system_config import SystemConfigService

        self.cfg = SystemConfigService(session)
        self._locked_by_this_attempt = False

    @staticmethod
    def _parse(raw: str) -> dict[str, Any]:
        try:
            state = json.loads(raw or "{}")
            return state if isinstance(state, dict) else {}
        except ValueError:
            return {}

    def _load(self, key: str) -> dict[str, Any]:
        return self._parse(self.cfg.get(key, ""))

    # --- who is locked ------------------------------------------------------------------------------------------------------

    def lock_reason(self, username: str, ip: str | None = None) -> str | None:
        """``"account"`` (until an administrator unlocks it), ``"address"`` (for a while) or None."""
        if self._load(_key("user", username)).get("locked"):
            return "account"
        if ip and float(self._load(_key("ip", ip)).get("until") or 0) > _now():
            return "address"
        return None

    def is_locked(self, username: str, ip: str | None = None) -> bool:
        return self.lock_reason(username, ip) is not None

    def locked_accounts(self, usernames: Iterable[str]) -> set[str]:
        """Those of ``usernames`` that are locked (for the user list of the administration)."""
        from sqlalchemy import select

        from namifax.models import SystemConfig

        by_key = {_key("user", name): name for name in usernames}
        if not by_key:
            return set()
        rows = self.cfg.session.execute(select(SystemConfig.key, SystemConfig.value).where(SystemConfig.key.in_(list(by_key))))
        return {by_key[key] for key, value in rows if self._parse(value or "").get("locked")}

    def unlock(self, username: str) -> bool:
        """Lift the lock of an account and start its count again (only an administrator calls this). False: it was not locked."""
        key = _key("user", username)
        if not self._load(key).get("locked"):
            return False
        self.cfg.locked_update(key, lambda raw: "{}")
        return True

    def forget(self, username: str) -> None:
        """Drop what is known about a name (a new account must not start locked because a stranger tried its name before)."""
        key = _key("user", username)
        if self._load(key):
            self.cfg.locked_update(key, lambda raw: "{}")

    # --- counting -----------------------------------------------------------------------------------------------------------

    @staticmethod
    def _counted(state: dict, now: float, period: float, limit: int) -> dict:
        """An address after one more failure: a new window when the old one is over, and a lock for a while at the limit."""
        if not state.get("start") or now - float(state["start"]) > period:
            state = {"n": 0, "start": now}                             # an old window (or an expired lock): start again
        state["n"] = int(state.get("n", 0)) + 1
        if state["n"] >= limit:
            state["until"] = now + period
        return state

    @staticmethod
    def _counted_account(state: dict, now: float, limit: int) -> dict:
        """An account after one more attempt: the count has no time limit, and the limit locks it until it is unlocked."""
        state = dict(state)
        state["n"] = int(state.get("n", 0)) + 1
        state.setdefault("start", now)
        if state["n"] >= limit:
            state["locked"] = True
            state["since"] = now
        return state

    def begin_attempt(self, username: str, ip: str | None = None) -> bool:
        """Count a sign-in attempt before its password is looked at; False (nothing counted) when the account or the address is
        locked, so that the password is not looked at.

        The rows of the user name and the address are locked (``SystemConfigService.lock``), the user name always first, so
        attempts that arrive together are counted one after the other: of forty at once only as many as the limit are let
        through. The attempt that reaches the limit is checked, and it locks the account at once; a success on that very attempt
        lifts that lock again (``record_success``)."""
        now, period, limit = _now(), lock_seconds(), max_failures()
        user_row = self.cfg.lock(_key("user", username))
        ip_row = self.cfg.lock(_key("ip", ip)) if ip else None
        user_state = self._parse(user_row.value or "")
        ip_state = self._parse(ip_row.value or "") if ip_row is not None else {}
        if user_state.get("locked") or float(ip_state.get("until") or 0) > now:
            return False
        counted = self._counted_account(user_state, now, limit)
        self._locked_by_this_attempt = bool(counted.get("locked"))
        user_row.value = json.dumps(counted)
        if ip_row is not None:
            ip_row.value = json.dumps(self._counted(ip_state, now, period, limit * IP_FACTOR))
        self.cfg.session.flush()
        return True

    def record_failure(self, username: str, ip: str | None = None) -> None:
        """Count one failure after the fact (the sign-in view counts with ``begin_attempt`` before the password is checked).
        The counters are changed under a row lock, so failures that arrive at the same moment are all counted and none of them
        ends in an error; the user name is always locked before the address."""
        now, period, limit = _now(), lock_seconds(), max_failures()

        def count_account(raw: str) -> str:
            state = self._parse(raw)
            return raw if state.get("locked") else json.dumps(self._counted_account(state, now, limit))

        def count_address(raw: str) -> str:
            state = self._parse(raw)
            if float(state.get("until") or 0) > now:
                return raw                                             # already locked: the clock is not extended
            return json.dumps(self._counted(state, now, period, limit * IP_FACTOR))

        self.cfg.locked_update(_key("user", username), count_account)
        if ip:
            self.cfg.locked_update(_key("ip", ip), count_address)

    def record_success(self, username: str, ip: str | None = None) -> None:
        """A right password clears the user name. A lock is never lifted here, except the one that this very attempt caused by
        reaching the limit (the right password came with the last try). With ``ip`` (the attempt was counted by ``begin_attempt``)
        the address gets that one count back, and the lock that this attempt itself caused, so that the successful sign-ins of
        an office never lock the address; the address is not cleared (one's own account could be used to reset it)."""
        key = _key("user", username)
        state = self._load(key)
        if state and (not state.get("locked") or self._locked_by_this_attempt):
            self.cfg.locked_update(key, lambda raw: "{}")
        if ip:
            ip_key, limit = _key("ip", ip), max_failures() * IP_FACTOR

            def give_back(raw: str) -> str:
                state = self._parse(raw)
                state["n"] = max(int(state.get("n", 0)) - 1, 0)
                if state["n"] < limit:
                    state.pop("until", None)
                return json.dumps(state)

            if self._load(ip_key):
                self.cfg.locked_update(ip_key, give_back)
