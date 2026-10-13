from __future__ import annotations

import os
import shlex
import subprocess
from typing import Any, Dict, List, Optional, Sequence

from namifax.services.user_account import NFUserAccount

SENDQ_KEYS = ["jid", "pri", "s", "owner", "mailaddr", "number", "pages", "dials", "tts", "status"]
DONEQ_KEYS = ["jid", "pri", "s", "owner", "mailaddr", "number", "pages", "dials", "status"]


def parse_queue_output(lines: Sequence[str], keys: Sequence[str]) -> List[Dict[str, Any]]:
    """Parse HylaFAX faxstat queue output lines into structured dictionary items."""
    cleaned = list(lines)

    # 1. Drop scheduler status line if present
    if cleaned and "HylaFAX scheduler on" in cleaned[0]:
        cleaned.pop(0)

    # 2. Drop modem lines
    while cleaned and cleaned[0].startswith("Modem "):
        cleaned.pop(0)

    # 3. Drop empty lines and header line (starting with JID)
    while cleaned and not cleaned[0].strip():
        cleaned.pop(0)

    if cleaned and cleaned[0].strip().startswith("JID"):
        cleaned.pop(0)

    queue = []
    num_keys = len(keys)
    last_idx = num_keys - 1

    for line in cleaned:
        tokens = line.split()
        if not tokens:
            continue

        item: Dict[str, Any] = {}
        for j, token in enumerate(tokens):
            if j < last_idx:
                item[keys[j]] = token
            else:
                if keys[last_idx] in item:
                    item[keys[last_idx]] += f" {token}"
                else:
                    item[keys[last_idx]] = token
        queue.append(item)

    return queue


class FaxQueue:
    """Service managing HylaFAX outbound send queue and failed queue operations."""

    def __init__(
        self,
        user_account: Optional[NFUserAccount] = None,
        faxsendq_cmd: str = "faxstat -s",
        faxdoneq_cmd: str = "faxstat -d",
        faxrm_cmd: str = "faxrm",
        faxalter_cmd: str = "faxalter",
        faxmail_user: Optional[str] = None,
        www_user: Optional[str] = None,
        auto_process: bool = True,
        db: Any = None,
    ) -> None:
        self.user_account = user_account
        self.db = db
        self.faxsendq_cmd = faxsendq_cmd
        self.faxdoneq_cmd = faxdoneq_cmd
        self.faxrm_cmd = faxrm_cmd
        self.faxalter_cmd = faxalter_cmd
        # the users whose jobs are matched to a person by mail address (the original's $FAXMAILUSER and $WWWUSER)
        self.faxmail_user = faxmail_user or os.environ.get("FAXMAILUSER", "faxmail")
        self.www_user = www_user or os.environ.get("WWWUSER", "www-data")

        self.queue: List[Dict[str, Any]] = []

        if auto_process:
            self.process_queue()

    def shell_exec(self, cmd: str) -> str:
        """Run a command (the configured faxstat command, split like a shell would) without a shell; return its stdout.

        A command that cannot be run (missing program, empty or malformed command) gives an empty output, never an error text.
        """
        try:
            argv = shlex.split(cmd)
            if not argv:
                return ""
            res = subprocess.run(argv, capture_output=True, text=True, check=False)
            return res.stdout or ""
        except (OSError, ValueError):
            return ""

    def process_queue(self, raw_output: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse active sending queue."""
        if raw_output is None:
            raw_output = self.shell_exec(self.faxsendq_cmd)

        lines = raw_output.splitlines()
        self.queue = parse_queue_output(lines, SENDQ_KEYS)
        return self.queue

    def process_failed_queue(self, raw_output: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parse done queue and filter for failed faxes (s == 'F')."""
        if raw_output is None:
            raw_output = self.shell_exec(self.faxdoneq_cmd)

        lines = raw_output.splitlines()
        items = parse_queue_output(lines, DONEQ_KEYS)
        self.queue = [item for item in items if item.get("s") == "F"]
        return self.queue

    def get_queue(self) -> List[Dict[str, Any]]:
        """Return queue decorated with resolved user display names."""
        user_svc = self.user_account or NFUserAccount(db=self.db)
        ret = []

        for q in self.queue:
            entry = dict(q)
            owner = entry.get("owner", "")
            mailaddr = entry.get("mailaddr", "")

            if owner in (self.faxmail_user, self.www_user):
                if user_svc.loadbyemail(mailaddr):
                    entry["user"] = getattr(user_svc, "name", None) or mailaddr
                else:
                    entry["user"] = mailaddr
            elif user_svc.load_username(owner):
                entry["user"] = getattr(user_svc, "name", None) or owner
            else:
                entry["user"] = owner

            ret.append(entry)

        return ret

    def list_owner(self, owner: str) -> List[Dict[str, Any]]:
        """Filter queue for specific owner or corresponding faxmail address."""
        user_svc = self.user_account or NFUserAccount(db=self.db)
        ret = []

        for q in self.queue:
            entry = dict(q)
            q_owner = entry.get("owner", "")
            mailaddr = entry.get("mailaddr", "")

            if q_owner == owner:
                if user_svc.load_username(q_owner):
                    entry["user"] = getattr(user_svc, "name", None) or owner
                else:
                    entry["user"] = owner
                ret.append(entry)
            elif q_owner in (self.faxmail_user, self.www_user):
                if user_svc.loadbyemail(mailaddr):
                    user_username = getattr(user_svc, "username", "")
                    if owner == user_username:
                        entry["user"] = getattr(user_svc, "name", owner)
                        ret.append(entry)

        return ret

    def killjob(self, user_or_jid: Any, jid: Optional[int] = None) -> bool:
        """Cancel and remove job from queue using faxrm. Supports (jid) or (user, jid)."""
        if jid is None:
            target_jid = int(user_or_jid)
            target_user = getattr(self.user_account, "username", "admin") or "admin"
        else:
            target_user = str(user_or_jid)
            target_jid = int(jid)

        env = dict(os.environ)
        env["FAXUSER"] = str(target_user)
        cmd = [self.faxrm_cmd, str(target_jid)]
        try:
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
            return proc.returncode == 0
        except Exception:
            return False

    kill_job = killjob

    def faxalter(self, user: str, jid: int, operations: Dict[str, Any]) -> bool:
        """Modify parameters of queued job using faxalter."""
        args = [self.faxalter_cmd]
        killjob = False

        for op, val in operations.items():
            if op == "resubmit":
                args.append("-r")
                killjob = True
            elif op == "sendtime":
                args.extend(["-a", str(val)])
            elif op == "destination":
                args.extend(["-d", str(val)])
            elif op == "killtime":
                args.extend(["-k", str(val)])
            elif op == "device":
                args.extend(["-m", str(val)])
            elif op == "priority":
                args.extend(["-P", str(val)])
            elif op == "tries":
                args.extend(["-t", str(val)])

        args.append(str(jid))
        env = dict(os.environ)
        env["FAXUSER"] = str(user)
        try:
            proc = subprocess.run(args, env=env, capture_output=True, text=True, check=False)
            success = (proc.returncode == 0)
        except Exception:
            return False

        if killjob:
            kill_ok = self.killjob(user, jid)
            return success and kill_ok

        return success
