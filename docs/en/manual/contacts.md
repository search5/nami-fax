# Contacts

**Contacts** (access key `c`) holds three lists in which you can save recipients you use often. Tabs at the top of each page switch between them.

| Tab | Purpose |
|---|---|
| Email Book | E-mail addresses used when e-mailing a fax. |
| Address Book | Companies and their fax numbers (the Contacts menu opens this page first). |
| Distribution Lists | Groups of fax numbers for sending to many recipients at once. |

!!! note "Showing all contacts"
    On servers where the administrator has turned off showing all contacts, the picker windows (in Send Fax and similar) only list contacts after you type at least two characters.

## Address book (companies and fax numbers)

The address book is organised by **company**. A company can have several fax numbers.

### List and search

- Typing in the **Search** box (company name or part of a fax number) filters the table as you type. The **Search** button searches again on the server.
- The table shows **Company / Name**, **Fax Number** (all saved numbers), **Email** and **Actions**; "N companies" is shown at the top right of the table.
- **Send Fax** in a row opens the [Send Fax](send-fax.md) page. **Edit** opens the company's edit page.
- If there are no companies, "No contacts yet" and an **Add First Contact** button are shown.

### Adding and editing a company

**+ New Company** opens the **Add New Company** page.

1. Enter the **Company Name** *.
2. In the **First Fax Number** block enter the **Fax Number** *. It must be a valid fax number, otherwise "Please enter a valid fax number" is shown.
3. If you like, enter **Description**, **Category**, **To person**, **Location**, **Voice Telephone**, **Street Address**, **Zip / Postal Code** and **City** for that number.
4. Click **Save**. "Address book entry saved." is shown.

Open an existing company with **Edit** (or the company name). On the **Edit Company** page you can:

- change the company name or edit the details of each saved number;
- remove a number by clearing its **Fax Number** field and saving ("Clear the number to remove it.");
- add a number by entering it in the **Add a Fax Number** block and saving;
- **Delete** the company and its numbers after confirming. The button is only shown when your account may delete; without the right, trying to delete gives "You are not allowed to delete address book entries."

If the company name is empty or the entry cannot be saved, the reason is shown at the top. **Back to Contacts** returns to the list.

### Importing a vCard (.vcf)

The **Upload contacts file (vCard)** area at the top of the **Add New Company** page (shown only when adding a new company) imports contacts.

1. Optionally choose a **Category** to give to the imported contacts.
2. Choose a `.vcf` file and click **Upload**.
3. The result page shows "Successfully uploaded N contacts".

The import rules are:

- Every fax number (FAX) line of a card creates a company with that number. The company name is the card's organisation (ORG) if it has one, otherwise the person's name (FN). The card's name becomes the number's **To person** and the chosen category its **Category**.
- E-mail lines of a card are added to the e-mail book and are not included in the count above.
- A file that is not a vCard gives the error "vCard file problem: this does not look like a vCard (.vcf) file", and the file size limit is the same as for fax attachments (10 MB by default).

## Email book

- On the **Email Book** tab, typing a name or address into **Search** filters the list.
- The table shows **Contact Name**, **Company Affiliation** and **Email Address**, with **Edit** on each row. With an empty list a message tells you to click "+ New Contact" to register one.
- **+ New Contact** or **Edit** opens a page with **Contact Name** * and **Email Address** *; **Save** stores it ("Contact details saved").
- **Delete** is only shown to superuser accounts. If another account tries to delete, "You are not allowed to delete contacts." is shown.
- **Upload contacts file (vCard)** at the top of the new-contact page imports a vCard: every e-mail address of a card that has a name (FN) is added to the e-mail book and "Successfully uploaded N contacts" is shown.
- When you e-mail a fax (see the [Inbox](inbox.md)), recipient addresses used for the first time are added here automatically.

## Distribution lists

A distribution list is a saved group of fax numbers from the address book. Choosing a list in Send Fax puts all its numbers into the destination field at once.

### Creating a list

1. On the **Distribution Lists** tab click **+ Create List**, or use the **Create New Distribution List** area on the right.
2. Enter a **List Name** * and click **Save** (or **Create List**).
3. You are taken to the page of the new list.

### Managing members

- Choose a list in **Saved Distribution Lists** on the left; its members are shown on the right as "Company - fax number". The **Search** box above the lists filters them, and each list shows its ID and number of members.
- **Add Member** opens the **Add contacts to the list** page. Use the **Search** box to find companies, pick one or more fax numbers in the list (multiple selection) and click **Add**; "Changes saved" is shown. **Back** returns to the list page.
- To remove members, tick their check boxes and click **Remove entries**.
- To rename the list, change the **List Name** and click **Save list name**.
- **Delete** deletes the list after the confirmation "Delete this distribution list?". The companies and numbers in the address book are not affected.

If a number is deleted from the address book it is no longer shown among the list's members.

## Picker windows

Send Fax and the e-mail page contain pop-up windows that let you pick contacts and put them into an input field. Allow pop-ups in your browser.

| Where | Link | Window title | What is inserted |
|---|---|---|---|
| [Send Fax](send-fax.md) | Choose from contacts | Fax Contacts | The fax numbers you pick from the "Company - number" list, separated by semicolons. Picking exactly one also fills in the person, company, address and similar fields. |
| [Send Fax](send-fax.md) | Choose a distribution list | Distribution Lists | All fax numbers of the lists you pick, separated by semicolons. |
| Forward fax via email ([Inbox](inbox.md)) | Choose from contacts | Email Contacts | The e-mail addresses you pick, separated by commas. |

Tick entries and click **Add** to append the values to the end of the original input field; the window closes. Typing in the **Search** box filters the list at once, and **Close** closes the window without inserting anything. If there are no entries, "No contacts found" is shown.
