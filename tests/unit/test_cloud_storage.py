import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from src.namifax.services.cloud_storage import (
    StorageConfig,
    LocalStorageProvider,
    S3CompatibleStorageProvider,
    CloudStorageManager,
)


class TestCloudStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.local_root = os.path.join(self.temp_dir, "archive")
        os.makedirs(self.local_root, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_local_storage_provider_upload_and_download(self):
        provider = LocalStorageProvider(base_dir=self.local_root)

        src_file = os.path.join(self.temp_dir, "sample.pdf")
        with open(src_file, "wb") as f:
            f.write(b"LOCAL_PDF_CONTENT")

        # Upload
        ok = provider.upload_file(src_file, "2026/10/01/fax10/fax.pdf")
        self.assertTrue(ok)
        dest_file = os.path.join(self.local_root, "2026/10/01/fax10/fax.pdf")
        self.assertTrue(os.path.exists(dest_file))

        # Download
        downloaded = os.path.join(self.temp_dir, "downloaded.pdf")
        ok_dl = provider.download_file("2026/10/01/fax10/fax.pdf", downloaded)
        self.assertTrue(ok_dl)
        with open(downloaded, "rb") as f:
            self.assertEqual(f.read(), b"LOCAL_PDF_CONTENT")

        # Delete file
        ok_del = provider.delete_file("2026/10/01/fax10/fax.pdf")
        self.assertTrue(ok_del)
        self.assertFalse(os.path.exists(dest_file))

    def test_local_storage_provider_delete_fax(self):
        provider = LocalStorageProvider(base_dir=self.local_root)
        fax_dir = os.path.join(self.local_root, "2026", "10", "01", "fax20")
        os.makedirs(fax_dir, exist_ok=True)
        with open(os.path.join(fax_dir, "fax.tif"), "wb") as f:
            f.write(b"TIFF")

        ok = provider.delete_fax(20)
        self.assertTrue(ok)
        self.assertFalse(os.path.exists(fax_dir))

    def test_local_storage_test_connection(self):
        provider = LocalStorageProvider(base_dir=self.local_root)
        res = provider.test_connection()
        self.assertTrue(res["success"])
        self.assertEqual(res["provider"], "LOCAL")

    @patch("boto3.client")
    def test_s3_storage_provider_operations(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        cfg = StorageConfig(
            storage_type="S3",
            endpoint_url="https://s3.ap-northeast-2.amazonaws.com",
            region_name="ap-northeast-2",
            bucket_name="my-fax-bucket",
            access_key="AKIA12345",
            secret_key="SECRET12345",
            prefix="faxes/",
        )
        provider = S3CompatibleStorageProvider(cfg)

        src_file = os.path.join(self.temp_dir, "doc.pdf")
        with open(src_file, "wb") as f:
            f.write(b"S3_CONTENT")

        # Upload
        ok = provider.upload_file(src_file, "2026/fax30/doc.pdf")
        self.assertTrue(ok)
        mock_s3.upload_file.assert_called_once_with(src_file, "my-fax-bucket", "faxes/2026/fax30/doc.pdf")

        # Download
        target_path = os.path.join(self.temp_dir, "s3_dl.pdf")
        ok_dl = provider.download_file("2026/fax30/doc.pdf", target_path)
        self.assertTrue(ok_dl)
        mock_s3.download_file.assert_called_once_with("my-fax-bucket", "faxes/2026/fax30/doc.pdf", target_path)

        # Delete file
        ok_del = provider.delete_file("2026/fax30/doc.pdf")
        self.assertTrue(ok_del)
        mock_s3.delete_object.assert_called_once_with(Bucket="my-fax-bucket", Key="faxes/2026/fax30/doc.pdf")

    @patch("boto3.client")
    def test_s3_storage_provider_delete_fax(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        # Mock listing objects under fax prefix
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "faxes/fax40/fax.tif"},
                {"Key": "faxes/fax40/fax.pdf"},
                {"Key": "faxes/fax40/thumb.png"},
            ]
        }

        cfg = StorageConfig(
            storage_type="S3",
            bucket_name="my-fax-bucket",
            prefix="faxes/",
        )
        provider = S3CompatibleStorageProvider(cfg)
        ok = provider.delete_fax(40)
        self.assertTrue(ok)

        mock_s3.delete_objects.assert_called_once()
        args, kwargs = mock_s3.delete_objects.call_args
        self.assertEqual(kwargs["Bucket"], "my-fax-bucket")
        self.assertEqual(len(kwargs["Delete"]["Objects"]), 3)

    @patch("boto3.client")
    def test_s3_storage_test_connection_success(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.head_bucket.return_value = {}

        cfg = StorageConfig(
            storage_type="S3",
            bucket_name="my-fax-bucket",
        )
        provider = S3CompatibleStorageProvider(cfg)
        res = provider.test_connection()
        self.assertTrue(res["success"])
        self.assertIn("Successfully connected", res["message"])

    def test_cloud_storage_manager_factory(self):
        manager = CloudStorageManager()
        local_p = manager.get_provider(StorageConfig(storage_type="LOCAL"))
        self.assertIsInstance(local_p, LocalStorageProvider)


if __name__ == "__main__":
    unittest.main()
