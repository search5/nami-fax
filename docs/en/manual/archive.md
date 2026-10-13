# Archive

The **Archive** (access key `a`) is where you search faxes you have archived from the [Inbox](inbox.md) and the faxes you have sent. The page title is **Archive Search**. Faxes still in the Inbox do not appear here. You can search the faxes your account is allowed to see (faxes you sent yourself, plus those on your permitted lines and categories); a superuser searches everything.

## Searching

When you first open the page, no search is run and the faxes of **today** are listed; the date selectors are also set to today. Leave filters empty to search all records; add criteria to narrow the results.

| Filter | Description |
|---|---|
| Company search | Type part of a company name; the **Company list** below follows what you type. |
| Company list | Pick a company to search only its faxes. |
| Fax ID | A single fax number (ID), matched exactly. |
| Keywords | Searched in the note (description) attached to the fax. If OCR is enabled on the server (`ENABLE_OCR_SUPPORT`) and the text of the fax has been stored, that text is searched as well. |
| Categories | **All Categories**, or one category your account may use. |
| User | Only shown to superuser accounts. Shows only faxes of one user. |
| Start Date / End Date | Each is a day, month and year selector; a blank entry means "not specified". |
| Direction | **Both sent and received faxes**, **Only sent faxes** or **Only received faxes**. |

After choosing the criteria click **Search**. **Reset** puts the filters back to their initial state.

### How dates work

- **Start Date** has to be given starting from the year. A year alone finds that whole year, year and month find that month, and with the day it finds that single day.
- If an **End Date** is given as well, the period from the start date to the end date is searched. An end date without a day runs to the end of that month, and one without month and day runs to the end of that year.
- An **End Date** on its own, without a start year, has no effect: no date condition is applied.
- If you added the archive to your browser's search box (browser "add search engine" feature), that search looks through all dates.

!!! note "OCR search"
    OCR only works when the administrator has switched it on in the server configuration. Faxes processed before that, or faxes whose text could not be read, cannot be found by content; they can only be found by their note (description).

## Results

Above the results "Total N results found." is shown; with more than one page the range (for example `1 - 25`) and page links with `‹` `›` appear at the bottom. The page size is set by **Archive Faxes Per Page** in [Account settings](account.md). If nothing matches, "No results were found" and a **Reset filters** link are shown.

Each row of the table, newest fax first, shows:

| Column | Content |
|---|---|
| # | Number of the result. |
| Thumbnail | First page. Hovering over the row shows a larger preview. |
| (action buttons) | See the table below. |
| Company | Company name and number, shown by the same rules as in the Inbox, so a link to name the sender or rename the company may appear (see "Naming the sender" in the [Inbox](inbox.md)). |
| Description | The note attached to the fax. |
| Pages | Number of pages. |
| Category | The assigned category. |
| Date | Archive or transmission time. |
| User | Only shown to superuser accounts. |
| (badge) | **Sent** for a sent fax, **Received** for a received one. Clicking it opens the **Transmission Report**. |

The action buttons are:

| Button | What it does |
|---|---|
| PDF | Downloads the fax as PDF. |
| Re-send | Opens [Send Fax](send-fax.md) with this fax attached as the original. |
| Email | E-mails the PDF (see "E-mailing a fax" in the [Inbox](inbox.md)). The fax is not in the Inbox, so the Category and Archive fields do not appear. |
| Note | Adds or changes the note (see "Notes" in the [Inbox](inbox.md)). |
| Delete | Only shown when you may delete faxes. Deletes the fax permanently after confirmation. |

## Transmission report

Clicking the badge at the end of a row opens the **Transmission Report**. It shows **Company:**, **Date:**, **Pages:**, **Fax Number:** and an image of the first page. Use **Print** to print it and **Close** to close the window.
