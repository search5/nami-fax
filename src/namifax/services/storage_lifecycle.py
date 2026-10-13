import os
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from namifax.db.missing import resolve_db
from namifax.services.cloud_storage import fax_object_key, provider_from_config


@dataclass
class StorageLifecyclePolicy:
    purge_tiff_after_days: int = 7        # Purge local TIFF if valid PDF exists after N days (0 = immediate)
    full_retention_days: int = 365        # Purge entire fax record & files after N days (0 = keep forever)
    remote_sync_delete: bool = True        # Also purge object on remote S3 when fax is deleted
    delete_remote_tiff_only: bool = False  # Purge only TIFF objects in remote cloud storage


class StorageLifecycleService:
    """Enterprise Storage Lifecycle Engine for NamiFAX."""

    def __init__(
        self,
        db: Any = None,
        storage_provider: Optional[Any] = None,
        archive_dir: Optional[str] = None,
    ) -> None:
        self.db = resolve_db(db, "StorageLifecycleService")
        self.storage_provider = storage_provider
        self.archive_dir = archive_dir or os.environ.get(
            "NAMIFAX_ARCHIVE_DIR", "/var/spool/hylafax/archive"
        )

    def purge_local_tiffs(self, days_old: int = 7, should_stop=None) -> Dict[str, Any]:
        """Purge raw TIFF files where a valid, non-empty PDF counterpart exists."""
        if not os.path.exists(self.archive_dir):
            return {"purged_count": 0, "reclaimed_bytes": 0}

        cutoff_timestamp = time.time() - (days_old * 86400)
        purged_count = 0
        reclaimed_bytes = 0

        for root, _, files in os.walk(self.archive_dir):
            if should_stop and should_stop():
                break
            if "fax.tif" in files:
                tif_path = os.path.join(root, "fax.tif")
                pdf_path = os.path.join(root, "fax.pdf")

                # Safeguard 1: PDF must exist and be non-empty (> 0 bytes)
                if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
                    continue

                # Safeguard 2: Check modification time
                try:
                    stat = os.stat(tif_path)
                    if stat.st_mtime <= cutoff_timestamp:
                        file_size = stat.st_size
                        os.remove(tif_path)
                        purged_count += 1
                        reclaimed_bytes += file_size
                except OSError:
                    continue

        return {
            "purged_count": purged_count,
            "reclaimed_bytes": reclaimed_bytes,
        }

    def purge_expired_faxes(self, retention_days: int, use_remote: bool = True, should_stop=None,
                            tiff_only: bool = False) -> Dict[str, Any]:
        """Delete faxes archived more than ``retention_days`` ago: database row, files and remote copy.

        The age is the fax's ``archstamp`` (as the legacy cron's ``-d`` uses) and its files are found through
        the stored ``faxpath``. ``retention_days <= 0`` keeps everything.
        """
        if retention_days <= 0:
            return {"purged_faxes_count": 0}

        from namifax.services import archive_orm
        from namifax.services.archive_base import FaxPDFArchive

        cutoff = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d %H:%M:%S")
        purged = 0
        for fid in archive_orm.fids_older_than(self.db, cutoff):
            if should_stop and should_stop():
                break
            arc = FaxPDFArchive(db=self.db)
            if not arc.load_fax(fid):
                continue
            faxpath = arc._on_disk(arc.dbdata.get("faxpath") or "") if arc.dbdata.get("faxpath") else ""

            if use_remote and self.storage_provider:
                try:
                    if tiff_only:                 # REMOTE_PURGE_TIFF_ONLY: the remote PDF stays
                        self.storage_provider.delete_file(fax_object_key(fid, "fax.tif"))
                    else:
                        self.storage_provider.delete_fax(fid)
                except Exception:
                    pass          # an unreachable bucket must not keep local data forever

            if arc.delete_fax():
                self._remove_leftovers(faxpath)
                purged += 1
        return {"purged_faxes_count": purged}

    def _remove_leftovers(self, faxpath: str) -> None:
        """Remove what is left of a fax directory, but only inside the archive."""
        if not faxpath:
            return
        root = os.path.realpath(self.archive_dir)
        target = os.path.realpath(faxpath)
        if target != root and target.startswith(root + os.sep) and os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)

    def run_lifecycle(self, policy: StorageLifecyclePolicy, should_stop=None) -> Dict[str, Any]:
        """Execute complete storage lifecycle sequence based on active policy."""
        tiff_res = self.purge_local_tiffs(days_old=policy.purge_tiff_after_days, should_stop=should_stop)
        fax_res = self.purge_expired_faxes(
            retention_days=policy.full_retention_days, use_remote=policy.remote_sync_delete, should_stop=should_stop,
            tiff_only=policy.delete_remote_tiff_only,
        )

        return {
            "tiffs_purged": tiff_res["purged_count"],
            "reclaimed_bytes": tiff_res["reclaimed_bytes"],
            "faxes_purged": fax_res["purged_faxes_count"],
            "executed_at": datetime.now().isoformat(),
        }

    def run_saved_policy(self, should_stop=None) -> Optional[Dict[str, Any]]:
        """Run the policy an administrator saved on the storage page (``None`` when none was saved).

        Nothing runs on the displayed defaults: deleting faxes automatically has to be an explicit choice.
        The remote provider comes from the saved cloud settings; with ``LOCAL`` there is no remote copy.
        """
        from namifax.services.system_config import SystemConfigService

        cfg = SystemConfigService(self.db)
        tiff_days, keep_days = cfg.get("storage_purge_tiff_days", ""), cfg.get("storage_retention_days", "")
        if not tiff_days and not keep_days:
            return None

        if self.storage_provider is None:
            self.storage_provider = provider_from_config(cfg)
        policy = StorageLifecyclePolicy(
            purge_tiff_after_days=int(tiff_days or 7),
            full_retention_days=int(keep_days or 0),
            remote_sync_delete=cfg.get("storage_remote_sync_delete", "1") == "1",
            delete_remote_tiff_only=cfg.get("storage_remote_tiff_only", "0") == "1",
        )
        return self.run_lifecycle(policy, should_stop)
