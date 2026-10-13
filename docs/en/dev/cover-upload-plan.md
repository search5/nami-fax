# Fax Cover Page Upload Plan

This is a plan for letting administrators upload cover page files on the `/admin/covers` screen and browse the files already uploaded to pick one.
This document is a plan; nothing has been implemented yet. The "Confirmed current state" below was verified on 2026-10-03 by reading the code and the original (`git show 9408385:legacy/avantfax/...`).

## 1. Background

The new-features plan (`llm-wiki/sources/new-features-plan.md` §3.5) promised a cover page studio with "drag-and-drop upload, live thumbnail preview, guidance on dynamic substitution variables, and PostScript, HTML and PDF support".
Currently, however, only the service code exists and it is not connected to any screen. This plan also corrects the "Cover page studio" line in §3 of the wiki's `known-gaps-and-decisions.md`, which lists this state only as "code exists" and so reads as if the work were finished.

## 2. Confirmed current state

| Item | Original AvantFAX 3.x | Current NamiFAX |
| --- | --- | --- |
| File upload | None. Files are copied directly on the server | Not on the screen |
| Screen input | Title, file name (typed text), hidden fields `cover_id`, `_submit_check` | Same |
| File existence check | Not done | Not done |
| Duplicate registration | Rejected with "Cover page already exists" if the file name is the same | Same (`Covers.create`) |
| Editing after saving | Only the title changes (the file name does not) | The file name changes too (difference) |
| Location read when sending | `$INSTALLDIR/images/<file>` | `AVANTFAX_INSTALLDIR/images/<file>` (`views/sendfax.py`, `services/sendfax_command.py`) |
| Service `CoverStudioService` | None | Accepts `.ps`, `.pdf`, `.html`, `.jinja2`, stores and registers them. **Nothing calls it** |
| Service default storage location | N/A | `/var/spool/hylafax/covers` (**differs from the location the send path reads**) |
| Formats the cover generator uses | N/A | `.ps`, `.html`/`.htm` (`.html` requires `USE_HTML_COVERPAGE` to be on) |
| Upload size limit | N/A | None for covers (there are `NAMIFAX_MAX_UPLOAD_BYTES` and `services/upload_check.py` for attachments) |

For this reason, wiring `CoverStudioService` up as it is now would cause two problems.
1. An uploaded cover page would appear in the list, but the file would not be found when sending (the storage location differs).
2. `.pdf` and `.jinja2` could be uploaded, but the cover generator cannot use them.

## 3. Goals and scope

Goals
1. A cover page file can be uploaded in both the add-new-cover mode and the edit mode.
2. Cover page files that were already uploaded can be browsed and picked from a list.
3. An uploaded cover page is actually used when sending.
4. The original's form contract and behavior (title and file name required, duplicate registration rejected) are not broken.

Out of scope (separate work)
- Thumbnail preview: the `.ps` conversion method (Ghostscript, etc.) has to be decided first, so it is handled separately.
- `.pdf` and `.jinja2` cover pages: the cover generator has no support for these formats, so they are excluded from this work.
- Deleting cover page files: unregistering and deleting the file are different operations, so this work keeps only unregistering.

## 4. Decisions

These are items the user must settle. Until they are settled, the plan follows the recommendation.

| # | Question | Recommendation | Status |
| --- | --- | --- | --- |
| D1 | When a file with the same name already exists | Reject by default, and allow only when "overwrite" is checked. Overwriting changes the sending results of other cover pages that use the same file | [NEEDS_CLARIFICATION: reject only, or add an overwrite checkbox] |
| D2 | Allowed upload formats | `.ps`, `.html` (including `.htm`). Same as the formats the generator uses | [NEEDS_CLARIFICATION: whether narrowing to these two formats is agreed] |
| D3 | Changing the file name on the edit screen | As in the original, change only the title, and make choosing the file a separate action through browsing or uploading. Whether to keep the current file-name-change behavior has to be decided | [NEEDS_CLARIFICATION: whether to keep the file name change] |

D3 is a difference from the original, so until it is decided the current behavior (the file name also changes) is kept, and once decided it is changed together with its tests.

## 5. Design

### 5.1 Form contract

The original inputs `title`, `file`, `cover_id`, `_submit_check` and the buttons `create`, `save`, `delete` are left as they are.
All added elements are optional features.
- File selection input `cover_upload` (`enctype="multipart/form-data"`). After uploading, the `file` field is filled with the uploaded file name.
- Overwrite checkbox `overwrite` (per the D1 decision).
- A browse list. Choosing an entry fills the name into the `file` field (without scripting, the name can still be typed directly into the `file` field).
- Form token `csrf_token`.

The existing request format (a request sending only `title` and `file`) must keep working.

### 5.2 Storage location and service

- The storage location is unified to `AVANTFAX_INSTALLDIR/images`, which the send path reads. The `CoverStudioService` default `/var/spool/hylafax/covers` is changed to this value, and the environment variable `AVANTFAX_COVERS_DIR` is either no longer used or cleaned up to point to the same folder.
- The service `save_template` keeps the flow of checking the format, then saving and registering, and adds the following.
  - File name checks: path separators are forbidden (in addition to `os.path.basename`, reject if the name changes), hidden files are forbidden, allowed characters are restricted
  - Size limit: a cover-specific setting (default smaller than the attachment limit)
  - Content check: a `.ps` must start with `%!PS`, and an `.html` must be text
  - Same-name handling (D1)
  - If the same file name is already registered in `CoverPages`, reject with "Cover page already exists" as in the original
- A write failure (no permission on the folder) is reported on an error screen. The deployment documentation states that the `images` folder must be writable by the web server user.

### 5.3 Browsing

- Only files of the allowed formats in the same folder are listed, sorted by name. No path is accepted; only file names are handled.
- Next to each file, the cover page (title) that uses it is shown, and unregistered files are marked "not registered".
- Other folders and parent paths cannot be viewed.

### 5.4 Screen

- Both the add-new-cover and the edit modes show upload and browsing.
- Tailwind utilities follow the tone of the existing screens, and drag-and-drop works only when scripting is available (without scripting, a file can still be uploaded by file selection).
- New strings are added together to the Korean catalog `ko/namifax.po`. The other language catalogs are not touched in this work (a full refresh would produce a large number of changes).

## 6. Implementation order

Within each step, write the tests first, confirm they pass, then move to the next step.

1. Service: unify the storage location, file name checks, size limit, content check, duplicate handling
2. View: wire upload handling into `/admin/covers` (`cover_upload`, form token, permissions)
3. Browse list and the screen form
4. Verify the send connection: test that a real send plan is built with an uploaded cover page
5. Documentation: folder permission notes in the deployment documentation, wiki update

## 7. Test plan

Service
- Allowed formats are saved and registered in `CoverPages`
- Disallowed extensions, files whose content differs from the format, and files over the size limit are rejected
- Names containing paths (`../x.ps`, `a/b.ps`, `.hidden.ps`) are rejected
- Same name: rejected by default, allowed when overwrite is on (D1)
- An already registered file name is rejected with the original's wording

View
- Upload works in both the new-cover and edit modes, and the `file` field is filled
- A request without the form token is rejected
- A non-administrator cannot upload
- The existing way of sending only `title` and `file` keeps working
- The browse list shows only files of allowed formats and shows no files outside the folder

Send connection
- The name of the uploaded cover page appears in the send screen's list, and the cover path in the send plan points to the uploaded file

Server DB tests: this feature does not use the DB in any new way, so SQLite tests are considered sufficient. However, registration in `CoverPages` uses existing queries, so the full test suite is run once on the 4 DBs to confirm.

## 8. Completion criteria

- All the tests above pass, and the full test suite (SQLite) shows no new failures.
- The uploaded cover page appears on the send screen and is reflected in the send plan.
- The wiki (`known-gaps-and-decisions.md`, the passages related to `new-features-plan`, and `log.md`) is updated to the actual state. PDF, Jinja2 and thumbnails are recorded as "not implemented".

## 9. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| The `images` folder is not writable by the web server user | Report write failures as a screen error and document the permissions in the deployment documentation |
| Overwriting a same-named file changes the results of other cover pages | Reject by default (D1); when overwriting, show the list of cover pages in use as a warning |
| Scripts inside an uploaded HTML | The cover page is only converted on the server and is never rendered directly on screen, so the screen risk is low, but confirm before implementation whether the conversion tool reads external resources |
| `.html` is not used when `USE_HTML_COVERPAGE` is off | Show the setting state on the upload screen and pin the behavior when it is off with a test |
| File name change behavior that differs from the original | Handle after the D3 decision, and keep the current behavior until then |

## 10. What has not been verified

- How the HTML cover page conversion tool (`html2ps`) reads external resources has not been checked.
- A send through a real HylaFAX `faxcover` cannot be tested in the current environment, so the send connection is verified only up to the send plan (command construction).
- The owner and permissions of the `images` folder in an actual deployment environment have not been checked.
