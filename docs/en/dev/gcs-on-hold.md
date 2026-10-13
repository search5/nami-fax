# Google Cloud Storage (GCS) - On-Hold Notes

On 2026-10-02 the GCS entries were removed from the Admin > Storage screen and from the code. The details are kept here for reference when GCS is added back later.

## State before removal (as of commit 53ed28b)
- Screen: the Storage Provider dropdown had `GCS`, and selecting it showed the same input fields as S3 (endpoint, region, bucket, access key, secret, prefix)
  with the labels "HMAC Access Key / HMAC Secret" and a help text.
  - Help text: "Google Cloud Storage is reached through its S3-compatible interface: use the endpoint https://storage.googleapis.com
    and an HMAC key (Cloud Storage > Settings > Interoperability)."
  - Korean: "Google Cloud Storage는 S3 호환 인터페이스로 연결합니다. 엔드포인트는 https://storage.googleapis.com, 인증은 HMAC 키
    (Cloud Storage > 설정 > 상호 운용성)를 사용하십시오."
  - Template structure: a `#cloud-fields` group + `data-for="S3"` / `data-for="GCS"` labels + `static/js/storage.js` (shows or hides them depending on the selected provider).
- Code: there was no GCS-specific code; `CloudStorageManager.get_provider` routed both `("S3", "GCS")` to `S3CompatibleStorageProvider` (boto3). When the endpoint was empty, it connected to AWS (defect report R3D-05; the report has been deleted and can be restored from commit 01f2f64).
- It was never tested with a real GCS account.

## Options when adding it back
1. **S3-compatible (XML API) approach**: endpoint `https://storage.googleapis.com` + HMAC key. Reuses the existing boto3 code. Needs a default value filled in for the endpoint and a connection test against a real GCS. Some S3 features (for example, versioning and some headers) behave differently on GCS.
2. **GCS-native approach (recommended)**: the `google-cloud-storage` library + a service account JSON key + Project ID. Requires a separate `GcsStorageProvider` and signed URLs (`generate_signed_url`). Spec: plan section 3.8, spec 41 §2.2.
3. Either way: add the new type to the remote-delete synchronization in `StorageLifecycleService` (two places with `cloud_storage_type in (...)`),
   handle the stored setting keys (`cloud_*`) and the secret (`cloud_secret_key`), and bring back the GCS tests in `tests/unit/test_storage_page_fields.py`.
