# Inbox

The **Inbox** (access key `i`) lists received faxes, newest first. Only faxes on the lines and in the categories your account is allowed to use are shown.

## The list

The top of the page has a badge with the number of faxes ("N Faxes") and a **Send Fax** button. When there are faxes, a batch-action row and a table follow.

| Column | Content |
|---|---|
| (check box) | Select the fax for a batch action. |
| Preview | Thumbnail of the first page. Click it to open the fax viewer. |
| Sender | Company name (found in the address book) or the sending number. The number and any note are shown underneath. |
| Received | Date and time of receipt. The line name is shown below it when there is one. |
| Pages | Number of pages. |
| Actions | **View**, **PDF**, **Reply** and a `···` menu. |

The `···` menu contains:

| Item | What it does |
|---|---|
| Archive | Moves the fax from the Inbox to the Archive. |
| Email Fax | E-mails the fax as a PDF attachment. See "E-mailing a fax" below. |
| Add a note | Attaches a note to the fax. See "Notes" below. |
| Rotate | Rotates the fax by 90 degrees. |
| Download TIFF | Only shown when TIFF download is switched on for the server. |
| Delete | Only shown when your account may delete faxes. |

### Paging and list size

- Below the list you see a range such as "1 - 25 (N faxes)" and, when there is more than one page, numbered page links with `‹` and `›` for previous and next.
- The number of faxes per page is set by **Faxes Per Page** in [Account settings](account.md) (10, 15, 20, 25, 30, 50, 100). If you have not set it, the server default is used. Appending `?pagelimit=N` to the address changes the size for that request only; values below 10 are treated as 10.
- The Inbox has no search box or filter. To find faxes by criteria use the [Archive](archive.md).
- On servers where `INBOX_LIST_MODEM` is switched on, the faxes are grouped by line, with a heading row showing the line name, instead of being listed by date.

### New-fax notification

While an Inbox page is open, the browser asks the server for the number of faxes every 30 seconds. When the number changes, the number next to the menu and the number in the browser tab title change, and on the Inbox page the list reloads itself. If these options are switched on in the server configuration, a new fax additionally brings the window to the front (`FOCUS_ON_NEW_FAX`), or shows a browser notification and plays the sound file set on your account (`FOCUS_ON_NEW_FAX_POPUP`; the browser must allow notifications). Both are off by default.

When there are no faxes, a "0 FAXES" message is shown with **Send Your First Fax** and **Search Archive** buttons.

## Viewing a fax

Click the thumbnail or **View** to open the viewer. Only faxes that are in the Inbox can be opened; the address of a fax that is archived, deleted, or not yours takes you back to the Inbox.

- The top shows **From**, **Date**, **Pages**, FaxID and **Device** (the receiving line).
- The column on the left holds a numbered thumbnail for each page. Click a thumbnail to show that page large. Clicking the large image moves on to the next page, and from the last page back to the first.

The buttons are:

| Button | What it does |
|---|---|
| Prev / Next | Go to the previous or next fax in the list (only shown when there is one). |
| Rotate | Rotates the fax by 90 degrees. |
| PDF | Downloads the PDF (depending on the browser it may open directly in the window). |
| TIFF | Only shown when TIFF download is switched on for the server. |
| Reply | Opens [Send Fax](send-fax.md) with the sender's number filled in as the destination. The original fax is sent along. |
| Email | E-mails the PDF. |
| Note | Adds a note. |
| Archive | Moves the fax to the Archive and goes to the next fax (or the previous one, or the Inbox if there is none). |
| Delete | Only shown when you may delete faxes. After deleting it goes to the next fax. |
| Inbox → | Back to the list. |

## Naming the sender (assigning a company)

The Sender column compares the fax's number with the address book and shows one of these:

| Shown | Meaning | What to do |
|---|---|---|
| Company name link | The number is in the address book. The link opens the company's edit page in the address book. | Nothing. |
| Number (or "Unknown Sender") link | The sender is not in the address book. | Click the link and name the sender on the **Name the sender** page. |
| Link whose company name equals the number | The company is only named after its number. | Click the link and rename it on the **Assign Company Name** page. |
| Drop-down with a **Select** button | "This number belongs to several companies. Which one is it?" | Pick the right company and click **Select**. |

### The "Name the sender" page

Opened from the link of an unknown sender. The sending number is shown at the top.

- **Select Contact Record**: pick an existing company from the list.
- **Or type a new company name**: create a new company to assign.
- Click **Save**: the fax is assigned to that company and you return to the Inbox. If both are empty, "You must enter a company name" is shown.

### The "Assign Company Name" page

Opened when the company is only named after its number.

- Type a new name into **Search Company Name** and click **Save** to rename that company. The placeholder of the box reads "Type company name to filter...", but the list is not filtered: what you type is saved as the new company name.
- Alternatively, pick an existing company in **Select Contact Record** and click **Save**: the numbers and faxes of this company are merged into the chosen company and this company disappears.
- If the name consists only of digits and a White Pages address is configured on the server, a White Pages search icon appears next to the box.

## Notes

**Add a note** (or **Note** in the viewer) opens the **Note / Description** box. Enter the text and click **Save**; it is stored as the fax's description, shown below the sender in the Inbox and in the **Description** column of the Archive. The box starts out containing the sentence "Reviewed and verified by operator.", so replace it with your own text before saving. You can find a note's text with **Keywords** in the [Archive](archive.md).

## E-mailing a fax

**Email Fax** (**Email** in the viewer) opens the **Forward fax via email** page.

| Field | Description |
|---|---|
| From | Your name and e-mail address from Settings. It cannot be changed here. |
| Recipients * | The addresses to send to. Separate several with commas and similar separators. **Choose from contacts** picks from the e-mail book. |
| CC / BCC | Optional. |
| Subject | Defaults to the company name (up to 45 characters). |
| PDF file name | Defaults to `fax-company.pdf`. |
| Message | Pre-filled with your e-mail signature from Settings. |
| Category | Only shown for a fax that is still in the Inbox. Choosing one assigns the category to the fax. |
| Archive fax | Only shown for a fax in the Inbox, and ticked by default. If it stays ticked the fax moves to the Archive after the mail has been sent. |

Click **Send**. The mail is sent with the PDF attached and "The email was sent successfully." is shown. Addresses used for the first time are added to the e-mail book automatically. A malformed address gives "Please enter a valid e-mail address." and a failed delivery gives "The email failed to send."

## Archiving and deleting

- **Archive** moves the fax from the Inbox to the [Archive](archive.md). The fax itself is not removed.
- **Delete** opens the **Delete Fax** confirmation: "Are you sure you want to delete this fax?" and "This operation will permanently purge the fax document archive." Clicking **Delete** cannot be undone. If your account has no delete right the Delete button is not shown at all.

## Batch actions

Use the row above the table to handle several faxes at once.

1. Tick the check boxes of the faxes, or tick **Select All Faxes** (all faxes on the current page are selected).
2. **Archive Selected** moves every selected fax to the Archive.
3. **Delete Selected** (only shown when you may delete) opens a confirmation, "Delete selected faxes?", with the number of faxes. **Delete** deletes them; **Cancel** returns to the Inbox.

## Replying

**Reply** opens [Send Fax](send-fax.md) with the sender's number as the destination. If the address book holds a number for the fax it is used; if no usable number is known the destination is left empty. The received fax is attached automatically and sent along; the page says "The original fax is sent along." and offers a PDF link.
