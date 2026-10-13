# Account settings

Click **Settings** at the top right (access key `p`) to open the **User Settings** page. **Return to Inbox** at the top takes you back at any time. Profile, preferences and password are one form: click **Update Settings** at the bottom to save them all at once. Two-factor authentication and passkeys are separate areas below that form and are handled on their own.

After a successful save "Settings updated successfully." is shown.

## Personal & Organization Details

| Field | Description |
|---|---|
| Full Name * | Required. If left empty, "You must enter a name." is shown. Shown at the top of the page and used as the sender name when you e-mail a fax. |
| Email Address * | Required and must be a valid address. Used by [Forgot password](getting-started.md) and for sending faxes by e-mail. |
| Company Name, Office / Location, Direct Voice Number, Direct Fax Number | Sender details printed on the cover page of the faxes you send. |
| Transmitting Station ID (TSI) | Only shown to superuser accounts. The header identifier printed at the top of transmitted fax pages. |
| Email & Fax Notification Signature | The signature pre-filled in the **Message** box when you e-mail a fax. |

## Portal & Delivery Preferences

| Field | Description |
|---|---|
| Display Language | The language of the screens. Choose among many languages, including English, Korean, Japanese, Chinese (Simplified and Traditional), German and French. |
| Default Cover Page | The cover page that is preselected in [Send Fax](send-fax.md). Choose among the cover pages the administrator has set up. |
| Faxes Per Page | Number of faxes on one [Inbox](inbox.md) page (10, 15, 20, 25, 30, 50, 100). |
| Archive Faxes Per Page | Number of faxes on one [Archive](archive.md) page (same choices). |

A changed language is saved with your account and is also remembered by this browser for one year, which makes it apply to the login page.

## Change Password

The **Change Password** area is skipped if you leave it empty. To change your password fill in all three fields and click **Update Settings**:

1. **Current Password**
2. **New Password**
3. **Confirm New Password**

If the current password is wrong or the two new passwords differ, an error is shown and the other settings entered together with it are not saved either. By default a password must be 8 to 15 characters long (an administrator can change this), and depending on the account settings an earlier password cannot be reused. Error messages for this form may appear in English.

## Two-Factor Authentication (TOTP)

The badge at the top right of the **Two-Factor Authentication (TOTP)** area shows the state (**Active / Enabled** or **Disabled**). When it is on, signing in with a password requires, in addition to the password, a 6-digit one-time code from an app on your phone. Google Authenticator, Authy and other apps that support RFC 6238 can be used.

!!! note "Passkey and SAML sign-in"
    The two-factor code applies to password sign-in only. Signing in with a passkey or through SAML does not ask for it.

### Turning it on

1. Click **Enable 2FA (Setup Authenticator)**.
2. On the setup page, step 1: scan the QR code with your authenticator app. If you cannot scan it, type the **Key** into the app by hand (**Copy key** copies it).
3. Step 2: enter the 6-digit code shown by the app and click **Turn on 2FA**. If it does not match you get "The code did not match. Check the time on your phone and try again."
4. On success the **Save your recovery codes** page shows 8 recovery codes.
5. Keep them somewhere safe with **Copy codes** or **Download as a file**, then click **Done**.

Recovery codes are for emergencies if you lose your phone, and each code works only once. They are shown only on this page, so be sure to store them. The downloaded file is made in your browser and is not stored on the server, which keeps the codes only as hashes. The file contains the recovery codes only, not the authenticator key.

### While it is on

When it is on, "N recovery codes left" is shown, and you can do two things:

- **New recovery codes**: enter the current code from your app and click it; all existing recovery codes are replaced by a new set that is shown to you.
- **Disable 2FA**: enter your **Password** and a **Code or recovery code**, click the button, and confirm "Turn off 2FA for your account?". Two-factor authentication is turned off and you return to the Settings page. A wrong password gives "The password is not correct." and a wrong code "The code is not valid."

After 5 wrong codes the code check is locked for 15 minutes ("Too many failed attempts. Try again in N minutes.") and even a correct code is refused during that time. If you have lost both your phone and your recovery codes, contact your system administrator.

If no encryption key is configured on the server, the setup page may show an error message instead; contact your administrator in that case too.

## FIDO2 Passkeys (security keys)

The **FIDO2 Passkeys & Biometric Security Keys** area manages passkeys for signing in without a password using Touch ID, Face ID, Windows Hello or a YubiKey.

1. Click **Register New Passkey**.
2. In the prompt the browser shows, enter a name by which you will recognise this key (for example MacBook Touch ID, YubiKey).
3. Confirm with your fingerprint, face or security key as your device and browser ask.
4. Once registered, the list shows the device name and the registration time.

**Remove** in the list removes that passkey after confirmation. With none registered, "No Passkeys registered yet." is shown.

- If the browser does not support passkeys (WebAuthn), an alert says so.
- A passkey is tied to the server address (host name) you used when registering it. Use the same address when signing in.
- For signing in with the **Sign in with Passkey (Touch ID / Security Key)** button on the login page, see [Getting started](getting-started.md).
