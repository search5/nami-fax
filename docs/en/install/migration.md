# Migrating from AvantFAX 3.x to NamiFAX

This document describes how to move an existing AvantFAX 3.x installation (3.0 to 3.3.5, MySQL/MariaDB) to NamiFAX, and what looks different afterwards.
AvantFAX 2.x is not supported (only databases from 3.x onward).

## 1. At a glance

| Question | Answer |
|---|---|
| Can the existing DB be used as is? | **Yes.** NamiFAX attaches to the same DB and fax archive folder. Users, modems, categories, routing, the address book, distribution lists, and archived faxes are all preserved. |
| What about passwords? | Users log in with the original MD5 hash as is. Nobody needs to be issued a new password. **When a login succeeds, that account's hash is rewritten as Argon2id** (see 4.5 below). |
| Can it be rolled back? | Conditionally, yes. The port only adds to the DB and never deletes or modifies existing data (see chapter 4 below), so the original PHP app can keep using the same DB. However, **an account that has logged in on the port or changed its password now has an Argon2id hash, which the original cannot read.** If both programs must run side by side, keep `NAMIFAX_PASSWORD_HASH=md5` enabled (4.3). |
| What looks different? | Previews of existing faxes are regenerated (4.2), old URLs, and every user must log in again. Characters the original stored as HTML entities are decoded for display, so they look the same (4.1). |
| What has not been verified? | Integration with a real HylaFAX server, and first-startup time on a large archive spanning several years. |

## 2. What the rehearsal verified

"The DB can be used as is" was verified with **data actually produced by the original PHP app**, not with synthetic test data.
`tools/migration_rehearsal/run.sh` reproduces this from scratch (`tools/migration_rehearsal/` has not been deleted, but it needs the original PHP source (`legacy/`) to run, so **restore it first with `git checkout 9408385 -- legacy`.** It will not run until that is done. Docker and network access are required; it takes about 15 seconds if the images are already present).

1. Run the original AvantFAX 3.3.5 on PHP 5.6 + MDB2 2.4.1 + MariaDB 10.3 (non-strict SQL mode, as around 2013).
2. Through the original's web screens, create 3 users, 2 modems, 3 categories, an address book, and an email address book, then record 6 faxes (2 of them archived) with the original's `ArchiveIn::create()`.
3. Connect NamiFAX to the same DB and fax folder and compare it with the original.

| Item checked | Result |
|---|---|
| Logins of the three users created by the original, and the administrator | All succeeded. The administrator's old password was correctly rejected |
| Per-user inbox list | **Same** as the original (including line and category restrictions) |
| Whether each user can open each fax's PDF (including archived faxes) | **Same** as the original |
| Fax thumbnails and page images | Served (generated fresh on first view, 4.2) |
| NamiFAX reading address book and email contacts written by the original | Read correctly; entities are decoded and appear as characters (4.1) |
| The original reading contacts written by NamiFAX | Works (including Korean and accented characters) |
| The original app after NamiFAX has used the DB | Login, inbox, address book, archive, settings, and outbox all work |

The test environment was 3.3.5 only. For installations that went through repeated upgrades from 3.0 to 3.2.x, `tests/unit/test_legacy_database_compat.py` checks against the
3.2.0 schema (MySQL 8.4, MariaDB), but this has not been tested with a DB that has a real upgrade history.

## 3. Migration procedure

1. **Back up.** Back up the DB (`mysqldump`) and the fax archive folder. Schema adjustments will take place.
2. **Configure.** Move the values in `local_config.php` to environment variables using the mapping table in chapter 5 below. At a minimum the following are required.
   - `DATABASE_URL` = `mysql+pymysql://user:password@host/avantfax` (the original's `AFDB_*` values)
   - `AVANTFAX_INSTALLDIR` = the original installation directory (e.g. `/var/www/avantfax`). This is the base used to resolve the fax paths stored in the DB as relative paths.
   - `AVANTFAX_ARCHIVE` = the received-fax archive folder (the original's `$ARCHIVE`, default `<installation directory>/faxes/recvd`)
   - `NAMIFAX_SESSION_SECRET`, `NAMIFAX_SECRET_KEY` (chapter 1 of [operations-checklist.md](operations-checklist.md))
3. **Start.** On first startup NamiFAX creates the new tables and indexes. A large `FaxArchive` may take a long time because of index creation.
4. **Log in.** All users must log in again (PHP sessions are not carried over). Accounts in the `wasreset` state change their password at first login.
5. **HylaFAX and cron.** Replace the original's PHP hooks and cron jobs with NamiFAX commands. See [hylafax.md](hylafax.md), `deploy/hylafax/` (hook scripts and config fragments), and `deploy/cron.d/namifax`.
6. **Web server.** Add rules that redirect old URLs to the new ones (chapter 6).
7. **SMTP.** Re-enter it in the SMTP settings of the admin screen (the original's `SMTP_*` variables are not read).

You may run the original PHP app alongside for a while (same DB). Note, however, that this side-by-side operation has only been verified within the read and write scope of the rehearsal above.

## 4. Differences and limitations

### 4.1 Characters the original stored as HTML entities

The original **stored text such as names as HTML entities** (every form value was passed through `htmlentities(ENT_QUOTES, "UTF-8")`). In the rehearsal, the values the original produced were as follows.

| Input | Value stored in the DB |
|---|---|
| Müller & Söhne GmbH | `M&uuml;ller &amp; S&ouml;hne GmbH` |
| Soporte Línea | `Soporte L&iacute;nea` |
| O'Brien "Bob" | `O&#039;Brien &quot;Bob&quot;` |

The original printed values into HTML as is, and the browser rendered them as characters. NamiFAX **decodes the entities when reading** and shows the same characters
(`LegacyHtmlString` and `LegacyHtmlText` in `models/types.py`). The DB is not touched, so rollback is unaffected.
Values that NamiFAX writes anew are plain UTF-8 and also display correctly in the original app.

- What is decoded for display is text that people type in (names, company names, descriptions, aliases, signatures, fax memos, and so on). Paths, numbers, and logs are left as they are.
- Search compares both the word as typed and the form the original would have stored (`müller` finds `M&uuml;ller`). It is case-insensitive.
- If you save without changing a value, the original value (the entity) stays in the DB; a value you change is stored as plain UTF-8.
- This is safe. Decoded characters are escaped again when output to the screen, so even if `&lt;script&gt;` is stored it does not run as a script.

**Limitations**

- Values the original **double-encoded and corrupted** are not restored. In the rehearsal, Korean text written into the user name field was stored corrupted as `ÃªÂ¹â‚¬`, and it also looked corrupted on the original's screen.
  Such values must be re-entered once in the admin screen.
- If a user typed something shaped like an entity, such as `&uuml;`, **literally as text**, it is decoded and shown as `ü`. This is rare.
- Duplicate checks on names (for example category names) compare stored values with each other, so if the original stored `Vertrieb M&uuml;ller` as an entity and you then create `Vertrieb Müller`, it may not be caught as a duplicate (this is an inference and has not been tested).
- The rehearsal only looked at the behavior of PHP 5.6. A DB written by an older PHP may be stored differently (for example, double encoding based on ISO-8859-1).

`tools/migration_rehearsal/check_text.py --strict` (this too is run after restoring `legacy/`) checks this against real data produced by the original.

### 4.2 Previews of existing faxes

The `thumb.gif` and `prev*.gif` files created by the original are not used. On first view, NamiFAX creates `thumb.png` and `page*.png` anew with Ghostscript **inside the fax folder**
(the original files are left as they are). The web server user must therefore be able to write to the fax folder, and Ghostscript must be installed.
The first archive screen converts up to one page's worth (30 items by default) at once. To pre-generate them, use `namifax create-thumbnails`.

### 4.3 What NamiFAX adds to the DB (no effect on the original PHP app)

- 5 new tables: `SystemConfig`, `SystemSettings`, `NetworkPrinters`, `UserTOTP`, `UserWebAuthnCredentials` (and `alembic_version`). OCR text is stored only in `FaxArchive.faxcontent`, as in the original (the `FaxOCR` table that revision `0019` used to create is dropped by `0027`)
- 12 search indexes
- 10 columns added to `AddressBook`, and `UserAccount.last_ip` widened from 15 to 45 characters (IPv6)
- Existing rows are not deleted or modified. The default categories and cover pages are not added to an existing DB.

### 4.4 Other differences

- The password length is 8 to 15 characters, the same as the original (changeable with `MIN_PASSWD_SIZE` and `MAX_PASSWD_SIZE`).
- The UI is newly built with Tailwind CSS. The original's themes and `custom.css` are not supported.
- Dialogs are pages rather than separate windows. Requests that change state (delete, archive, and so on) require POST and a CSRF token, so the way external scripts called the original's `ajax/*.php?fid=…` with GET does not work.
- Dates in the inbox and archive are shown in a fixed format (there is no equivalent of the original's `ARCHIVE_DATE_FORMAT` setting).
- Translations other than Korean are partial. Of 695 strings, the number that appear translated in non-Korean locales is 292 to 333 (about 42 to 47%), and the rest are in English. For strings with the same meaning as in the original, the original's English source was used and the original's translations were imported. The rest are UI strings newly written for NamiFAX, so the original has no translations for them. (The `tools/i18n_import_legacy.py` used for the import has been deleted.)

### 4.5 Password hash (Argon2id)

- The port stores passwords as **Argon2id** (salted; the cost is adjustable with `NAMIFAX_ARGON2_TIME_COST`, `_MEMORY_COST`, and `_PARALLELISM`).
  The original's MD5 (32 characters) is still accepted, and **at the moment that account logs in to the port** it is converted to Argon2id. Accounts that have not logged in stay as MD5.
- Migration 0026 widens `UserAccount.password` and `UserPasswords.pwdhash` to 255 characters (the original has `VARCHAR(32)`).
- **The original PHP app cannot read Argon2id.** An account that has logged in on the port cannot log in if you return to the original, and has to obtain a new password through password recovery.
- While you run the two programs side by side or want to keep the option of rolling back, set `NAMIFAX_PASSWORD_HASH=md5`. New passwords are then also written in the original format and no upgrade takes place.
  Once the switch is final, simply remove this setting (from the next login onward, hashes are converted to Argon2id).

## 5. `local_config.php` setting mapping table

The original's `local_config.php` is not read. Specify the same names as **environment variables** (with systemd, `Environment=` or `EnvironmentFile=`).
For on/off values, `1` or `true` means on (do not use PHP's `true`/`false` as is). If unspecified, the default applies; most defaults were matched to the original, but some differ (the per-variable differences were in E6 and E7 of `git show 61c3663:docs/PORTING_GAPS.md`).

### 5.1 Specified under the same name

| Category | Variables (defaults as verified, in parentheses) |
|---|---|
| UI behavior | `SHOW_ALL_CONTACTS` (on), `RESTRICTED_USER_MODE`, `INBOX_LIST_MODEM`, `FOCUS_ON_NEW_FAX`, `FOCUS_ON_NEW_FAX_POPUP`, `SENDFAX_USE_COVERPAGE` (on), `SENDFAX_REQUEUE_EMAIL` (on), `ENABLE_DL_TIFF`, `SHOWSERVER_DETAILS`, `WHITEPAGES` |
| Page size and length limits | `DEFAULT_FAXES_PER_PAGE_INBOX` (25), `DEFAULT_FAXES_PER_PAGE_ARCHIVE` (30), `MAX_USERNAME_SIZE` (15), `MAX_PASSWD_SIZE` (15), `MIN_PASSWD_SIZE` (8), `MAX_EMAIL_SIZE` (99) |
| Routing and recognition | `ENABLE_DID_ROUTING`, `AUTOCONFDID`, `ENABLE_BARDECODE_SUPPORT`, `BARDECODE_BINARY`, `BARDECODE_COMMAND`, `ENABLE_OCR_SUPPORT`, `OCR_BINARY`, `OCR_COMMAND`, `OCR_LANGUAGE`, `CALLIDN_CIDNUMBER`, `CALLIDN_CIDNAME`, `CALLIDN_DIDNUM` |
| Receiving and notification | `ARCHIVEFAX2EMAIL`, `FAXRCVD_INCLUDE_PDF`, `FAXRCVD_INCLUDE_THUMBNAIL`, `FAXRCVD_PRINT_PDF`, `NOTIFY_INCLUDE_PDF`, `NOTIFY_ON_SUCCESS`, `PRINTFAXRCVD`, `PRINTERNAME`, `PRINTCMD`, `PRINTFAX2PS`, `PDFPRINTCMD`, `TIFF_TO_G4`, `ENABLE_FAX_ANNOTATION`, `ANN_GRAVITY` |
| Cover pages and sending | `COVERPAGE_FILE`, `COVERPAGE_MATCH`, `USE_HTML_COVERPAGE`, `NUM_PAGES_FOLLOW`, `CPAGE_LINELEN`, `FAXCOVER_DATE_FORMAT`, `EMAIL_DATE_FORMAT`, `EMAIL_ENCODING_TEXT`, `EMAIL_ENCODING_HTML`, `EMAIL_ENCODING_CHARSET`, `FROM_COMPANY`, `FROM_LOCATION`, `FROM_VOICENUMBER`, `FROM_FAXNUMBER`, `DEFAULT_TSI_ID` |
| Conversion | `PAPERSIZE` (a4), `DPI` (200), `PREV_TN` (80), `PREV_SP` (750) |
| Paths and executables | `HYLASPOOL`, `HYLAFAX_PREFIX`, `BINARYDIR` (also specifiable per tool name: `SENDFAX`, `FAXSTAT`, and so on), `PHONEBOOK`, `ARCHIVE_SENT`, `WWWUSER` (the original used `apache`; the port defaults to Debian's `www-data`), `SUDO` |
| Authentication | `ALTERNATE_AUTH_ENABLE`, `ALTERNATE_AUTH_CLASS`, `ALTERNATE_AUTH_FALLBACK`, `WEBSERVER_AUTH`, `PWAUTHPATH` |

The date format syntax differs. The original's `ARCHIVE_DATE_FORMAT` uses MySQL format (`%i` is minutes), whereas NamiFAX's `EMAIL_DATE_FORMAT` and `FAXCOVER_DATE_FORMAT` use Python format (`%M` is minutes). Do not carry the value over as is.

### 5.2 Renamed or configured elsewhere

| Original | NamiFAX |
|---|---|
| `AFDB_ENGINE`, `AFDB_HOST`, `AFDB_USER`, `AFDB_PASS`, `AFDB_NAME` | `DATABASE_URL` (e.g. `mysql+pymysql://user:pw@host/avantfax`) |
| `$INSTALLDIR`, `$ARCHIVE`, `$TMPDIR` | `AVANTFAX_INSTALLDIR`, `AVANTFAX_ARCHIVE`, `AVANTFAX_TMPDIR` |
| `$RESERVED_FAX_NUM` | `AVANTFAX_RESERVED_FAX_NUM` |
| `$AVANTFAX_SERVERNAME` | `AVANTFAX_SERVERNAME` |
| `SF_MAXSIZE`, `SF_FILESIZE` (upload size) | `NAMIFAX_MAX_UPLOAD_BYTES` (in bytes) |
| `USE_SMTPSERVER`, `SMTP_SERVER`, `SMTP_PORT`, `SMTP_AUTH`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SYSTEM_EMAIL_SIG_TEXT`, `SYSTEM_EMAIL_SIG_HTML` | **SMTP settings in the admin screen** (stored in the DB; the password is encrypted with `NAMIFAX_SECRET_KEY`) |

### 5.3 Not needed

- Themes and plugins: `ADMINTHEME_DIR`, `ADMIN_THEME_PATH`, `USERTHEME_DIR`, `USER_THEME_PATH`, `PLUGINS_DIR`, `PLUGINS_PATH`, `ARCHIVE_WIDE`, `NOTHUMBIMG`
- Conversion tools: `CONVERT`, `TIFFCP`, `TIFFCPG4`, `TIFFPS`, `TIFFSPLIT`, `GSR`, `GSN`, `GSN2`, `GSTIFF`, `GSCMD`, `PNMSCALE`, `PNMDEPTH`, `PPMTOGIF`, `PNMQUANT`, `PSRESIZE`, `DPIS`, `HYLATIFF2PS` (replaced by Ghostscript, Pillow, and others; see section G of `git show 61c3663:docs/PORTING_GAPS.md`)
- PHP environment: `HAS_MIME_FUNCTION`, `HAS_FILEINFO`, `HAS_NEGATIVE_TIFF`, `AVANTFAX_DEBUG`, `AVANTFAX_VERSION`, `USERSESSION`
- Used only for UI text: `CONTACTFILETYPES`, `SENDFAXFILETYPES`, `SYSTEM_IP` (the address in new-user emails uses the request address)

## 6. Redirecting old URLs to new URLs at the web server

To keep bookmarks and external links from breaking, configure permanent redirects (301) **in the web server**. This is the web server's job rather than the application's, so it was not put into the NamiFAX code.
The rules are in `deploy/legacy-redirects/`, and 17 URLs were tested against real servers for both Apache and nginx.

- Apache: `Include` `apache.conf` inside the `<VirtualHost>` of `deploy/apache/namifax.conf`, before `ProxyPass` (`mod_rewrite` is required).
- nginx: `include` `nginx.conf` inside the `server` block, before `location /`.

| Old URL | New URL |
|---|---|
| `/inbox.php?pageindex=2` | `/inbox?pageindex=2` (the query string is preserved) |
| `/index.php` | `/login` |
| `/addressbook_edit.php?abook_id=5` | `/addressbook/edit?abook_id=5` |
| `/pdf.php?fid=12` | `/faxes/download/12?format=pdf` |
| `/refax.php?fid=12` | `/sendfax?refax=12` |
| `/admin/conf_modems_edit.php?devid=1` | `/admin/modems?devid=1` |
| `/admin/users.php?uid=4` | `/admin/users?uid=4` |

Only screens that people open are covered. The original's `ajax/*.php` and `file.php` are URLs that the screens call by themselves, so they are not in the rules.
`tests/unit/test_legacy_redirects.py` checks that the rules' destination URLs actually exist in the app.

## 7. What to tell users

- They must log in again once, the first time.
- The look of the screens and the dialogs has changed. The features and permission rules are the same.
- Password recovery, two-factor authentication (TOTP), and passkeys are new features.
