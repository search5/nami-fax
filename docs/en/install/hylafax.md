# HylaFAX Integration Installation Guide

These are the steps for connecting NamiFAX to HylaFAX. The files are in the `deploy/` folder. **This repository has not been tested against a real HylaFAX.** The steps below carry over what the original AvantFAX install scripts (`debian-install.sh`, `setup-postfix.sh`, etc.; the original source is in `legacy/` at commit 9408385) did, and each step includes a way to verify it. Run through them once on a test server before applying them to a production server.

Assumed paths: NamiFAX is in `/opt/namifax` (virtual environment `.venv`), the HylaFAX spool is `/var/spool/hylafax`, and the service user is `uucp`. If yours differ, change the corresponding parts of the files in `deploy/`.

## 0. Environment file

Put the DB connection and settings in `/etc/namifax.env` (mode 0640). All the files in the repository read this one file.

- systemd service (`systemd/namifax.service`): `EnvironmentFile=-/etc/namifax.env`
  (Because of the `-`, the service still starts if the file is missing. However, `DATABASE_URL` is then absent and the service silently falls back to a SQLite file in the current folder, so be sure to create the file).
- cron (`deploy/cron.d/namifax`): cron has no `EnvironmentFile`, so each line first reads the file with `sh -c 'set -a; . /etc/namifax.env; set +a; exec …'`.
- HylaFAX hook scripts (`deploy/hylafax/bin/*`): they run `set -a; . /etc/namifax.env; set +a` and then `exec`.

**Write one `KEY=value` per line, and do not use `export` or a trailing `#` comment after a value.** systemd and the shell read the same file, and systemd treats a `#` at the end of a line as part of the value. Write comments as separate lines that start with `#`.
If a value contains `&` `;` `(` `)` `<` `>` `|` or a space (for example, a DB URL with `?charset=utf8mb4&x=1` appended), **wrap it in double quotes**: systemd and the shell strip double quotes the same way. Without quotes, the shell ends the command at the `&`, so the value comes out empty or truncated. Do not put `$`, a backslash, a backtick, or `"` inside the double quotes.

```
DATABASE_URL=mysql+pymysql://avantfax:비밀번호@localhost/avantfax
NAMIFAX_SESSION_SECRET=<긴-무작위-문자열>
NAMIFAX_SECRET_KEY=<비밀저장소에-따로-보관>
# ENABLE_DID_ROUTING 은 훅과 웹이 같은 값을 써야 합니다
ENABLE_DID_ROUTING=0
FAXMAILUSER=faxmail
# WWWUSER 는 서비스를 실행하는 사용자
WWWUSER=uucp
```

If HylaFAX is not in the default location, tell NamiFAX with `HYLASPOOL`, `HYLAFAX_PREFIX`, and `BINARYDIR` (they are used to find `sendfax`, `faxstat`, `faxinfo`, and `faxadduser`).

## 1. Connecting the hooks

1. Copy `deploy/hylafax/bin/*` to `/var/spool/hylafax/bin/` and make the files executable
   (`faxrcvd`, `dynconf`, `notify`, `faxcover`). The owner is the user HylaFAX runs the hooks as (usually `uucp`).
2. Append the three lines of `deploy/hylafax/config.namifax` to each modem configuration (`/etc/hylafax/config.ttyS0`, etc.).
   If there are several modems, append them to every file.
3. Append the `JobFmt` line from `deploy/hylafax/hfaxd.conf.snippet`, and the `NotifyCmd` and `CoverCmd` lines from
   `deploy/hylafax/etc-faxq.snippet`, to the server configuration (`/var/spool/hylafax/etc/config`).
   **`JobFmt` must match the column order NamiFAX reads.** If it does not, the outbox list is misaligned or looks empty.
4. Restart HylaFAX: `systemctl restart hylafax` (or `faxq`, `hfaxd`, `faxgetty`, depending on the distribution).

Verify: `sudo -u uucp /var/spool/hylafax/bin/dynconf ttyS0 5551234` should finish without printing anything (for a blocked number it prints
`RejectCall: true`). A `dynconf> checking CallID1 …` line is left on the system log screen.

## 2. Web service

- Place the top-level `systemd/namifax.service` (not the one under `deploy/`) in `/etc/systemd/system/`, then run `systemctl daemon-reload && systemctl enable --now namifax`. This service reads `/etc/namifax.env` (step 0).
- Front web server: `deploy/nginx/namifax.conf` or `deploy/apache/namifax.conf`. If you use HTTPS, `session.secure = true` is needed in the ini, but `namifax serve` reads the ini **only when you pass the option**. Either change `ExecStart` in the service file to `namifax serve --config /etc/namifax/production.ini`, or add `NAMIFAX_INI=/etc/namifax/production.ini` to the environment file (from `[app:main]` in the ini it reads `session.secret`, `session.secure`, `csrf.trusted_origins`, `secret.key`, and `sqlalchemy.url`. Starting with `pserve production.ini` behaves the same).
  Behind a proxy, you must pass `X-Forwarded-Host` for the origin check on state-changing requests to succeed.
- First administrator: `namifax createuser -u admin -e you@example.com`.

## 3. User synchronization (optional)

A user name must be registered with the HylaFAX server (`hfaxd`) for `faxrm` and `faxalter` to handle that user's jobs. The original ran `faxadduser`/`faxdeluser` through `sudo` every time an account was created or a password was changed. To turn on the same behavior:

1. Copy `deploy/sudoers.d/namifax` to `/etc/sudoers.d/namifax` (mode 0440, check with `visudo -cf`). Adjust the service user name.
2. Set `HYLAFAX_USER_SYNC=1` in `/etc/namifax.env`.
3. Change `NoNewPrivileges=true` in `systemd/namifax.service` to `false`. While it is on, `sudo` does not work.

`faxadduser` accepts the password only as a command-line argument (`-p`), so for the brief moment it runs, other users on the same server can see it with `ps` (the same limitation as the original). Use this on a dedicated machine that has no other users. When it is off (the default), nothing is executed.

## 4. Periodic jobs

Configure them under **Admin > Scheduled Jobs** (`/admin/scheduler`; there is no `/admin/maintenance`). The built-in scheduler runs four jobs (`tmp`, `inbox`, `lifecycle`, `phonebook`): cleaning the temporary folder (days, time), moving old faxes in the received-fax inbox to the archive (days, time; off by default), applying the retention policy (policy values are on the Storage & Cloud screen), and exporting the phone book (interval). Each job shows "Run now" and its last run result. A saved change is picked up by the running scheduler within 1 minute (no restart needed), and the top of the screen has the scheduler status and **Stop/Start** buttons. Stopping shuts down the APScheduler engine itself so that no job runs on its own (the process remains and checks for a start request every 15 seconds); starting brings the engine up again. The stopped state is stored in the DB and persists across restarts. The scheduler runs only inside the web service process (`NAMIFAX_ENABLE_SCHEDULER=1`, the default). There is no separate scheduler service. Do not run more than one web service against the same database (the schedulers would overlap). The cron method below is an alternative for when you do not use the scheduler.


Copy `deploy/cron.d/namifax` to `/etc/cron.d/namifax` and set the retention period.
The built-in scheduler (`NAMIFAX_ENABLE_SCHEDULER=1`) runs the four jobs above (`inbox`, which archives the received-fax inbox, is off by default, and `lifecycle` runs once a storage policy has been saved). However, **there is no scheduler job that corresponds exactly to `-d`, which deletes old faxes in the archive by date** (the closest thing is `full_retention_days` in the storage policy). If you need `-d`, put it in cron. If nothing is turned on, faxes pile up forever. The cron lines are wrapped in `sh -c` so that they read the environment file, so keep that form when you edit a line.

## 5. Sending faxes by email (optional)

`deploy/postfix/setup-email2fax.md`. This is the configuration the original `setup-postfix.sh` performed; the script in this repository does not modify system files directly, so read its contents and apply them yourself before use.

## 5-1. Sending faxes from a virtual printer (optional)
This is a CUPS backend that sends a printed document as a fax. Copy `deploy/cups/namifax-fax` to `/usr/lib/cups/backend/namifax-fax` (owner root, mode 0700),
and add a printer in CUPS with the device address `namifax-fax:/`. The printed content must contain a tag such as `[[FAX: 02-123-4567]]`, and the job is passed to
`sendfax` under the CUPS user name (without a tag it is saved only as a draft in the temporary folder, and if `sendfax` fails the failure is returned to CUPS). Verify: `echo "[[FAX: 123]]" | namifax print-in 1 사용자 제목 1 ""`.
**This repository has not been tested against a real CUPS and HylaFAX** (only the backend script's argument passing and the behavior of `namifax print-in` were tested).

## 6. File permissions

- The archive folders (`/var/spool/hylafax/archive`, `…/sent`) must be writable by both the user that runs the hooks and the web service user
  (running both as the same `uucp` is the simplest).
- The temporary folder (`AVANTFAX_TMPDIR`) is the same.
- Make `/etc/namifax.env` readable only by the service user (0640, owner `root:uucp`). systemd reads it as root, but cron and the hooks read it as `uucp`. It contains the DB password and the session key.

## 7. Post-install checklist

1. Log in, then check that Settings > System Log shows no errors.
2. Create a modem under Admin > Modems and check that its status shows `Running and idle` (it reads `faxstat`).
3. Send a test fax and check that the job appears in the outbox, and that after completion `notify` creates a sent fax in the archive.
4. Receive a test fax and check that `faxrcvd` puts it in the received-fax inbox (thumbnail, PDF, email notification).
5. Check that the HylaFAX version is displayed on the admin dashboard (`faxstat -i`).
