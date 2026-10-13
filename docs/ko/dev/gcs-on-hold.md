# Google Cloud Storage (GCS) - 보류 메모

2026-10-02 에 Admin > Storage 화면과 코드에서 GCS 항목을 제거했습니다. 나중에 다시 추가할 때 참고하려고 내용을 남깁니다.

## 제거 전 상태 (커밋 53ed28b 시점)
- 화면: Storage Provider 드롭다운에 `GCS` 가 있었고, 고르면 S3 와 같은 입력란(엔드포인트, 리전, 버킷, 액세스 키, 시크릿, 접두사)을
  "HMAC Access Key / HMAC Secret" 라벨과 안내문으로 보여 주었습니다.
  - 안내문: "Google Cloud Storage is reached through its S3-compatible interface: use the endpoint https://storage.googleapis.com
    and an HMAC key (Cloud Storage > Settings > Interoperability)."
  - 한국어: "Google Cloud Storage는 S3 호환 인터페이스로 연결합니다. 엔드포인트는 https://storage.googleapis.com, 인증은 HMAC 키
    (Cloud Storage > 설정 > 상호 운용성)를 사용하십시오."
  - 템플릿 구조: `#cloud-fields` 묶음 + `data-for="S3"` / `data-for="GCS"` 라벨 + `static/js/storage.js` (제공자 선택에 따라 보임/숨김).
- 코드: GCS 전용 코드는 없었고 `CloudStorageManager.get_provider` 가 `("S3", "GCS")` 를 모두 `S3CompatibleStorageProvider`(boto3)로
  보냈습니다. 엔드포인트가 비어 있으면 AWS 로 접속하는 문제가 있었습니다(결함 보고서 R3D-05; 보고서는 삭제됨, 커밋 01f2f64 에서 복원 가능).
- 실제 GCS 계정으로는 한 번도 시험하지 않았습니다.

## 다시 추가할 때의 선택지
1. **S3 호환(XML API) 방식**: 엔드포인트 `https://storage.googleapis.com` + HMAC 키. 기존 boto3 코드를 재사용. 엔드포인트 기본값 채우기와
   실제 GCS 에서의 연결 시험이 필요합니다. 일부 S3 기능(예: 버전, 일부 헤더)은 GCS 가 다르게 동작합니다.
2. **GCS 전용 방식(권장)**: `google-cloud-storage` 라이브러리 + 서비스 계정 JSON 키 + Project ID. 별도 `GcsStorageProvider` 와
   서명된 URL(`generate_signed_url`)이 필요합니다. 명세: 계획서 3.8, 명세 41 §2.2.
3. 어느 쪽이든: `StorageLifecycleService` 의 원격 삭제 동기화(`cloud_storage_type in (...)` 두 곳)에 새 유형을 추가하고,
   저장된 설정 키(`cloud_*`)와 시크릿(`cloud_secret_key`) 처리, `tests/unit/test_storage_page_fields.py` 의 GCS 시험을 되살립니다.
