# Storage and scheduler

**Storage & Cloud** (`/admin/storage`, *Superuser only*) holds the storage provider and the retention policy. **Scheduled Tasks** (`/admin/scheduler`, *Administrator Console* or *Superuser*) runs the housekeeping jobs, including the one that applies the retention policy.

## Storage & Cloud

The page has two forms.

### Storage Lifecycle Policies

| Field | Meaning |
|---|---|
| **Purge Local TIFFs After (Days)** | A received fax is kept as `fax.tif` and `fax.pdf`. TIFF files older than this many days are deleted, but only where a non-empty `fax.pdf` exists beside them. `0` means right away. Range 0 to 3650, default 7. The age is the file's modification time. |
| **Full Fax Retention (Days)** | Every fax whose archive timestamp is older than this many days is deleted completely: the database record, its files and the remote copy. `0` means keep forever. Range 0 to 7300, default 365. |
| **Synchronize remote cloud object deletion on fax purge** | When on (default), the remote copy in the S3 bucket is deleted along with the fax. If the bucket cannot be reached, the local fax is deleted anyway. |

Press **Save Lifecycle Policy** (*Lifecycle policy saved successfully.*).

!!! warning "Saving the policy switches automatic deletion on"
    The fields show 7 and 365 as defaults, but **nothing is deleted until you save the policy once**. After that the *Apply the retention policy* task of the scheduler (on by default, daily at 00:00) deletes faxes older than the retention days, and **Run now** does the same at once. Deleted faxes are not recoverable from NamiFAX, so [download a backup](system.md#database-archive-backup) first and choose the days with care. Use `0` for retention if faxes must be kept forever.

The TIFF purge and the cleanup look for files in the folder `NAMIFAX_ARCHIVE_DIR` (default `/var/spool/hylafax/archive`). If your fax archive is elsewhere (`AVANTFAX_ARCHIVE`), set `NAMIFAX_ARCHIVE_DIR` to the same folder.

### Cloud Storage Backend

**Storage Provider** has two choices:

- **Local Filesystem (Default)**: faxes stay in the archive folder on this server. There is nothing else to fill in.
- **Amazon S3 / MinIO / Ceph**: any S3-compatible object store.

For S3, fill in:

| Field | Meaning |
|---|---|
| **Endpoint URL (MinIO / S3 Compatible)** | Leave empty for Amazon S3; for MinIO or Ceph enter its URL, for example `http://minio.internal:9000`. |
| **Region** | For example `us-east-1`. |
| **Bucket Name** | The bucket to use. |
| **Access Key ID**, **Secret Access Key** | Credentials. If either is empty, the default credential lookup of the AWS library is used instead (environment, instance role and so on). Leave the secret empty when saving to keep the stored one; it is stored encrypted, which needs `NAMIFAX_SECRET_KEY` (or `secret.key`) to be set. |
| **Key Prefix** | An optional folder prefix such as `faxes/`. |

- **Save Storage Config** stores the settings (*Cloud storage configuration saved successfully.*).
- **Test Connection** checks the values currently in the form without saving them, and reports whether the bucket can be reached. A blank secret uses the stored one.

What S3 is used for: when a fax is **received**, the receive hook copies its `fax.tif` and `fax.pdf` to the bucket under `<prefix>fax<id>/`. A failure is only written to the [system log](system.md#system-logs) and does not stop reception. Faxes received before S3 was switched on are not uploaded afterwards. The remote copy is removed when the retention policy purges a fax.

## Scheduled Tasks

The scheduler runs inside the NamiFAX web service. It is started with the service unless the environment variable `NAMIFAX_ENABLE_SCHEDULER` is set to something other than `1`/`true`.

### The scheduler state box

At the top, a coloured box tells you what is going on:

| Message | Meaning |
|---|---|
| *A scheduler is running (last seen n seconds ago)* | A scheduler process has reported in during the last 180 seconds. |
| *The scheduler is starting…* / *…is stopping…* | A change is being applied; it takes a few seconds. |
| *The scheduler is stopped* | An administrator stopped it. Nothing runs by itself, but **Run now** still works. |
| *No scheduler is running* | No process has reported in. Start the web service with `NAMIFAX_ENABLE_SCHEDULER=1` (the default); until then tasks run only with **Run now**. |

The button in the box reads **Stop the scheduler** or **Start the scheduler**. Stopping is remembered in the database, so it survives a restart of the web service.

### The four tasks

Each task has a tick box (enabled or not), its settings, a status line and a **Run now** button. All settings are saved together with the **Save** button at the bottom (*Scheduled tasks saved. A running scheduler picks the change up within a minute.*). Times are written `HH:MM` on a 24-hour clock; a wrong time is refused with a message and the old time is kept.

| Task (label) | What it does | Default | Settings |
|---|---|---|---|
| **Clean the temporary folder** | Deletes temporary files older than the given days, every day. | On, 00:00, older than 1 day | **Time (HH:MM)**, **Older than (days)** (1 to 3650) |
| **Move old faxes to the archive** | Faxes in the inbox older than the given days are moved to the archive. Nothing is deleted. | **Off**, 01:00, older than 30 days | **Time (HH:MM)**, **Older than (days)** (1 to 3650) |
| **Apply the retention policy** | Runs the TIFF purge and the retention period saved on the Storage page. Without a saved policy it removes nothing. The box shows the saved policy (*TIFF n / keep n days*). | On, 00:00 | **Time (HH:MM)** |
| **Export the address book to HylaFAX** | Writes the address book as a HylaFAX phonebook, repeatedly. | On, every 60 minutes | **Every (minutes)** (1 to 10080) |

### Run now, Stop, status

- **Run now** starts the task at once, in the background, whether or not it is enabled and even if the scheduler is stopped. If it is already running you get *This task is already running.*
- While a task runs its line shows *Running — started …* and a **Stop** button. Stop asks the task to stop; it stops at the next safe point (*Stopping…* meanwhile).
- When a task has finished, its line shows **Last run** with the time and a summary, for example how many faxes were moved or removed, or `failed: …` with the reason. A task that has never run shows *Has not run yet.* Every run is also written to the [system log](system.md#system-logs).
- The status blocks refresh by themselves while a task runs.
