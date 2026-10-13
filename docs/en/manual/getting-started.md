# Getting started

## Signing in

Open the NamiFAX address in your browser and the **Sign in** page appears. If you do not have an account, contact your system administrator (the page says the same).

### Signing in with a password

1. Enter your **Username** and **Password**.
2. Click **Login**.

After a successful sign-in you land in the [Inbox](inbox.md). Opening the login address while you are already signed in also takes you to the Inbox.

If the user name or password is wrong, the message "Invalid username or password" is shown. Other messages you may see:

| Message | Meaning |
|---|---|
| Account is disabled | An administrator has disabled the account. |
| Too many failed sign-in attempts. Please try again later. | Repeated failures have temporarily blocked sign-in. |
| Too many failed sign-in attempts. This account is locked until an administrator unlocks it. | The account is locked. Ask an administrator to unlock it. |

### The two-factor (TOTP) step

If two-factor authentication is turned on for your account, a **Two-Factor Authentication** page appears after the password has been accepted.

1. Enter the 6-digit code from your authenticator app in **Authentication Code**. If you cannot use your phone, enter one of the recovery codes you received when you turned two-factor authentication on (each recovery code works only once).
2. Click **Verify & Log In**.

A wrong code gives "Invalid or expired verification code." After 5 failures the account's code step is locked for 15 minutes, and even a correct code is refused during that time ("Too many failed attempts. Try again in N minutes."). Use **Back to Login** to return to the first page.

How to set up two-factor authentication is described in [Account settings](account.md).

### Signing in with a passkey

Under **Or continue with** on the login page, the **Sign in with Passkey (Touch ID / Security Key)** button signs you in with the browser's passkey dialog (Touch ID, a security key and so on) without typing a user name or password.

- Register a passkey first in [Account settings](account.md).
- If the browser does not support passkeys (WebAuthn), an alert says so.
- Passkey sign-in does not go through the two-factor (TOTP) code step above.
- A passkey is tied to the server address (host name) you used when registering it. Use the same address when signing in.

### SAML sign-in

The **SAML 2.0 Enterprise SSO (Okta / Entra ID)** button only appears on servers where an administrator has turned on and configured SAML 2.0 sign-in. It sends you to your company's identity provider and returns you to NamiFAX after authentication. This method does not go through the two-factor (TOTP) code step either.

If SAML sign-in fails you are returned to the login page with the reason, for example "No account here matches the identity provider's answer." In that case contact your administrator.

## Forgotten password

1. Click **Forgot password?** on the login page.
2. On the **Lost Password** page, enter the **E-mail address** of your account and click **Send Password**.
3. A new password is sent to that address. Sign in with it and then change it to one of your choice in [Account settings](account.md).

If no account has that address, the page says so. If the mail cannot be sent, "Email failed to send" is shown and your old password stays valid. Signing in with the new password may first take you to the "Password Expired" page described below. Click **Cancel** to go back.

## Expired password

An account whose password was reset, has expired or has never been used cannot finish signing in even with the right password: it is taken to the **Password Expired** page ("Action Required"). You must choose a new password here to complete the sign-in (if two-factor authentication is on, the code step follows).

1. Enter your current password in **Old Password**.
2. Enter the same new password in **New Password** and **Confirm New Password**.
3. Click **Update Password**.

All three fields are required and the two new passwords must match. By default a password must be 8 to 15 characters long (an administrator can change this), and depending on the account settings a previously used password cannot be reused. If a rule is broken, the reason is shown.

## Choosing a language

The login page has no language selector. After signing in, choose a language under **Display Language** in **Settings** and click **Update Settings**. The choice is saved with your account and also remembered by this browser (in a cookie), so it also applies to the next login page. Many languages, including Korean, are offered. See [Account settings](account.md).

!!! tip "Changing the language through the address"
    Opening an address with `?lang=ko` appended (for example `/login?lang=ko`) shows that request in the given language.

## Logging out

Click **Logout** below your name at the top right (access key `l`) and you are signed out immediately and taken to the login page. If you open the logout address (`/logout`) directly, a "Sign out?" confirmation page appears and you have to click **Logout** to actually sign out. **Cancel** returns you to the Inbox.
