"""Received faxes are uploaded to S3 when the administrator chose S3; the lifecycle can keep only the remote PDF."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy as sa

from namifax.cli import faxrcvd as mod
from namifax.models import FaxArchive
from namifax.services import cloud_storage
from namifax.services.cloud_storage import S3CompatibleStorageProvider, StorageConfig
from namifax.services.storage_lifecycle import StorageLifecyclePolicy, StorageLifecycleService
from namifax.services.system_config import SystemConfigService


class FakeProvider:
    def __init__(self, fail=False):
        self.uploads, self.deleted_files, self.deleted_faxes, self.fail = [], [], [], fail

    def upload_file(self, local_path, remote_key):
        if self.fail:
            raise RuntimeError("bucket unreachable")
        self.uploads.append((os.path.basename(local_path), remote_key))
        return True

    def delete_file(self, remote_key):
        self.deleted_files.append(remote_key)
        return True

    def delete_fax(self, fid):
        self.deleted_faxes.append(fid)
        return True


def _receive(tmp_path, session, provider, storage="S3"):
    tiff = tmp_path / "fax00123.tif"
    tiff.write_bytes(b"mock tiff")
    finfo = {"Sender": "Newco", "Pages": "1", "Received": "2026:10:01 10:05:09", "CallID1": "5557777"}
    cfg = SystemConfigService(session)
    cfg.set("cloud_storage_type", storage)
    cfg.set("cloud_prefix", "nami")

    def fake_pdf(src, dst):
        with open(dst, "wb") as f:
            f.write(b"%PDF-1.4 x")

    with patch.object(mod, "ARCHIVE", str(tmp_path / "archive")), \
            patch.object(mod, "faxinfo", return_value=finfo), \
            patch.object(mod, "tiff2pdf", side_effect=fake_pdf), patch.object(mod, "static_preview"), \
            patch.object(mod, "send_mail"), patch.object(mod, "bardecode", return_value=None), \
            patch.object(mod, "ocr_faxcontent", return_value=""), \
            patch("namifax.services.cloud_storage.CloudStorageManager.get_provider", return_value=provider):
        return mod.run_faxrcvd(["faxrcvd.py", str(tiff), "ttyS0", "c1", "none"], session=session)


def _fid(session):
    return session.execute(sa.select(FaxArchive.fid).order_by(FaxArchive.fid.desc())).scalars().first()


def test_s3_receive_uploads_tiff_and_pdf_under_the_fid_key(tmp_path, dbsession):
    p = FakeProvider()
    assert _receive(tmp_path, dbsession, p) == 0
    fid = _fid(dbsession)
    assert sorted(p.uploads) == sorted([("fax.tif", f"fax{fid}/fax.tif"), ("fax.pdf", f"fax{fid}/fax.pdf")])


def test_an_upload_failure_does_not_fail_the_receive_and_is_logged(tmp_path, dbsession):
    with patch("namifax.common.helpers.avantfaxlog") as log:
        assert _receive(tmp_path, dbsession, FakeProvider(fail=True)) == 0
    assert _fid(dbsession) is not None
    assert any("upload" in str(c.args[0]).lower() for c in log.call_args_list)


def test_local_storage_uploads_nothing(tmp_path, dbsession):
    p = FakeProvider()
    assert _receive(tmp_path, dbsession, p, storage="LOCAL") == 0
    assert p.uploads == []


def test_provider_prefix_is_applied_to_the_key():
    prov = S3CompatibleStorageProvider(StorageConfig(storage_type="S3", bucket_name="b", prefix="nami"))
    assert prov._resolve_key(cloud_storage.fax_object_key(7, "fax.pdf")) == "nami/fax7/fax.pdf"


def test_delete_fax_does_not_touch_other_faxes_sharing_the_number_prefix():
    prov = S3CompatibleStorageProvider(StorageConfig(storage_type="S3", bucket_name="b"))
    client = MagicMock()
    client.list_objects_v2.return_value = {}
    prov._client = client
    assert prov.delete_fax(1) is True
    prefixes = [c.kwargs["Prefix"] for c in client.list_objects_v2.call_args_list]
    assert prefixes == ["fax1/"]              # "fax1" alone would also match fax10, fax100...
    client.delete_objects.assert_not_called()


def _expired_fax(session, tmp_path):
    path = tmp_path / "archive" / "d" / "n" / "1"
    path.mkdir(parents=True)
    (path / "fax.tif").write_bytes(b"t")
    (path / "fax.pdf").write_bytes(b"%PDF")
    old = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d %H:%M:%S")
    row = FaxArchive(faxpath=str(path), pages=1, inbox=0, archstamp=old)
    session.add(row)
    session.flush()
    return row.fid


@pytest.mark.parametrize("tiff_only", [True, False])
def test_remote_tiff_only_policy(tmp_path, dbsession, tiff_only):
    dbsession.execute(sa.delete(FaxArchive))
    fid = _expired_fax(dbsession, tmp_path)
    p = FakeProvider()
    svc = StorageLifecycleService(db=dbsession, storage_provider=p, archive_dir=str(tmp_path / "archive"))
    res = svc.run_lifecycle(StorageLifecyclePolicy(full_retention_days=365, delete_remote_tiff_only=tiff_only))
    assert res["faxes_purged"] == 1
    if tiff_only:
        assert p.deleted_files == [f"fax{fid}/fax.tif"] and p.deleted_faxes == []
    else:
        assert p.deleted_faxes == [fid] and p.deleted_files == []


def test_saved_policy_reads_the_remote_tiff_only_setting(dbsession, tmp_path):
    cfg = SystemConfigService(dbsession)
    cfg.set("storage_retention_days", "365")
    cfg.set("storage_remote_tiff_only", "1")
    svc = StorageLifecycleService(db=dbsession, storage_provider=FakeProvider(), archive_dir=str(tmp_path))
    with patch.object(StorageLifecycleService, "run_lifecycle", return_value={}) as run:
        svc.run_saved_policy()
    assert run.call_args.args[0].delete_remote_tiff_only is True
