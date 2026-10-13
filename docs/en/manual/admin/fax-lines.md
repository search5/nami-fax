# Fax lines and routing

This page covers the screens that describe your fax lines and decide where a received fax goes: **Fax Modems**, **DID Routing**, **Barcode Routing**, **Fax Categories**, **Fax to Email** and **Blacklist (DynConf)**.

## How a received fax is routed

When HylaFAX receives a fax, the `faxrcvd` hook files it in the Inbox and then chooses a category, an e-mail contact and a printer. The steps run in this order, and a later step overrides an earlier one only for the values it actually has:

1. **Line or DID route.** With DID routing **off** (`ENABLE_DID_ROUTING` not set), the settings of the receiving line (**Contact Email**, **Printer**, **Category** on [Fax Modems](#fax-modems)) are used. With DID routing **on**, the route whose **Route Code** equals the dialled DID number is used instead (the line's own settings are then not used).
2. **Fax to Email.** If the sender's fax number is in the Address Book and that number has an **Email**, **Printer** or **Category**, they replace the values above.
3. **Barcode.** If barcode support is on and a barcode is read from the fax, a matching **Barcode Routing** rule replaces the category, printer and contact with the ones it has.

The e-mail goes out through the [SMTP gateway](system.md#smtp-gateway). Printing happens only when the hook runs with `PRINTFAXRCVD` switched on.

## Fax Modems

**Fax Modems** (`/admin/modems`, sidebar group *Hardware & Lines*) lists the fax lines NamiFAX knows about under **Active Modem Lines**: **Device**, **Alias**, **Contact** and **Status**.

!!! note
    Devices entered here must be devices that the HylaFAX server really has (serial ports, USB modems or virtual IAX modems). The screen only records them.

### Add, edit and delete

Use the form on the right (**Configure Modems Device** for a new line, **Edit Modem (…)** for an existing one). Click a device name to edit it.

| Field | Meaning |
|---|---|
| **Device** \* | The HylaFAX device name, for example `ttyS0`. |
| **Alias** \* | A friendly name, for example `Main Inbound Line`. |
| **Contact Email** | Received faxes of this line are e-mailed here (DID routing off). |
| **Printer** | A printer name handed to the print command for received faxes of this line (DID routing off), for example `lp0`. This is plain text. |
| **Category** | The category given to received faxes of this line (DID routing off). Choose from [Fax Categories](#fax-categories). |

- **Create** adds a line. Messages: *The modem was created*; *You must enter a device name*; *You must enter an alias*; *This modem already exists*.
- **Save** changes alias, contact, printer and category. The device name of an existing line cannot be changed: the Device box is ignored on save, so delete the line and create it again to rename it.
- **Delete** (with a confirmation) removes the line from NamiFAX.

### Status

The status text comes from running the HylaFAX `faxstat` command on the web server each time the page is built. Possible values:

| Status shown | Meaning |
|---|---|
| Running and idle | The modem is free. |
| Sending fax {JID: n} | Sending job `n`. |
| Receiving from … / Receiving facsimile | A fax is being received. |
| Please wait | `faxstat` gave no answer for this device, or the state is not one of the above. |

The dashboard shows the same status next to each line. The status texts are not translated.

## DID Routing

Available only when `ENABLE_DID_ROUTING` is on. **DID Routing** (`/admin/did`, also `/admin/routing/did`) lists the **Active DID Routing Rules** (**Route Code**, **Alias**, **Contact**, **Printer**).

| Field | Meaning |
|---|---|
| **Route Code** \* | The DID number (extension) that HylaFAX reports for the call. The match must be exact. |
| **Alias** \* | A friendly name. |
| **Contact Email** | Faxes of this route are e-mailed here. |
| **Printer** | Printer name for received faxes of this route. |
| **Category** | Category given to the faxes of this route (**-- None --** for no category). |

Press **New DID Route** (or **Reset**) for an empty form, click **Edit** on a rule to change it. With a rule open you can **Save**, **Delete** (with a confirmation) or **Cancel**.

When a fax arrives on a DID number that has no rule, the hook creates one with the number as both route code and alias, unless `AUTOCONFDID` is switched off (it is on by default). Which users may see the faxes of a route is set on the [Users](users.md) screen (**DID Routes**).

## Barcode Routing

Available only when `ENABLE_BARDECODE_SUPPORT` is on. **Barcode Routing** (`/admin/barcodes`) routes faxes by a barcode read from the fax (Code39 or QR, as the screen says). The recognised value is also stored as the fax's note.

Fields: **Barcode** \*, **Alias** \*, **Contact Email**, **Printer**, **Category**. Press **New Barcode Route** for a new rule; click **Edit** on a rule to **Save**, **Delete** or **Cancel**. The rule matches when its **Barcode** equals the recognised value.

## Fax Categories

**Fax Categories** (`/admin/categories`) manages the labels used to organise faxes. The list **Existing Categories** shows each name and its ID.

- **New Category**, then type the **Category Name** \* (for example `Invoices`) and press **Save**.
- **Edit** a category to rename it (**Save**) or **Delete** it (with a confirmation). Deleting a category also removes it from the faxes that had it.

Categories are used when you give users access to categories ([Users](users.md)), and as the **Category** of lines, DID routes, barcode rules and Fax to Email numbers. An empty name is refused (*Category Name is required*).

## Fax to Email

**Fax to Email** (`/admin/fax2email`) sets where faxes **from** a given sender go. The list **Company Forwarding Rules** shows each company in the Address Book, how many fax numbers it has and its e-mail and printer. Companies and their fax numbers are created in the Address Book (the link **Add companies in the Address Book**); when a fax comes from an unknown number, the receive hook adds it to the Address Book by itself.

Click **Edit** on a company. The form shows the **Company** name and, for each of its fax numbers, the number (read-only) and:

| Field | Meaning |
|---|---|
| **Email** | One or more addresses, separated by `,` or `;`. Every address must be valid (*Please enter a valid e-mail address.*). |
| **Printer** | Printer name. |
| **Category** | Category given to the faxes from this number. |

**Save** stores the company name (required) and the three values of every number (*Fax to Email settings saved*). **Delete** removes the company *and all its fax numbers* (with a confirmation). Unless `ARCHIVEFAX2EMAIL` is switched off (on by default), a fax that was forwarded by these rules is moved to the archive after it is mailed or printed.

## Blacklist (DynConf)

**Dynamic Configuration** (`/admin/dynconf`) blocks incoming calls by caller ID. The list **Blocked Caller IDs** shows each rule with its caller ID, device (or *All Devices*) and ID.

| Field | Meaning |
|---|---|
| **Caller ID** \* | The caller's number. The match is exact (a SIP `@host` part sent with the number is ignored). Despite the example text in the box, patterns are not supported. |
| **Modem Device** | One of your lines, or **All Devices**. |

Use **New Rule**, then **Save**; click **Edit** on a rule to **Save**, **Delete** or **Cancel**. Creating a rule that already exists is refused (*Rule already exists*).

The rules take effect only when the `dynconf` hook is connected to HylaFAX ([HylaFAX setup](../../install/hylafax.md)): on each call HylaFAX asks the hook, and the hook answers `RejectCall: true` for a blocked caller. A rule applies from the next call; each check is written to the [system log](system.md#system-logs).
