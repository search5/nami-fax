# Administrator Manual

This manual describes the administration screens (`/admin`) of NamiFAX. Every statement was checked against the screens and the code of this repository.

## Who can open the admin screens

Access is decided by two flags on the user account (set on the [Users](users.md) screen):

| Flag (label on the user form) | Effect |
|---|---|
| **Administrator Console** (`is_admin`) | Opens the admin screens. |
| **Superuser Rights** (`superuser`) | Also opens the admin screens, and works with the faxes of every line and category in the Inbox, Outbox and Archive. |

- Every `/admin` page requires one of the two flags. Someone without either is sent back to the Inbox by the browser; a request that is not a browser page gets `403`; a person who is not signed in goes to the login page.
- Four pages need the **Superuser** flag specifically: **SMTP Gateway**, **Network Printers**, **Storage & Cloud** and **SAML 2.0 SSO**. An account that only has *Administrator Console* sees these menu entries, but opening them is refused (the browser returns to the Inbox).
- The flags are copied into the sign-in session when the person signs in. If you change someone's *Administrator Console* or *Superuser* flag, it applies from their next sign-in. The lines, DID routes, categories and the delete right are read from the database on every request and apply at once.
- The first administrator is created on the server with `namifax createuser` (the account gets both flags unless `--user-only` is given).

!!! note "The text under your name"
    The panel at the bottom of the sidebar always shows the word *Superuser* under your user name. It is fixed text and does not reflect your real flags.

## The menu

The sidebar (and, on a narrow screen, the *Module Switcher* drop-down) is grouped as follows. The Korean labels are the ones shown with the Korean language.

| Group | Entry | Page |
|---|---|---|
| Overview (개요) | Dashboard (대시보드) | this page, below |
| Access Control (접근 제어) | User Accounts (사용자 계정 관리) | [Users](users.md) |
| Hardware & Lines (하드웨어 및 회선) | Fax Modems (팩스 모뎀 장치) | [Fax lines](fax-lines.md) |
| | Network Printers (네트워크 프린터) | [System](system.md) |
| Inbound Routing (수신 라우팅) | DID Routing (DID 수신 라우팅) | [Fax lines](fax-lines.md) |
| | Fax to Email (팩스-이메일 라우팅) | [Fax lines](fax-lines.md) |
| | Barcode Routing (바코드 라우팅) | [Fax lines](fax-lines.md) |
| Content & Templates (콘텐츠 및 템플릿) | Fax Categories (팩스 카테고리 관리) | [Fax lines](fax-lines.md) |
| | Cover Pages (표지 템플릿 관리) | [Cover pages](covers.md) |
| Security & System (보안 및 시스템) | Blacklist (DynConf) (동적 차단 목록(DynConf)) | [Fax lines](fax-lines.md) |
| | System Audit Logs (시스템 감사 로그) | [System](system.md) |
| | System Functions (시스템 기능) | [System](system.md) |
| | SMTP Gateway (SMTP 게이트웨이) | [System](system.md) |
| | Storage & Cloud (스토리지 및 클라우드) | [Storage and scheduler](storage-scheduler.md) |
| | Scheduled Tasks (예약 작업) | [Storage and scheduler](storage-scheduler.md) |
| | SAML 2.0 SSO | [Authentication](authentication.md) |

The sidebar also has a **User Portal** button (back to the Inbox) and **Logout**.

!!! note "Entries that appear only when a feature is switched on"
    - **DID Routing** appears only when the environment variable `ENABLE_DID_ROUTING` is `1` or `true`.
    - **Barcode Routing** appears only when `ENABLE_BARDECODE_SUPPORT` (spelled exactly so) is `1` or `true`.

    The same variables are read by the HylaFAX receive hook, so the web service and the hook must use the same values. See the [HylaFAX setup](../../install/hylafax.md).

## The dashboard

`/admin` shows:

- Four cards: the number of **Fax Lines**, the number of **Users**, the HylaFAX version (**Backend Core**, from the HylaFAX installation, `unknown` if it cannot be read) and a **Scheduler** card.
- **Registered User Accounts**: name, user name, last login and e-mail of every account, with a **Manage Users** link.
- **Configured Modems**: every fax line with its current status (see [Fax lines](fax-lines.md)).
- Quick links to Users, Modems, DID Routes and Logs, and an **Administrator Workflow Guide** with three short hints.

!!! warning "Some dashboard badges are fixed text"
    *SYSTEM OPERATIONAL*, *Hardware Ready*, the **Scheduler** card (*APScheduler*, *Running*), *APScheduler Active*, *SQLAlchemy / SQLite* under **Database Engine**, and *Appliance Engine Online* in the top bar are always shown; they are not live checks. To see whether the scheduler is really running, open [Scheduled Tasks](storage-scheduler.md). The real database may be MySQL, MariaDB, PostgreSQL or SQLite.

## Pages of this manual

1. [Users](users.md): accounts, permissions, password rules, lockouts.
2. [Fax lines](fax-lines.md): modems, DID and barcode routes, categories, Fax to Email, call blocking.
3. [Cover pages](covers.md): what the screen can do today.
4. [System](system.md): System Functions, logs, SMTP gateway, network printers.
5. [Storage and scheduler](storage-scheduler.md): storage provider, retention, scheduled tasks.
6. [Authentication](authentication.md): SAML, passkeys, TOTP, login throttling, sessions.

For the user screens, see the [Inbox](../inbox.md).
