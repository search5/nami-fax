# Getting started

## Requirements

- Python 3.11 or newer
- A database: SQLite (nothing to install), MySQL/MariaDB or PostgreSQL (a server is needed)
- HylaFAX: needed to actually send and receive faxes
- Ghostscript (optional): used for PostScript conversion and PDF previews of sent faxes
- Tesseract (optional): searching the text of received faxes (OCR)

## Try it quickly for development

```sh
uv sync                                    # install dependencies (--extra mysql / --extra postgresql for those databases)
uv run namifax createuser -u admin         # create an administrator (it asks for the password; there is no default)
uv run namifax serve --host 127.0.0.1 --port 8000
```

`namifax serve` is a development server. The database is chosen with the `DATABASE_URL` environment variable; without it a SQLite file is created in the current folder. To change the look of the screens you must rebuild the Tailwind CSS with `npm run build:css`.

## Installing on a production server

In production use `production.ini` with `pserve` (waitress) or `systemd/namifax.service`. The steps are:

1. If you do not have a HylaFAX server yet, start with [Preparing the HylaFAX server](hylafax-server.md).
2. Follow [HylaFAX setup](hylafax.md) to set up the environment file, the HylaFAX hooks, the web service and the periodic jobs.
3. To send faxes by e-mail, set up [E-mail to fax](email-to-fax.md). Operational know-how such as moving the receive spool and housekeeping is in the [HylaFAX operations notes](hylafax-operations.md).
4. Use the [operations checklist](operations-checklist.md) to check security settings and backups.
5. If you already run AvantFAX 3.x, read [Migrating from AvantFAX 3.x](migration.md) before the steps above.

The installation files are in the repository under `deploy/` (apache, nginx, postfix, hylafax, cups, cron.d, sudoers.d) and `systemd/`.

## Building this manual

```sh
pip install -r requirements-docs.txt
mkdocs serve          # preview at http://127.0.0.1:8000
mkdocs build          # generate the static site in site/
```
