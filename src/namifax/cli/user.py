"""NamiFAX User management CLI."""

from __future__ import annotations

import argparse
import getpass
import os
from datetime import datetime
import sys
from typing import Any, Sequence

from namifax.db.provider import cli_session
from namifax.services.user_account import NFUserAccount


def run_createuser(argv: Sequence[str] | None = None, *, session: Any = None) -> int:
    parser = argparse.ArgumentParser(
        prog="namifax createuser",
        description="Create or update a NamiFAX user account",
    )
    parser.add_argument("-u", "--username", default="admin", help="Username (default: admin)")
    parser.add_argument("-p", "--password", default=None,
                        help="Password (otherwise NAMIFAX_NEW_USER_PASSWORD, or you are asked; there is no default)")
    parser.add_argument("-e", "--email", default="admin@namifax.local", help="Email address")
    parser.add_argument("-n", "--name", default="Administrator", help="Full name")
    parser.add_argument("--admin", action="store_true", default=True, help="Grant admin & superuser privileges")
    parser.add_argument("--user-only", action="store_false", dest="admin", help="Create as regular user")

    args = parser.parse_args(argv)

    args.password = _password(args.password)
    if args.password is None:
        return 2

    if session is not None:
        return _create_user(args, session)
    with cli_session(ensure_schema=True) as opened:
        return _create_user(args, opened)


def _password(given: str | None) -> str | None:
    """The password to set: the option, the environment, or a prompt for a person. None (after a message) if unusable."""
    password = given or os.environ.get("NAMIFAX_NEW_USER_PASSWORD")
    if not password:
        if not sys.stdin.isatty():
            print("[!] A password is required: use -p, set NAMIFAX_NEW_USER_PASSWORD, or run this in a terminal to be asked.")
            return None
        password = getpass.getpass("Password: ")
        if getpass.getpass("Repeat password: ") != password:
            print("[!] The passwords do not match.")
            return None
    from namifax.common import settings

    if len(password) < settings.min_passwd_size():
        print(f"[!] The password must be at least {settings.min_passwd_size()} characters long.")
        return None
    return password


def run_unlock_user(argv: Sequence[str] | None = None, *, session: Any = None) -> int:
    """Lift the lock of an account that was locked by too many wrong passwords (the administration does the same from the user list)."""
    parser = argparse.ArgumentParser(prog="namifax unlock-user", description="Unlock an account that too many wrong passwords locked")
    parser.add_argument("username")
    args = parser.parse_args(argv)
    if session is not None:
        return _unlock_user(args.username, session)
    with cli_session(ensure_schema=True) as opened:
        return _unlock_user(args.username, opened)


def _unlock_user(username: str, session: Any) -> int:
    from namifax.services.login_throttle import LoginThrottle

    if not LoginThrottle(session).unlock(username):
        print(f"{username} is not locked.")
        return 1
    print(f"{username} is unlocked.")
    return 0


def run_reset_2fa(argv: Sequence[str] | None = None, *, session: Any = None) -> int:
    """Turn two-factor authentication off for a user who lost their device and their recovery codes."""
    parser = argparse.ArgumentParser(prog="namifax reset-2fa", description="Remove a user's two-factor enrolment")
    parser.add_argument("username")
    args = parser.parse_args(argv)
    if session is not None:
        return _reset_2fa(args.username, session)
    with cli_session(ensure_schema=True) as opened:
        return _reset_2fa(args.username, opened)


def _reset_2fa(username: str, session: Any) -> int:
    from namifax.services.totp import TotpService

    user = NFUserAccount(db=session)
    if not user.load_username(username):
        print(f"[!] No such user: {username}")
        return 1
    TotpService(session).disable_totp(user.get_uid())
    print(f"[+] Two-factor authentication is off for '{username}'.")
    return 0


def _create_user(args: argparse.Namespace, session: Any) -> int:
    """Create or update the requested account in the given session."""
    user_svc = NFUserAccount(db=session)

    # Check if username already exists
    if user_svc.load_username(args.username):
        print(f"[*] User '{args.username}' already exists. Updating credentials...")
        if not user_svc.change_password(args.password):
            print(f"[!] The password was not changed: {user_svc.get_error()}")
            return 1
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_svc.useraccount.update_entry({
            "uid": user_svc.get_uid(),
            "name": args.name,
            "email": args.email,
            "is_admin": 1 if args.admin else 0,
            "superuser": 1 if args.admin else 0,
            "acc_enabled": 1,
            "wasreset": 0,
            "last_login": now_str,
            "pwdexpire": None,
        })
        print(f"[+] User '{args.username}' updated successfully.")
        return 0

    user_data = {
        "username": args.username,
        "password": args.password,
        "name": args.name,
        "email": args.email,
        "is_admin": 1 if args.admin else 0,
        "superuser": 1 if args.admin else 0,
        "acc_enabled": 1,
        "wasreset": 0,
        "last_login": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "pwdexpire": None,
    }

    if user_svc.create(user_data):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_svc.useraccount.update_entry({
            "uid": user_svc.get_uid(),
            "is_admin": 1 if args.admin else 0,
            "superuser": 1 if args.admin else 0,
            "acc_enabled": 1,
            "wasreset": 0,
            "last_login": now_str,
            "pwdexpire": None,
        })
        print(f"[+] Created user '{args.username}' (UID: {user_svc.get_uid()}, Admin: {args.admin}) successfully.")
        return 0
    else:
        print(f"[-] Failed to create user: {user_svc.get_error()}", file=sys.stderr)
        return 1
