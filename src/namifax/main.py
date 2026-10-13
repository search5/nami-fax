#!/usr/bin/env python3
"""NamiFAX unified CLI entry point.

Unified CLI for system services, HylaFAX hooks, APScheduler maintenance, and web server.
"""

from __future__ import annotations

import os
import sys
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, make_server


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True

# Ensure src directory is on sys.path
SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import argparse

from namifax.cli.cron import run_cron
from namifax.db.bootstrap import ensure_schema
from namifax.db.provider import create_sa_engine, resolve_database_url
from namifax.cli.dynconf import run_dynconf
from namifax.cli.faxcover import run_faxcover
from namifax.cli.faxrcvd import run_faxrcvd
from namifax.cli.notify import run_notify
from namifax.cli.phb import main as run_phb
from namifax.cli.user import run_createuser, run_reset_2fa, run_unlock_user
from namifax.services.scheduler import get_scheduler

USAGE = """NamiFAX Modernized Enterprise System CLI

Usage:
  namifax <command> [arguments]

Available commands:
  serve              Start the HTTP / API web service (with integrated APScheduler)
  createuser         Create or update user account (ID / PW credentials)
  import-archive     Import an existing HylaFAX/AvantFAX fax archive directory into the database
  unlock-user        Unlock an account that too many wrong passwords locked
  reset-2fa          Turn off two-factor authentication for a user (lost device and recovery codes)
  encrypt-secrets    Encrypt stored credentials (cloud key, SMTP password, 2FA seeds) with NAMIFAX_SECRET_KEY
  dynconf            Execute HylaFAX dynamic configuration call filter
  cron               Execute periodic maintenance and archive cleanup (manual trigger)
  notify             Execute HylaFAX outbound post-send notification hook
  faxrcvd            Execute HylaFAX inbound received fax processing hook
  faxcover           Generate HylaFAX fax cover page
  phb                Generate HylaFAX PBOOK1.1 format phonebook
  print-in           CUPS backend: send a printed document as a fax (needs a [[FAX: number]] tag in the text)
  ocr-import         Execute OCR text extraction batch on archive
  create-thumbnails  Batch generate fax page thumbnails
  import-users       Import user accounts from tab-delimited text
  import-blacklist   Import blacklist rules from text file
  reroute            Reroute modem or DID routing notification email
  i18n               Manage translation catalogs (extract, compile, update, init)

Run 'namifax <command> --help' for details on a specific command.
"""


def _load_ini_settings(path: str) -> dict:
    """The [app:main] settings of a PasteDeploy ini file (``%(here)s`` expanded), as ``pserve`` would pass them."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"no such file: {path}")
    from pyramid.paster import get_appsettings

    return dict(get_appsettings(os.path.abspath(path), name="main"))


def serve_main(argv: list[str] | None = None) -> int:
    """Entry point for namifax-server / namifax serve."""
    parser = argparse.ArgumentParser(prog="namifax serve", description="Start NamiFAX Web Service")
    parser.add_argument("--host", default=os.environ.get("NAMIFAX_HOST", "0.0.0.0"), help="Bind host")
    parser.add_argument("--port", type=int, default=int(os.environ.get("NAMIFAX_PORT", "8000")), help="Bind port")
    parser.add_argument(
        "--config", "-c", default=os.environ.get("NAMIFAX_INI") or None,
        help="ini file whose [app:main] section supplies the app settings (session.secret, session.secure, "
             "csrf.trusted_origins, secret.key, sqlalchemy.url ...); default: $NAMIFAX_INI, else none",
    )
    args, _ = parser.parse_known_args(argv or [])
    host = args.host
    port = args.port

    settings: dict = {}
    if args.config:
        try:
            settings = _load_ini_settings(args.config)
        except Exception as exc:
            print(f"[!] Cannot read the configuration file {args.config}: {exc}", file=sys.stderr)
            return 1

    # Ensure DB tables exist (same URL resolution as the web app, no global engine)
    engine = create_sa_engine(resolve_database_url(settings, os.environ))
    try:
        ensure_schema(engine)
    finally:
        engine.dispose()

    # Start in-process APScheduler if enabled
    enable_internal_sched = os.environ.get("NAMIFAX_ENABLE_SCHEDULER", "1") in ("1", "true", "True")
    if enable_internal_sched:
        scheduler = get_scheduler()
        scheduler.start()
        print("[*] In-process APScheduler started.")

    try:
        from namifax import create_app as make_app
        app = make_app(**settings)
    except Exception as exc:
        print(f"[!] NamiFAX web application failed to start: {exc!r}", file=sys.stderr)
        if enable_internal_sched:
            get_scheduler().stop()
        return 1

    print(f"[*] Starting NamiFAX Web Service on http://{host}:{port} ...")
    with make_server(host, port, app, server_class=ThreadingWSGIServer) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[*] Shutting down NamiFAX Web Service...")
            if enable_internal_sched:
                get_scheduler().stop()
    return 0


def createuser_main() -> None:
    sys.exit(run_createuser(sys.argv[1:]))


def dynconf_main() -> None:
    sys.exit(run_dynconf(["dynconf"] + sys.argv[1:]))


def faxrcvd_main() -> None:
    sys.exit(run_faxrcvd(["faxrcvd.php"] + sys.argv[1:]))


def notify_main() -> None:
    sys.exit(run_notify(["notify.php"] + sys.argv[1:]))


def faxcover_main() -> None:
    sys.exit(run_faxcover(["faxcover.php"] + sys.argv[1:]))


def cron_main() -> None:
    sys.exit(run_cron(["avantfaxcron.php"] + sys.argv[1:]))


def phb_main() -> None:
    sys.exit(run_phb())


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]

    if not args:
        print(USAGE)
        return 0

    cmd = args[0]
    sub_args = args[1:]

    if cmd in ("-h", "--help", "help"):
        print(USAGE)
        return 0

    if cmd == "serve":
        return serve_main(sub_args)

    elif cmd == "createuser":
        return run_createuser(sub_args)

    elif cmd == "dynconf":
        return run_dynconf(["dynconf"] + sub_args)

    elif cmd == "cron":
        return run_cron(["avantfaxcron.php"] + sub_args)

    elif cmd == "notify":
        return run_notify(["notify.php"] + sub_args)

    elif cmd == "faxrcvd":
        return run_faxrcvd(["faxrcvd.php"] + sub_args)

    elif cmd == "faxcover":
        return run_faxcover(["faxcover.php"] + sub_args)

    elif cmd == "phb":
        return run_phb()

    elif cmd in ("print-in", "print_in"):
        from namifax.cli import print_in
        return print_in.main(["print_in"] + sub_args)

    elif cmd in ("ocr-import", "ocr_import"):
        from namifax.cli import ocr_import
        return ocr_import.main(sub_args)

    elif cmd in ("create-thumbnails", "create_thumbnails"):
        from namifax.cli import create_thumbnails
        return create_thumbnails.main(sub_args)

    elif cmd in ("import-users", "import_users"):
        from namifax.cli import import_users
        return import_users.main(sub_args)

    elif cmd in ("import-blacklist", "import_blacklist"):
        from namifax.cli import import_blacklist
        return import_blacklist.main(sub_args)

    elif cmd in ("import-archive", "import_archive"):
        from namifax.cli import import_archive
        return import_archive.main(sub_args)

    elif cmd in ("unlock-user", "unlock_user"):
        return run_unlock_user(sub_args)

    elif cmd in ("reset-2fa", "reset_2fa"):
        return run_reset_2fa(sub_args)

    elif cmd in ("encrypt-secrets", "encrypt_secrets"):
        from namifax.cli import encrypt_secrets
        return encrypt_secrets.run_encrypt_secrets(sub_args)

    elif cmd == "reroute":
        from namifax.cli import reroute
        return reroute.main(sub_args)

    elif cmd == "i18n":
        from namifax.cli.i18n import run_i18n
        return run_i18n(sub_args)

    else:
        print(f"Unknown command: {cmd}\n")
        print(USAGE)
        return 1


if __name__ == "__main__":
    sys.exit(main())
