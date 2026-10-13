# NamiFAX User Manual

This manual explains how to use NamiFAX as an ordinary (non-administrator) user: receiving, sending and finding faxes, managing contacts, and setting up your own account. For the administrator screens, see the [Admin manual](admin/index.md).

!!! note "What you see depends on your account and the server settings"
    Which faxes are visible (lines, categories), whether a Delete button is shown, and whether the Priority and TSI fields appear all depend on the rights given to your account. Some features only work when the administrator has switched them on in the server configuration. Each such condition is mentioned where it applies.

## Screen map

After you sign in, the following menu is shown at the top of the page. An access key is a keyboard shortcut that opens the screen when pressed together with your browser's access-key modifier (this differs by browser and operating system).

| Menu | Access key | Description | Details |
|---|---|---|---|
| Inbox | `i` | List of received faxes. The number badge next to the menu is the number of faxes in the inbox. | [Inbox](inbox.md) |
| Send Fax | `s` | The fax sending form. The blue **Send Fax** button at the top right opens the same screen. | [Send Fax](send-fax.md) |
| Outbox | `o` | Jobs that are queued or being transmitted. The badge is the number of jobs in progress. | [Outbox](outbox.md) |
| Archive | `a` | Search sent and archived faxes. | [Archive](archive.md) |
| Contacts | `c` | Address book, e-mail book and distribution lists. | [Contacts](contacts.md) |

The top right of the page also has:

- **Settings** (access key `p`): profile, language, password, two-factor authentication and passkeys. See [Account settings](account.md).
- **Logout** (access key `l`).
- A fax line indicator: green with the number of lines that are "Ready" when lines are available, otherwise "Standby".
- For administrators, a gear icon that links to the admin pages. A superuser account also gets a **Superuser** badge next to the name.

!!! tip "Narrow screens"
    On a narrow screen (for example a phone) the top menu row is hidden. Use the buttons and links on each screen, or type the address directly.

## What is in this manual

1. [Getting started](getting-started.md): signing in (password, two-factor step, passkey, SAML), forgotten password, expired password, language, logging out
2. [Inbox](inbox.md): the list, viewing a fax, naming the sender, notes, e-mailing, archiving and deleting
3. [Send Fax](send-fax.md): recipients, attachments, cover page, advanced options, what happens after sending
4. [Outbox](outbox.md): the queue, modifying and killing jobs, retrying, transmission report
5. [Archive](archive.md): search filters, results, actions
6. [Contacts](contacts.md): address book, e-mail book, distribution lists, vCard import, picker windows
7. [Account settings](account.md): profile, language, password, two-factor authentication, passkeys

Administrator settings are covered in the [Admin manual](admin/index.md).
