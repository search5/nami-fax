# HylaFAX operations notes

Things you run into during operation: moving the receive spool, housekeeping, the files one received fax creates, accepted attachment formats, and printing to fax. The installation order is in [HylaFAX integration install](hylafax.md).

!!! warning "Test scope"
    This repository has not been tested against a real HylaFAX or CUPS. The NamiFAX behaviour below was confirmed by reading the code; the HylaFAX behaviour itself (moving the spool, `faxqclean`) is ordinary HylaFAX practice. Verify on a test server before applying to production.

## 1. Moving the receive spool (`recvq`) to a larger disk

### HylaFAX side

`/var/spool/hylafax/recvq` is the temporary buffer where HylaFAX writes the TIFF while a fax is being received. Do not rename the folder through daemon settings; change only the physical storage at the operating-system level. Always stop HylaFAX while moving it.

Method 1, symbolic link:

```sh
service hylafax stop
mv /var/spool/hylafax/recvq /data/storage/fax_recvq
ln -s /data/storage/fax_recvq /var/spool/hylafax/recvq
chown -R uucp:uucp /data/storage/fax_recvq
service hylafax start
```

Method 2, bind mount (more robust). Add one line to `/etc/fstab`:

```
/data/storage/fax_recvq   /var/spool/hylafax/recvq   none   bind   0 0
```

### NamiFAX side

- NamiFAX does not read the `recvq` path itself. The receive hook (`faxrcvd`) simply uses the TIFF path HylaFAX passes as an argument, so after a link or mount **no NamiFAX setting needs to change.**
- The hook **copies** that TIFF into the archive folder. NamiFAX has no code that deletes the original in `recvq`. Every fax users see is the copy in the archive folder.
- To move the **archive folder** (where the copies accumulate) to a larger disk, set the path in `/etc/namifax.env`: `AVANTFAX_ARCHIVE` for received faxes (default `<HYLASPOOL>/archive`) and `ARCHIVE_SENT` for sent faxes (default `<HYLASPOOL>/sent`).
- The cloud retention policy and the local storage provider separately read `NAMIFAX_ARCHIVE_DIR` (default `/var/spool/hylafax/archive`). When you move the archive folder, **set `AVANTFAX_ARCHIVE` and `NAMIFAX_ARCHIVE_DIR` to the same value.**
- The archive folder must be writable by both the user that runs the hooks (`uucp`) and the web service user.

## 2. Housekeeping

Cleanup happens in three places, each with a different target.

| Target | Done by | Notes |
|---|---|---|
| HylaFAX spool (`recvq`, `doneq`, `docq`, `tmp`) | HylaFAX `faxqclean`, `faxcron` | NamiFAX does not touch it |
| NamiFAX archive and temporary folders | NamiFAX built-in scheduler or `namifax cron` | see below |
| Remote (S3) copies | storage policy | [Storage and scheduled tasks](../manual/admin/storage-scheduler.md) |

### HylaFAX side (`faxqclean`)

HylaFAX cleans finished jobs and document files that no job refers to any more with `faxqclean`, normally run from cron. Retention periods and how `recvq` is cleaned depend on your HylaFAX version and distribution setup, so check the `faxqclean(8)` and `faxcron(8)` manual pages. NamiFAX's `src/` and `deploy/` contain no code that handles `recvq` or `faxqclean`.

### NamiFAX side (`namifax cron`)

The built-in scheduler (it runs inside the web service, `NAMIFAX_ENABLE_SCHEDULER=1` by default) runs four tasks: `tmp` (clean the temporary folder), `inbox` (move old faxes out of the inbox, off by default), `lifecycle` (run the storage policy) and `phonebook` (export the phone book). Configure them under **Admin > Scheduled tasks**. If you do not want to use the scheduler, copy `deploy/cron.d/namifax` to `/etc/cron.d/namifax` and run `namifax cron` from cron.

| Option | Action |
|---|---|
| `-t days` | Delete files in the temporary folder (`AVANTFAX_TMPDIR`, default `/tmp/avantfax/`) older than the given days. **Required.** |
| `-i days` | Prune old faxes from the inbox (move to the archive) |
| `-d days` | Delete faxes older than the given days from the inbox/archive |
| `-p days` | Delete the original TIFF of faxes for which a PDF exists |
| `-s` | Run the policy saved on the Admin > Storage page (does nothing if none was saved) |

Without `-t` the command only prints its usage and does nothing, so also give `-t 2` (or similar) on lines that use `-i`/`-d`/`-p`/`-s`. Example:

```
0 0 * * *   uucp  sh -c 'set -a; [ -r /etc/namifax.env ] && . /etc/namifax.env; set +a; exec /opt/namifax/.venv/bin/namifax cron -t 2'
```

In `deploy/cron.d/namifax` only this `-t 2` line is enabled by default; the others (`-i 30 -d 365`, `-p 90`, `-s`) are commented out (those commented example lines lack `-t`, so add `-t 2` when you uncomment them). No scheduler task corresponds exactly to `-d`, so put it in cron if you want to delete by age. If nothing is enabled, faxes accumulate forever. See [Storage and scheduled tasks](../manual/admin/storage-scheduler.md) for the screens.

## 3. Files created per received fax

Whatever its page count, HylaFAX stores a fax received in one call as a single multi-page TIFF in `recvq` (`fax<number>.tif`, for example `fax00000042.tif`), and runs the `FaxRcvdCmd` hook (`faxrcvd`) when reception ends.

The hook creates this path in the archive folder:

```
<archive folder>/YYYY/MM/DD/<sender number>/<HylaFAX ID>/
```

- The date is the reception time reported by `faxinfo`.
- The sender number keeps only `+` and digits (the leading `+` is dropped); `unknown` if empty.
- The HylaFAX ID is the file name without `fax` and `.tif`, and **leading zeros are kept** (`00000042`).

Files created in that folder, in order:

| File | Description |
|---|---|
| `fax.tif` | Copy of the original TIFF. Recompressed to CCITT G4 when `TIFF_TO_G4` is on |
| `fax.pdf` | Converted with LibTIFF `tiff2pdf`, falling back to Pillow |
| `page0.png` ... `page<N-1>.png` | One image per page, numbered from 0. Grayscale, width `PREV_SP` (default 750) |
| `thumb.png` | Thumbnail of the first page. Width `PREV_TN` (default 80) |

The number of files is **3 + page count** (4 for 1 page, 8 for 5, 33 for 30, 103 for 100). With high daily volume the page images grow the file count and disk use quickly, so keep the cleanup settings (section 2) switched on. The optional features (`ENABLE_FAX_ANNOTATION`, OCR indexing, S3 upload) run after these files are created.

If `faxinfo` fails or the TIFF copy fails, the hook only logs and exits with code 0. HylaFAX sees that as success, so check that the fax actually appeared in the archive folder.

## 4. Accepted attachment formats and conversion

The upload type is decided from the **first 4096 bytes** of the file, not from its name.

| Format | Extension | Handling |
|---|---|---|
| PDF | `.pdf` | Accepted, passed to `sendfax` as is |
| PostScript | `.ps` | Accepted |
| TIFF | `.tif`, `.tiff` | Accepted |
| Text | `.txt` | Accepted (no NUL bytes and valid UTF-8). HylaFAX does the conversion |
| Pictures (PNG, JPEG), Word/Excel/PowerPoint/HWP | | **Rejected** (`File type is unauthorized`) |

- The size limit is `NAMIFAX_MAX_UPLOAD_BYTES` (default 10 MiB); larger files are rejected with `File size is over the limit`.
- NamiFAX does not convert uploaded files. Tell users to **save pictures and office documents as PDF** before uploading.
- The file picker on the Send page shows only `.pdf, .tif, .tiff, .ps, .txt`.
- Paper size, resolution and colour mode are not checked by the code. In general black-and-white or grayscale A4/Letter at 200-300 DPI is enough (fax is 204 DPI horizontally, 98/196 DPI vertically); large or colour documents lengthen the transmission and can blur the text.

## 5. Print to fax (CUPS)

What is implemented is the server-side path from a CUPS backend through `namifax print-in` to `sendfax`.

```
CUPS printer -> deploy/cups/namifax-fax -> namifax print-in -> (same path as the Send page) -> sendfax
```

Install it by section 5-1 of [HylaFAX integration install](hylafax.md): copy `deploy/cups/namifax-fax` to `/usr/lib/cups/backend/namifax-fax` (owner root, mode 0700) and add a CUPS printer with the device URI `namifax-fax:/`. The backend reads `/etc/namifax.env` and runs `${NAMIFAX_HOME:-/opt/namifax}/.venv/bin/namifax print-in`.

Behaviour:

- The printed content must contain a tag such as `[[FAX: 02-123-4567]]`. Only digits, `-`, `+`, parentheses and spaces are allowed in the number; matching is case-insensitive; if there are several tags **only the first** is used.
- With a tag, the job is passed to `sendfax` under the CUPS user name and queued. If NamiFAX has a user of that name, the user's name, company, phone and fax fill in the sender. Success gives `QUEUED`; failure gives `FAILED` (CLI exit code 1, the spool file is kept).
- Without a tag, the file is only saved under `namifax_drafts/` in the temporary folder and the result is `DRAFT` (exit code 0). No web page reads these drafts yet.
- The tag is found by reading the print data as text. In a measurement it **was found in PostScript input but not in PDF input**. Add the client printer with the "Generic / PostScript" driver.
- Check: `echo "[[FAX: 123]]" | namifax print-in 1 user title 1 ""`

!!! note "Not implemented"
    These appeared in the old design document but do not exist in this repository. Do not put them in operating procedures.

    - Upload of sent faxes to S3/GCS (only the S3 upload of received faxes and the storage policy exist)
    - HTTP webhook hooks (`/api/hooks/faxrcvd`) and `/api/sendfax` for client uploads
    - A Windows virtual port (RedMon/WPHFX), a macOS `osascript` backend, and Linux `fax4CUPS`/`zenity`/`kdialog` number-entry pop-ups
    - Extra tag syntax (`TO:`, `COVER:`), tag masking, and finding the tag through PDF text extraction/OCR
    - A web Outbox Drafts page and its notice banner
    - Automatic PDF conversion of images and office documents (LibreOffice and the like)

Related: [E-mail to fax](email-to-fax.md), [Operations checklist](operations-checklist.md)
