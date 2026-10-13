# Send Fax

Use **Send Fax** (access key `s`) to send a document by fax. The top of the page has **Address Book** and **Distribution Lists** shortcut buttons. The form has four sections.

## 1. Destination & Recipients

| Field | Description |
|---|---|
| Destination fax numbers * | Required. To send to several destinations at once, separate the numbers with semicolons (for example `+1-555-0199`). |
| Attention To | Optional. Printed on the cover page; with a single number it is also passed on as the name of the destination. |
| Company | Optional. Printed on the cover page. |
| Location, Voice Number, Address, City, Zip | Optional. Used on the cover page. |
| Subject / Regarding | Optional. Passed on to the cover page and the transmission job as the subject. |

### Picking destinations from your contacts

Two links sit under the destination field. Both open a small pop-up window, so allow pop-ups in your browser if they are blocked.

- **Choose from contacts**: the fax numbers of the address book are listed as "Company - number". Typing in the box at the top filters the list as you type; pressing Enter in the box searches on the server. Tick the entries you want and click **Add**: the numbers are appended to the destination field, separated by semicolons, and the window closes. If you pick **exactly one** number, the person, company, address, zip, city, location and voice number saved with that number are filled into the matching fields as well.
- **Choose a distribution list**: the distribution lists are shown. Tick one or more and click **Add** to append all fax numbers of those lists to the destination field. See [Contacts](contacts.md) for how to create lists.

If the administrator has turned off showing all contacts, you have to type at least two characters before any contacts are listed.

## 2. Document Attachment

- Click the file area and choose files. You can choose several files, click again to add more, and remove one from the list with `×`. The list shows each file's name and size; a file over the size limit is shown in red.
- **Supported: PDF, TIFF, PostScript, TXT.** The type is decided by the file's content, not its name, so a file that merely has a different extension is not accepted. Plain text (UTF-8) is allowed.
- The maximum size per file is shown on the page as "Max 10 MB" (the default is 10 MB; an administrator can change it).
- Convert Word or Excel documents to PDF before attaching them.
- You can also send a cover page without any file. If you choose no file and do not include a cover page, "Select a file to send, or ask for a cover page." is shown.

An unsuitable file gives "File type is unauthorized (file name)" and a file that is too large gives "File size is over the limit (file name)"; in both cases nothing is sent.

## 3. Cover Page

- Tick **Include Cover Page** to show the options below. Whether it is ticked from the start depends on the server setting `SENDFAX_USE_COVERPAGE` (on by default).
- **Cover Template**: choose among the cover pages the administrator has set up. The preselected one is your **Default Cover Page** from [Account settings](account.md), or the first in the list if you have none. If no cover pages exist, "No cover pages are set up" is shown.
- **Send via Line**: only shown when more than one line is available to you. The entry **Any Available Line (Auto)** only appears for accounts that have that right. Choosing a line you may not use gives "You may not use this line." If no modem is configured at all, "No modems configured" is shown and nothing can be sent. This field is part of the cover page section, so it folds away when Include Cover Page is unticked.
- **Cover Comments**: a note or message printed on the cover sheet.

The sender details on the cover page (name, company, location, voice and fax number) come from the values you entered in [Account settings](account.md).

## 4. Advanced Options

**Advanced Options** (priority, retries, notifications) is collapsed at first; click it to expand.

| Field | Description |
|---|---|
| Priority | Only shown to superuser accounts. Other accounts are sent with the default priority. |
| Max Retries | A number from 1 to 10. "Retries automatically on busy signal." If left empty the server default is used. |
| Expire after | A number and a unit (**Minutes**, **Hours**, **Days**). If the fax has not been sent within that time the job expires. If left empty the server default is used. |
| Schedule Send Time | Tick it and choose an hour and minute to send at that time. If it is not ticked the fax is sent as soon as possible. |
| TSI ID | Only shown to superuser accounts. Other accounts use the value saved in their settings. |
| Notify on requeue | When ticked, HylaFAX is asked to send a notification also when the job is requeued. Whether it is ticked from the start depends on the server setting `SENDFAX_REQUEUE_EMAIL` (on by default). |

## Sending

Click **Send Fax** at the bottom of the form to put the fax into the HylaFAX queue. **Cancel & return to Inbox** leaves without sending and goes to the [Inbox](inbox.md).

When the fax has been queued you are taken to the [Outbox](outbox.md) with the message "Your fax has been successfully queued to be faxed." and the job number in brackets. Follow the job in the Outbox; once it has been sent you can find it in the [Archive](archive.md).

If the fax cannot be queued, the form is shown again with the error above it and your entries are kept. Typical causes are an empty destination, a file that is not accepted, or HylaFAX (the `sendfax` program) not being installed or reachable on the server. In the last case, ask your administrator.

!!! note "Replying to a received fax"
    **Reply** in the [Inbox](inbox.md) and **Re-send** in the [Archive](archive.md) open this page with the original fax attached automatically ("The original fax is sent along."). For a received fax the sender's number is filled in as the destination.
