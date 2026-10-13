# Users

**User Accounts** (`/admin/users`) lists every account and has one form to create or change an account.

## The user list

Columns: **Username**, **Name**, **Email**, **Last Login**, **Last IP**, **Superuser** (YES/NO), **Admin** (YES/NO) and **Actions**. Click a user name or **Edit** to load the account into the form below the list; **Create New User** jumps to the empty form. An account that has never signed in shows `Never` as its last login. Deleted accounts are not listed.

A **Locked** badge next to a user name means too many wrong passwords were typed (see [Lockouts](#lockouts)). Those rows also show an **Unlock** button.

## Creating an account

Fill in the form under **New User** and press **Save**.

| Field | Rules |
|---|---|
| **Full Name** \* | Required, at most 40 characters. |
| **Username** \* | Required. Only letters, digits, `_` and `.` are allowed. At most `MAX_USERNAME_SIZE` characters (default 15). Must not be in use. |
| **Password** | Optional. At most `MAX_PASSWD_SIZE` characters (default 15). If you leave it empty, a random password is generated and e-mailed to the new user through the [SMTP gateway](system.md#smtp-gateway). |
| **Email Address** \* | Required and must be a valid address; at most `MAX_EMAIL_SIZE` characters (default 99). Must not be in use by another account. |
| **Password expiration cycle** | **Never**, **Every 3 Months** or **Every 6 Months**. |
| **Language** | The interface language of the user. |
| **Password can be reused** | Tick to allow the user to choose a password they used before. |

Whichever way the password is given, a new account must choose its own password at the first sign-in (the sign-in is followed by the *password expired* page).

The remaining fields are personal defaults of the user: **My Company**, **My Location**, **My Voice Number**, **My Fax Number**, **TSI ID**, **Select Cover Page** (from the registered [cover pages](covers.md)), **New fax sound** (shown only if sound files are installed), **Inbox - show** and **Archive - show** (rows per page: 10, 15, 20, 25, 30, 50 or 100). Company, location, numbers and TSI start with the values of the environment variables `FROM_COMPANY`, `FROM_LOCATION`, `FROM_VOICENUMBER`, `FROM_FAXNUMBER` and `DEFAULT_TSI_ID` when those are set.

## Permissions

Under **Permissions & Capabilities**:

| Checkbox | Meaning |
|---|---|
| **Administrator Console** | May open the admin screens (see [overview](index.md)). |
| **Superuser Rights** | May open the admin screens and works with all faxes of all lines and categories. Needed for SMTP Gateway, Network Printers, Storage & Cloud and SAML. |
| **User can delete faxes** | May delete faxes. A superuser may delete without this flag. |
| **Send on Any Modem** | The *Line* drop-down of Send Fax offers *Any Available Line (Auto)*. |

## Which faxes a normal user sees

An account without the superuser flag sees the faxes of the choices ticked at the bottom of the form, plus the faxes it sent itself:

- **Fax Lines**: the modems the user may use. When DID routing is switched off, received faxes are matched by line.
- **DID Routes**: shown only when `ENABLE_DID_ROUTING` is on. Includes the entry **Catch All**. When DID routing is on, received faxes are matched by route instead of by line.
- **Categories**: the fax categories the user may see.

If nothing exists yet to tick, the form shows a link instead (for example *You must first create a modem*). Changes of these choices apply at once.

## Changing an account

Load the account and change the form. Leave **Password** empty to keep the current password. After a successful save the form shows *User settings have been saved.* and reloads the account.

- If you type a password, it must be at least `MIN_PASSWD_SIZE` characters (default 8) and at most `MAX_PASSWD_SIZE` (default 15). Unless **Password can be reused** is ticked, a password the account used before is refused.
- Changing the **Password expiration cycle** sets the next expiry date 3 or 6 months from today. When the date has passed, the user must choose a new password at the next sign-in. The same happens for an account whose password was reset (by an administrator disabling it, or through *Forgot password?*).
- Untick **Account active** (shown only when editing) to disable the account: the user can no longer sign in (*Account is disabled*). The account is also marked so that a new password must be chosen at the next sign-in after it is enabled again.
- Changing the user name works; the old name is removed from the HylaFAX user list.

!!! note "Password rules, in short"
    Minimum and maximum lengths come from `MIN_PASSWD_SIZE` / `MAX_PASSWD_SIZE`; the defaults are 8 and 15. The length check is applied when a password is changed; the new-account form only needs a password when you want to choose it yourself.

## Deleting an account

Press **Delete User** at the bottom of the edit form. A confirmation page (*Are you sure you want to delete the user …?*) follows. You cannot delete your own account (*You cannot delete your own account.*) or the last superuser (*You cannot delete the last superuser.*).

A deleted account is marked as deleted and disappears from the list. Its user name and e-mail address become free for a new account, and its stored password history is cleared.

## Lockouts

An account is locked after `NAMIFAX_LOGIN_MAX_FAILURES` wrong passwords (default 5). The lock does not expire. To lift it, press **Unlock** in the user list (the action is written to the system log), or run `namifax unlock-user <username>` on the server. Details are in [Authentication](authentication.md#login-throttling).

## Two-factor authentication (2FA) reset

Users turn their own 2FA on and off in their settings. There is no button for it on the admin screens. If a user lost both the authenticator and the recovery codes, run on the server:

```
namifax reset-2fa <username>
```

This removes the user's 2FA enrolment; the user can enrol again from their settings.
