# NamiFAX Manual

NamiFAX is a web front end for the HylaFAX fax server. It is written in Python (Pyramid, SQLAlchemy). Administrators manage users, permissions, fax lines (modems) and categories in a browser, and users can view, send and archive faxes from anywhere.

## Where to start

| I want to... | Read |
|---|---|
| Learn what NamiFAX is and what it does | [Overview](guide/overview.md) |
| Install it for the first time | [Getting started](install/index.md) → [Preparing the HylaFAX server](install/hylafax-server.md) → [HylaFAX setup](install/hylafax.md) |
| Move from an existing AvantFAX 3.x | [Migrating from AvantFAX 3.x](install/migration.md) |
| Check a server before going live | [Operations checklist](install/operations-checklist.md) |
| Receive, send and search faxes | [User manual](manual/index.md) |
| Manage users, fax lines and storage | [Administrator manual](manual/admin/index.md) |

!!! warning "What has been tested"
    This repository has not been tested against a real HylaFAX, CUPS or S3. Before going live, walk through [HylaFAX setup](install/hylafax.md) and the [operations checklist](install/operations-checklist.md) on a test server.
