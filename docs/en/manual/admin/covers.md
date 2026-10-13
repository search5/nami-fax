# Cover pages

**Cover Pages** (`/admin/covers`, sidebar group *Content & Templates*) keeps the list of cover page templates that users can choose when they send a fax.

!!! warning "There is no file upload"
    The screen only **registers a file name**. It cannot upload a file, browse files, check that a file exists, or preview a cover page. Uploading is planned but not built; see the [cover upload plan](../../dev/cover-upload-plan.md). A service for storing templates exists in the code, but no screen calls it.

## What the screen does today

The list **Available Cover Pages** shows each registered cover page: **title**, **file** name in brackets and its ID. A new database contains three entries: *Generic A4* (`cover.ps`), *Generic Letter* (`cover-letter.ps`) and *Generic HTML* (`coverpage.html`).

| Action | How |
|---|---|
| Register | **New Cover Page**, fill in **Title** \* and **File** \* (the box suggests `custom.ps`), press **Save**. |
| Change | Click **Edit** on an entry. Both **Title** and **File** can be changed. **Save** keeps the new values (*The cover page was updated*). |
| Remove | Open the entry and press **Delete** (with a confirmation). |

- Both fields are required (*Title and File are required*).
- A file name that is already registered is refused (*Cover page already exists*).
- **Delete** only removes the registration from the list. The file itself is not touched.

## Putting the file in place

Because nothing is uploaded, you copy the template file to the server yourself. When a fax is sent with a cover page, NamiFAX looks for the file in the `images` folder under `AVANTFAX_INSTALLDIR` (default `/var/www/avantfax/images`). Register the file name exactly as it is in that folder. The screen does not check that the file is there; if it is missing, the cover page will not be produced correctly when the fax is sent.

Users pick a cover page in the Send Fax form and can set a default one in their account (**Select Cover Page** on the [Users](users.md) screen).

## Template formats

The cover generator reads:

- **PostScript** (`.ps`), and
- **HTML** (`.html`, `.htm`) only when the environment variable `USE_HTML_COVERPAGE` is `1` or `true`.

In a template, a placeholder is the text `XXXX-` followed by a name; every occurrence is replaced when the cover page is made, and an unknown name becomes empty. The names the generator fills in are:

`from`, `from-mail-address`, `to`, `to-company`, `to-location`, `to-voice-number`, `to-fax-number`, `regarding`, `from-company`, `from-location`, `from-voice-number`, `from-fax-number`, `page-count`, `todays-date` and `comments`.

For example `XXXX-to-company` becomes the recipient's company. The easiest way to make a new template is to copy `cover.ps` or `coverpage.html` from the NamiFAX `images` folder and edit it.

!!! note "The tag list on the screen"
    Below the form the screen shows a card **Cover Template Studio: Dynamic Tag References** that lists tags written like `@TO_COMPANY@`. The cover generator in the current code does **not** read that notation. Use the `XXXX-` names above.
