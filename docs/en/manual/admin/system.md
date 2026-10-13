# System

This page covers **System Functions**, **System Audit Logs**, the **SMTP Gateway** and **Network Printers**. The first two need the *Administrator Console* or *Superuser* flag; the last two need the *Superuser* flag (see [overview](index.md)).

## System Functions

**System Functions** (`/admin/sysfunc`, also `/admin/system_func`) has two panels in one form.

!!! danger "Read before pressing a button"
    The panel warns that restarting or shutting down will interrupt active modem spooling and disconnect client sessions. Make sure no transmission is still in the modem queue first.

### Daemon Service Control

Shows whether three processes are running, found by name on the server: **faxq daemon** and **hfaxd daemon** (HylaFAX) and the **web worker** (the NamiFAX web process, with its process id). Each shows `RUNNING (pid n)`, `NOT RUNNING`, or `unknown` when the check could not be made.

| Button | What it really does |
|---|---|
| **Reboot Services** | Runs the command in the environment variable `NAMIFAX_REBOOT_CMD`; by default `sudo /sbin/reboot`. This restarts the **whole server**, not only the services. No confirmation is asked. |
| **Shutdown Services** | Runs `NAMIFAX_SHUTDOWN_CMD`; by default `sudo /sbin/halt`. This halts the **whole server**. A confirmation dialog is shown first. |

Both need `sudo` to be allowed, without a password prompt, for the user that runs the web service (for example through a `sudoers` rule), or you must set the two variables to commands that work in your environment. The page shows *The system is rebooting. Please wait...* or *The system is shutting down. Please wait...* as soon as the command has been started; it does not wait for the result. If the command cannot be started at all, the error *The command could not be run* is shown with the reason.

### Database & Archive Backup

| Button | Result |
|---|---|
| **Download Archive** | A gzip-compressed tar file `avantfax-archive-YYYYMMDD.tar.gz` with the received-fax archive folder (`AVANTFAX_ARCHIVE`, default `<HYLASPOOL>/archive`) and the sent-fax folder (`AVANTFAX_ARCHIVE_SENT`, else `ARCHIVE_SENT`, default `<HYLASPOOL>/sent`), whichever exist. If neither exists: *There is no fax archive folder to download.* |
| **Download Database** | A gzip-compressed SQL dump `avantfax-schema-YYYYMMDD.sql.gz`. SQLite is dumped by NamiFAX itself; MySQL/MariaDB needs `mysqldump` and PostgreSQL needs `pg_dump` on the server. If that fails: *The database dump could not be made*. |

The archive can be large, and the download is built on the server first. If you use the cloud storage option, see [Storage and scheduler](storage-scheduler.md).

!!! note "Fixed sample text"
    The lines *Archive Storage: 12.4 GB in 1,420 files*, *Database Size: 18.2 MB* and *Last Snapshot: Today, 04:00 AM*, and the *HylaFAX Engine Active* badge, are fixed text. They are not measured and no snapshot is taken automatically.

## System logs

**System Audit Logs** in the menu (`/admin/syslog`, also `/admin/system_logs`) is titled **System Logs**. It lists events NamiFAX writes: sign-ins and failed sign-ins (with the password masked except its last three characters), password resets, account unlocks, the receive, notify and `dynconf` hooks, scheduler runs and cloud upload failures. The table has **Date** and **Log Text**, newest first, 100 rows per page (**Previous** / **Next**, *Page n / m*).

- When you open the page, it lists today's events.
- **Keywords**: a case-insensitive substring of the log text.
- **Date**: the three drop-downs DD / MM / YYYY. A date filter needs a year; choosing year only matches the whole year, year and month matches the month, and all three match one day. A day without a year is ignored.
- Press **Search**. A search with no date lists all events that match the keyword.

## SMTP gateway

**SMTP Gateway** (`/admin/smtp`, *Superuser only*) sets the mail server that NamiFAX uses for every e-mail it sends: passwords of new users, *Forgot password?* mails, received faxes sent to contacts, and notifications. If nothing has been saved, NamiFAX uses `localhost` port 25.

**Server Connection & Security**

| Field | Meaning |
|---|---|
| **SMTP Host / Server** \* | Server name. |
| **Port** \* | 1 to 65535. |
| **Encryption Protocol** | **None (Plain)**, **STARTTLS (587)** or **SSL / TLS (465)**. The numbers in the labels are only hints; the port is whatever you enter. |
| **Requires SMTP Authentication** | Tick to log in with the next two fields. |
| **Username / Login**, **Password / App Key** | Credentials. The password box is pre-filled with the saved password. |

**Default Sender Profile & Signatures**: **From Email Address** \*, **From Display Name**, **Email Signature (Plaintext)**.

Press **Save Gateway Settings**. The SMTP password is stored encrypted; this needs the key `NAMIFAX_SECRET_KEY` (or `secret.key` in the ini file) to be set, otherwise saving a non-empty password fails with an error. The page shows when the settings were last updated.

**Diagnostic Self-Test**: enter a **Target Recipient Email** (it starts with your own address) and press **Send Diagnostic Email**. NamiFAX uses the values currently in the form, saved or not, connects (10 second limit), greets the server, starts TLS if chosen, logs in if chosen and sends a short test message. The **Diagnostics Result** box lists each step and the error if one failed.

## Network printers

**Network Printers** (`/admin/printers`, *Superuser only*) keeps a list of network printers.

**Add Network Printer**: **Printer Name** \*, **Protocol** (`RAW` port 9100 / JetDirect, `IPP` or `LPD` / LPR), **Host / IP** \*, **Port** (9100 by default), **Queue Name (Optional)**, **Description**. Press **Register Printer**. The list **Configured Printers** shows **Name**, **Protocol**, **Endpoint** (`host:port`) and **Description**, with two actions per row:

- **Test Print** opens a plain TCP connection to the host and port and sends a short text line with a form feed. This is a raw-socket test whatever protocol the entry has, so it fits `RAW` printers on port 9100; it is not an IPP or LPD test. The result is shown as a success or error message.
- **Delete** (with a confirmation) removes the entry.

!!! note "What the list is used for"
    In the current code the list is used only on this screen. The **Printer** boxes of [fax lines, DID routes, barcode rules and Fax to Email](fax-lines.md) are free text (for example `lp0`) that is passed to the print command on the server, and they do not read this list.
