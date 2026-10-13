# Outbox

The **Outbox** (access key `o`) shows the jobs that are in the transmission queue. The number badge next to the menu is the number of jobs in progress. The page refreshes itself every 60 seconds.

!!! note "Which jobs you see"
    A superuser sees all jobs. Other accounts only see the jobs they sent themselves (and those sent for them by mail).

As the banner at the top says, only faxes that are queued or in progress are listed. Once a fax has been delivered it disappears from the list; completed records are found in the [Archive](archive.md). With no jobs at all, "No jobs in queue" and a **Send a Fax** button are shown. Right after you queue a fax in [Send Fax](send-fax.md), the message "Your fax has been successfully queued to be faxed." (with the job number) appears at the top.

## Jobs in progress

Under the "N jobs in progress" badge, each job is one row.

| Column | Content |
|---|---|
| Job ID | The HylaFAX job number. |
| Priority | The job priority. |
| User | The user who submitted the job. |
| Company | The company if the destination number is in the address book, otherwise the number. |
| Pages | Number of pages to send. |
| Dials | How many times the number has been dialled so far. |
| TTS | The scheduled transmission time (empty if none is scheduled). |
| Status | The job state text reported by HylaFAX (underscores are shown as spaces). |
| Actions | **Modify**, **Kill**. |

The status text is shown exactly as HylaFAX reports it; this manual does not list the possible values.

## Modifying a job

**Modify** opens the **Modify Job** page. Fill in only what you want to change and click **Save**; the job is altered and you return to the Outbox. Fields left empty or unselected are not changed.

| Field | Description |
|---|---|
| New Destination | Changes the destination fax number. |
| Priority | The empty first entry leaves the priority as it is. |
| Modem / Device | Assigns a different line. |
| Number of tries | Maximum number of tries (a number). |
| Expire after | "Now +" a number and a unit (**Minutes**, **Hours**, **Days**). The job expires after that time from now. |
| Schedule Send Time | Tick **Now** to ask for immediate transmission. Tick the second box and choose hour and minute to schedule the job for that time. |

A non-numeric value in a numeric field gives "Please enter a valid number." **Cancel** returns without changes.

## Killing a job

**Kill** opens a confirmation, "Kill job N?". When you confirm, the job is removed from the queue and "Job #N successfully killed" is shown. If the job cannot be removed, "Failed to kill job #N" is shown, and if it has already gone, "Job #N was not found in your queue". A killed job cannot be brought back. If your session has expired you get "Your session has expired. Reload the page and try again."; reload and click again.

## Failed transmissions

Jobs that failed are collected in a separate **Failed Transmissions — N** table lower on the same page ("Review the number or retry below."). It has the same columns as the table above, except **TTS**.

- **Retry** opens the same Modify Job page. Clicking **Save** there asks for the job to be resubmitted together with your changes. **Expire after** is preset to 3 hours; you can also change the destination and the other fields first.
- **Kill** removes the failed job from the list.

## Transmission report and re-sending

Finished faxes are handled in the [Archive](archive.md). At the right end of each Archive row there is a badge (**Sent** for a sent fax, **Received** for a received one). Clicking it opens the **Transmission Report** for that fax (Company, Date, Pages, Fax Number and an image of the first page), which you can print with **Print**. To send the same document again, use **Re-send** in the Archive.
