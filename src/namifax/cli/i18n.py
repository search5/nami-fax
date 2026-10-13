"""NamiFAX i18n management CLI commands using Python Babel."""

from __future__ import annotations

import argparse
import os
import sys
from babel.messages.frontend import CommandLineInterface


def run_i18n(argv: list[str] | None = None) -> int:
    """CLI handler for `namifax i18n` command."""
    parser = argparse.ArgumentParser(
        prog="namifax i18n",
        description="NamiFAX Internationalization catalog management",
    )
    parser.add_argument(
        "action",
        choices=["extract", "update", "compile", "init"],
        help="i18n action to perform",
    )
    parser.add_argument(
        "-l", "--locale",
        help="Locale code for init or update (e.g. ko, en, ja)",
    )

    args = parser.parse_args(argv)
    cli = CommandLineInterface()

    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    cfg_file = os.path.join(root_dir, "babel.cfg")
    pot_file = os.path.join(root_dir, "src", "namifax", "locale", "namifax.pot")
    locale_dir = os.path.join(root_dir, "src", "namifax", "locale")

    if args.action == "extract":
        cmd = ["pybabel", "extract", "-F", cfg_file, "-o", pot_file, root_dir]
        return cli.run(cmd)

    elif args.action == "compile":
        cmd = ["pybabel", "compile", "-d", locale_dir, "-D", "namifax"]
        return cli.run(cmd)

    elif args.action == "update":
        cmd = ["pybabel", "update", "-i", pot_file, "-d", locale_dir, "-D", "namifax"]
        return cli.run(cmd)

    elif args.action == "init":
        if not args.locale:
            print("Error: --locale <lang> is required for init action", file=sys.stderr)
            return 1
        cmd = ["pybabel", "init", "-i", pot_file, "-d", locale_dir, "-l", args.locale, "-D", "namifax"]
        return cli.run(cmd)

    return 0
