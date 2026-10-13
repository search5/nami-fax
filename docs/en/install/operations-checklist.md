# Pre-Production and Ongoing Operations Checklist

Items to check once before putting NamiFAX into production, and periodically while it runs. Behavior guaranteed by code is described in chapter 17 of `ARCHITECTURE.md` (deleted; restored from commit 01f2f64). This document collects only **what a person has to configure or decide**.

## 1. Before the first start (once)

| Item | How | Why |
|---|---|---|
| Wire up the environment file | Place `/etc/namifax.env` (one `KEY=value` per line, no quotes, no `export`, no trailing comments). The systemd service (`EnvironmentFile=-`), the cron lines (`sh -c 'set -a; . /etc/namifax.env; …'`) and the HylaFAX hook scripts (`set -a; . …`) all read the same file. | If the file is not passed along, `DATABASE_URL` is missing and the app silently falls back to a SQLite database (`namifax.db`) in the current folder. |
| Pin the session signing key | `session.secret` (ini) or the environment variable `NAMIFAX_SESSION_SECRET` | Without it, each process uses a random key and only logs a warning. With several workers or after a restart, the intermediate 2FA state and the login flow break. |
| Secure cookies on HTTPS | `session.secure = true` in the ini. The ini is read via `namifax serve --config <file.ini>` or the environment variable `NAMIFAX_INI` (starting with `pserve` also works). Without either option, no ini is read. | The default is false. `csrf.trusted_origins` and `secret.key` work the same way. |
| Credential encryption key | Set the environment variable `NAMIFAX_SECRET_KEY` (or ini `secret.key`) and run `namifax encrypt-secrets` once | Encrypts cloud keys, SMTP passwords and 2FA seeds at rest. **If you lose the key, the encrypted values cannot be recovered.** Keep it separately in a secret store. |
| First administrator | `namifax createuser -u <name> -e <mail>` (the password comes from `-p`, `NAMIFAX_NEW_USER_PASSWORD` or a prompt) | No demo account is created in a server DB (MySQL, MariaDB, PostgreSQL). There is no built-in default password either. |
| SMTP gateway | Configure it in the admin screen | **Forgot password**, forwarding of received faxes by mail, and notification mails all use this setting. If mail cannot be sent, forgot password shows "Email failed to send" and leaves the existing password unchanged. |
| Turn off demo data | Do not enable `NAMIFAX_DEMO_DATA` | It is an opt-in that works only on SQLite. SQLite is not a production DB. |
| Periodic jobs | The built-in scheduler (`/admin/scheduler`) runs four jobs: temp folder cleanup (`tmp`), moving received faxes to the archive (`inbox`, off by default), running the retention policy (`lifecycle`) and phonebook export (`phonebook`). | There is no job that exactly corresponds to `cron -d`, which deletes old archived faxes by date. If you need it, add it to `deploy/cron.d/namifax`. |
| Password hash | Argon2id by default. While sharing one DB with the original PHP, use `NAMIFAX_PASSWORD_HASH=md5` | The original cannot read Argon2id ([migration.md](migration.md) 4.5). |

### SAML login and permissions

- In Admin > SAML, save the IdP address and certificate and turn the feature on. Until it is configured, no button appears on the login screen. Only responses **signed** by the IdP are accepted (signature algorithm SHA-256 or stronger).
- If "Take permissions from the IdP" is on, each login determines administrator, superuser, delete and any-line permissions from the role attribute in the response (`Role` by default). Line, category and DID routing entries are managed only for items whose attribute name is listed; names in the list that do not exist in namifax are ignored. If a role is removed, the permission is removed at the next login, and values changed by hand here are overwritten.
- In Keycloak, use client mappers to put `Role` (a role list, multi-valued) and a user attribute such as `modems` (multi-valued) into the response. User attributes are stored only if "unmanaged attributes" is enabled in the realm.
- Login, rejection of forged and replayed responses, granting and revoking roles, and reflection of line attributes were verified against a real Keycloak 26 container. Integration with other IdPs such as Okta and Entra ID has not been tested.

## 2. HylaFAX integration (verifiable only on a real server)

Tests confirm that the same command line as the original `submit_fax()` is built, but **the connection to a real HylaFAX has not been verified in this repository.**

- `sendfax` must be on `PATH`. If it is missing, sending is marked as failed in an environment where `NAMIFAX_QUEUE_SIMULATION` is off (it is simulated if that variable is on or `/var/spool/hylafax` does not exist).
- Cover page: the cover file must exist at `AVANTFAX_INSTALLDIR/images/<cover file>`, and the executable is `NAMIFAX_FAXCOVER` (default `python -m namifax.cli.faxcover`).
- `DEFAULT_TSI_ID`, `ENABLE_DID_ROUTING` (the receive hook and the web app must use the same value), `AVANTFAX_ARCHIVE`, `AVANTFAX_TMPDIR`.
- After the first send, check that the job appears in the outbox, and that `request id is N` in the `sendfax` output is read as the job number.
- When only a cover page is sent, check that the temporary `.ps` file is removed after sending (`AVANTFAX_TMPDIR` or the system temp folder).

## 3. When migrating from an existing AvantFAX

The full procedure, the settings mapping table, redirects for old URLs on the web server and the dry-run results are in [migration.md](migration.md). Only the key points are repeated below.

- It attaches directly to the original MySQL/MariaDB DB (`ARCHITECTURE.md` (deleted; restored from commit 01f2f64) 17.5a). A large `FaxArchive` table **may take a long time on the first start because the search index is built.** The duration has not been measured, so do the first start during a maintenance window.
- **PHP sessions and login cookies do not carry over.** All users must log in again right after the switch.
- The migration rehearsal tool `tools/migration_rehearsal/` remains in the repository, but it does not run until you restore `legacy/` with `git checkout 9408385 -- legacy`.
- Back up the original DB before the first start (the schema is adjusted).
- SQLite files created by earlier versions of the port are adjusted at startup, but those from very early versions are only partly adjusted. If it is not production data, delete it and create a new one.
- Import existing archived fax files with `namifax import-archive`. Import users with `namifax import-users`.

## 4. Items that need a security judgement

### Forgot password (original `forgot.php` behavior)
As in the original, **a new temporary password is generated for the given email address and sent by mail, and that password must be changed at the next login.** It keeps the original's characteristics, so you should be aware of them.

- Anyone who knows another person's email address can **invalidate that account's existing password** (this is not account takeover, because the temporary password goes to the owner's mailbox, but it can disrupt their login). To prevent this, rate-limit `/forgot` at the front end (reverse proxy).
- Entering a non-existent address returns "no such user" (original behavior). This exposes whether an account exists.
- Differences from the original: the new password is **not written to the system log** (the original logged it in plain text). If sending the mail fails, the **existing password is restored** (in the original the account stayed locked). Deleted accounts are not looked up.
- An account with two-step verification enabled is still asked for the verification code even when logging in with the temporary password.

### Known limitations (not fixed)
- SAML login does not go through the app's 2FA. It is a **settled policy** that the IdP is responsible for two-step verification.
- The permission rules of the original archive search and the received-fax inbox were checked for agreement by actually running the original. However, editing a queued job (`/ajax/faxalter`) only checks that the user is logged in, as the original does.

## 5. Periodic checks during operation

- Check the system log now and then for `Access denied to … fax` (attempts to access without permission) and `Attempt to reset password for email` (failed forgot-password attempts).
- TOTP locks for a period after 5 failures. For a user who has lost both the device and the recovery codes, unlock with `namifax reset-2fa <user>`.
- Faxes of a modem deleted from the settings are, as in the original, **not shown in the received-fax inbox** (superusers included). Empty or archive the received-fax inbox before deleting a modem.
- To rotate the key, work while the values can still be read with the existing key, before switching to the new `NAMIFAX_SECRET_KEY` (if the key is lost, recovery is impossible).

## 6. Not done yet

- The outbox was aligned to the same columns and buttons as the original, but it was checked **only against fake `faxstat` output**. The real HylaFAX job list format (`JobFmt` must include a `Mailaddr` column) and the owner-permission behavior of `faxrm` and `faxalter` must be verified on a server that has HylaFAX. The web server user and the faxmail user name are set with the environment variables `WWWUSER` (default `www-data`; the original default is `apache`) and `FAXMAILUSER` (default `faxmail`). If a HylaFAX job owner has one of these names, the user is looked up by mail address.
