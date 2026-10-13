"""namifax.cli.import_users

Batch user import tool matching legacy tools/import_users.php.
"""

from __future__ import annotations

import os
import sys

from typing import Any

from namifax.db.provider import cli_session
from namifax.services.user_account import NFUserAccount


def main(args=None, *, db: Any = None, session: Any = None):
    if args is None:
        args = sys.argv[1:]

    if len(args) < 1:
        print("""usage: import_users.php filename
Example: import_users.php users.txt
One user entry per line with fields: name, username, password, and email separated by 1 tab
Example:
John Doe\tjohndoe\tpassw0rd\tjohn.doe@mycompany.com
NOTE: Be sure to set $AVANTFAX_SERVERNAME in includes/local_config.php before running this script""")
        return 0

    filename = args[0]
    if not os.path.isfile(filename):
        print(f"Error: File not found: {filename}")
        return 1

    with open(filename, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    if db is not None or session is not None:
        return _import_users(lines, session if session is not None else db)
    with cli_session(ensure_schema=True) as opened:
        return _import_users(lines, opened)


def _import_users(lines: list[str], db: Any) -> int:
    user_details_base = {
        "name": None,
        "username": None,
        "password": None,
        "email": None,
        "email_sig": None,
        "from_company": os.environ.get("FROM_COMPANY", ""),
        "from_location": os.environ.get("FROM_LOCATION", ""),
        "from_voicenumber": os.environ.get("FROM_VOICENUMBER", ""),
        "from_faxnumber": os.environ.get("FROM_FAXNUMBER", ""),
        "superuser": 0,
        "can_del": 0,
        "language": os.environ.get("NAMIFAX_DEFAULT_LANGUAGE", "en"),
        "pwdcycle": 0,
        "pwd_reuse": 0,
        "is_admin": 0,
        "acc_enabled": 1,
    }

    for line in lines:
        line = line.rstrip("\r\n")
        if not line:
            continue

        parts = line.split("\t", 3)
        if len(parts) < 4:
            print(f"Error> {parts[0]}: expected name, username, password and email separated by tabs")
            continue

        name, username, password, email = parts[0], parts[1], parts[2], parts[3]
        user_details = dict(user_details_base)
        user_details["name"] = name
        user_details["username"] = username
        user_details["password"] = password
        user_details["email"] = email

        user = NFUserAccount(db=db)
        if user.create(user_details):
            print(f"user> {name}: User details saved")
        else:
            print(f"Error> {name}: {user.get_error()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
