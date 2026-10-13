# Authentication

This page describes the ways people sign in, from the administrator's point of view: what you configure, what users do themselves, and what protects the sign-in. Only SAML has an admin screen; the other settings are environment variables and the user settings.

## Ways to sign in

| Way | Where it is set | Notes |
|---|---|---|
| User name and password | [Users](users.md) | Always available. Subject to [login throttling](#login-throttling), the password expiry rules and, if the user turned it on, TOTP. |
| Passkey | The user, in their own settings | A **Sign in with Passkey (Touch ID / Security Key)** button is always on the login page. |
| SAML 2.0 SSO | **SAML 2.0 SSO** admin screen | The button **SAML 2.0 Enterprise SSO (Okta / Entra ID)** appears on the login page only when SAML is enabled and an IdP sign-on URL is set. |
| System password (PAM, `pwauth`) | Environment variables `ALTERNATE_AUTH_ENABLE`, `ALTERNATE_AUTH_CLASS`, `ALTERNATE_AUTH_FALLBACK`, `PWAUTHPATH` | Optional. The account must still exist in NamiFAX. With `ALTERNATE_AUTH_FALLBACK` on (default) the NamiFAX password may be used when the system password fails. |
| Web server sign-in | Environment variable `WEBSERVER_AUTH` | Optional. Trusts the `REMOTE_USER` that the web server sets. Off by default. |

## SAML 2.0 SSO

**SAML 2.0 SSO** (`/admin/saml`, *Superuser only*) connects NamiFAX, as a service provider, to an identity provider (IdP) such as Okta, Microsoft Entra ID, Google Workspace or Keycloak.

### Set-up order

1. Open the page. In the box **NamiFAX SP Endpoints** copy the **Assertion Consumer Service (ACS) URL**, the **SP Entity ID / Metadata URL** and note the **NameID Format** (`urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress`) into your IdP. **Download SP Metadata XML** gives the same information as a file. The addresses are built from the address you used to open the page, so open the admin screen through the public address of NamiFAX (for example `https://fax.example.com`).
2. In the IdP, make the user's e-mail address available as the NameID (or in an `email` attribute) and, if you want, a display name in `displayName` or `name`.
3. Back in NamiFAX fill in **Identity Provider (IdP) Settings** and press **Save SAML Configuration**.

| Field | Meaning |
|---|---|
| **Enable SAML 2.0 Single Sign-On** | Shows the SSO button on the login page. |
| **IdP Entity ID / Issuer** | The IdP's entity ID. If you fill it in, the Issuer of every answer must match it. If it is empty the Issuer is not checked and a warning is written to the server log; fill it in. |
| **IdP Single Sign-On Service URL (HTTP-Redirect / POST)** | Where users are sent to sign in. Without it the SSO button does not appear. |
| **IdP Public X.509 Certificate (PEM)** | Certificate that verifies the IdP's signature. Without it every SAML answer is refused. |
| **Just-in-Time (JIT) Provisioning** | On (default): an account is created at the first SSO sign-in. |
| **Default Role for JIT Users** | **Standard User** or **Administrator**. *Administrator* gives the new account the *Administrator Console* flag. Ignored when rights are taken from the IdP (below). |

The page does not check the values when you save them.

### How a SAML sign-in is accepted

- The answer must be **signed** by the IdP with the configured certificate; only the signed part is believed.
- It must answer the sign-in request that this browser started, be addressed to NamiFAX (audience and recipient), be within its validity time (a 2 minute clock difference is tolerated) and not have been used before.
- The user is found by **e-mail address** (never by the part before the `@`). If no account has that address and JIT is on, an account is created: the user name comes from the part of the NameID before `@` (made unique with a number if needed), it has no administrator rights unless *Default Role* says so, and a random password that nobody knows.
- With JIT off and no matching account the person is sent back to the login page with *No account here matches the identity provider's answer.*
- A disabled account is refused, as with a password.

A SAML sign-in does not ask for a TOTP code and is not counted by the login throttle.

### Taking rights from the identity provider

Tick **Take rights from the identity provider** to let the IdP decide an account's rights **at every sign-in**. Rights set by hand on the [Users](users.md) screen are overwritten at the next SSO sign-in, and a role the IdP no longer sends takes the right away.

| Field | Default | Meaning |
|---|---|---|
| **Attribute that holds the roles** | `Role` | Name of the SAML attribute that lists the user's roles. |
| **Role: administrator** | `namifax-admin` | Role that gives *Administrator Console*. |
| **Role: superuser** | `namifax-superuser` | Role that gives *Superuser Rights* (and, with it, the console). |
| **Role: may delete faxes** | `namifax-can-delete` | Gives *User can delete faxes*. |
| **Role: send on any line** | `namifax-any-modem` | Gives *Send on Any Modem*. |
| **Attribute with the lines** | empty | Attribute listing the device names of the **Fax Lines** the user may use. |
| **Attribute with the categories** | empty | Attribute listing **Category** names. |
| **Attribute with the DID routes** | empty | Attribute listing DID route codes or aliases. |

A role field left empty never grants that right. For the lines, categories and DID routes, a blank attribute name means *not managed* (the values set on the Users screen stay); names that do not exist in NamiFAX are ignored.

## Passkeys (WebAuthn)

- Users register their own passkeys in their settings (**FIDO2 Passkeys & Biometric Security Keys**, **Register New Passkey**) and can remove them there. There is no admin screen to list or revoke another user's passkeys.
- A passkey is tied to the host name the user was on when registering (NamiFAX uses that host name as the relying-party ID). Keep one stable address for NamiFAX; passkeys registered under another host name will not work on a new one. Browsers only allow passkeys on HTTPS pages (and on `localhost`).
- A passkey sign-in checks only that the account is enabled. It does **not** ask for a TOTP code and is **not** counted by the login throttle. This is deliberate in the current design.

## TOTP (authenticator app) and recovery codes

- TOTP is optional and **per user**; there is no switch for administrators to require it for everybody. A user turns it on in their settings (they confirm with a code from the app and receive recovery codes), turning it off needs the password and a valid code, and making new recovery codes needs a valid code.
- When a user has TOTP on, a **password** sign-in (including a system-password or web-server sign-in routed through the login page) is followed by the code step. Passkey and SAML sign-ins skip it.
- After 5 wrong codes the user is locked out of the code step for 15 minutes, even for a correct code. These two numbers are fixed in the program; they are not the throttle variables below.
- If the user lost the authenticator and the recovery codes, turn their TOTP off on the server with `namifax reset-2fa <username>` (see [Users](users.md)).

## Login throttling

Wrong passwords on the login form are counted so that guessing is stopped. Two counters run side by side.

| | Account (by user name) | Address (by client IP) |
|---|---|---|
| Limit | `NAMIFAX_LOGIN_MAX_FAILURES`, default **5** | 10 times that, default **50** |
| What happens | The account is **locked**. The password is no longer even looked at, so the right password does not help. | The address is locked for `NAMIFAX_LOGIN_LOCK_MINUTES` minutes (default **15**), then tried again. |
| Ends | **Never by itself.** An administrator unlocks it. | By time. |
| Counting | From the last successful sign-in; failures do not expire. | In a window of the same length as the lock. |
| Message | *Too many failed sign-in attempts. This account is locked until an administrator unlocks it.* | *Too many failed sign-in attempts. Please try again later.* |

Details worth knowing:

- Failures are counted per user name **whether or not the account exists**, so the answer does not reveal which names are real.
- A correct password clears the account's count. A successful sign-in does not lift a lock that already exists.
- The address limit is higher because one address can be a whole office or a proxy.
- To **unlock an account**: press **Unlock** in the [Users](users.md) list, or run `namifax unlock-user <username>` on the server. There is no way to unlock an address before its time is up.
- Both variables are read when the sign-in happens; set them in the service environment (for example `/etc/namifax.env`, see the [HylaFAX setup](../../install/hylafax.md)) and restart. A value that is not a positive whole number is replaced by the default.
- The counters are kept in the database, so all worker processes share them and a restart does not clear them.

## Sessions

- The sign-in cookie `namifax_session` is `HttpOnly` and `SameSite=Lax`. It carries `Secure` when `session.secure = true` is set in the ini file or, without an ini value, when `NAMIFAX_SESSION_SECURE` is `1`/`true`/`yes`. Turn this on when NamiFAX is served over HTTPS.
- Sign-in sessions are kept in the memory of the web process. They end after **2 hours without any request** (the time restarts at each request; it cannot be configured), and a restart of the web service signs everybody out.
- A second cookie, `namifax_flow`, holds short-lived steps such as the TOTP step, the password-change step and SAML or passkey challenges. It lasts 30 minutes and is signed with `NAMIFAX_SESSION_SECRET` (or `session.secret`). **Set a fixed value**; without one a random secret is made for every process, which breaks these steps after a restart or when more than one worker answers.
- Rights changes made on the Users screen: the *Administrator Console* and *Superuser* flags apply at the next sign-in; lines, DID routes, categories and the delete right apply at once.
- Passwords of users are stored as Argon2id hashes. TOTP seeds, the SMTP password and the S3 secret are stored encrypted with `NAMIFAX_SECRET_KEY`; keep that key safe, because encrypted values cannot be recovered without it.
- *Forgot password?* on the login page mails a new random password to the account's address (through the [SMTP gateway](system.md#smtp-gateway)); the user must choose a new password at the next sign-in.

See also the [operations checklist](../../install/operations-checklist.md).
