---
title: Google Cloud Storage 구현 보류 메모
type: source
updated: 2026-10-13
sources: [docs/ko/dev/gcs-on-hold.md, docs/en/dev/gcs-on-hold.md]
verified: false
---

> 원본은 `docs/ko/dev/gcs-on-hold.md`(2026-10-13 에 MkDocs 구조로 이동. 이전 경로 `docs/FUTURE_GCS_STORAGE.md`)다. 영문판 `docs/en/dev/gcs-on-hold.md` 가 있으나 이 요약은 한국어 원문 기준이다.

## 요약

2026-10-02 에 Admin > Storage 화면과 코드에서 GCS(Google Cloud Storage) 항목을 제거했고, 나중에 다시 추가할 때 참고하려고 제거 전 상태와 선택지를 남긴 메모. 실제 GCS 계정으로는 한 번도 시험하지 않았다.

## 핵심 내용

### 제거 전 상태 (커밋 `53ed28b` 시점)

**화면**
- Storage Provider 드롭다운에 `GCS` 가 있었고, 고르면 S3 와 같은 입력란(엔드포인트, 리전, 버킷, 액세스 키, 시크릿, 접두사)을 "HMAC Access Key / HMAC Secret" 라벨과 안내문으로 보였다.
- 영어 안내문: "Google Cloud Storage is reached through its S3-compatible interface: use the endpoint https://storage.googleapis.com and an HMAC key (Cloud Storage > Settings > Interoperability)." 한국어 번역도 같은 뜻(엔드포인트 `https://storage.googleapis.com`, 인증은 HMAC 키).
- 템플릿 구조: `#cloud-fields` 묶음 + `data-for="S3"` / `data-for="GCS"` 라벨 + `static/js/storage.js`(제공자 선택에 따라 보임/숨김).

**코드**
- GCS 전용 코드는 없었다. `CloudStorageManager.get_provider` 가 `("S3", "GCS")` 를 모두 `S3CompatibleStorageProvider`(boto3)로 보냈다.
- 엔드포인트가 비어 있으면 AWS 로 접속하는 문제가 있었다(결함 보고서 R3D-05; 보고서는 삭제됨, 커밋 `01f2f64` 에서 복원).
- 실제 GCS 계정으로는 시험한 적 없다.

### 다시 추가할 때의 선택지
1. **S3 호환(XML API)**: 엔드포인트 `https://storage.googleapis.com` + HMAC 키로 기존 boto3 코드를 재사용. 엔드포인트 기본값 채우기와 실제 GCS 연결 시험이 필요하고, 일부 S3 기능(버전, 일부 헤더)은 GCS 가 다르게 동작한다.
2. **GCS 전용(권장)**: `google-cloud-storage` 라이브러리 + 서비스 계정 JSON 키 + Project ID. 별도 `GcsStorageProvider` 와 서명된 URL(`generate_signed_url`)이 필요하다. 명세: 계획서 3.8, 명세 41 §2.2.
3. 어느 쪽이든: `StorageLifecycleService` 의 원격 삭제 동기화(`cloud_storage_type in (...)` 두 곳)에 새 유형 추가, 저장된 설정 키(`cloud_*`)와 시크릿(`cloud_secret_key`) 처리, `tests/unit/test_storage_page_fields.py` 의 GCS 시험 복원.

## 문서가 주장하는 수치·상태

- 제거 시점 2026-10-02, 제거 전 기준 커밋 `53ed28b`.
- GCS 실계정 시험 0회. 구현 선택지 2가지 중 GCS 전용 방식을 권장.

## 낡았을 가능성이 큰 부분

- 제거 전 상태는 커밋 `53ed28b` 시점이다. 그 뒤 Storage 코드가 바뀌었으므로 복구 전에 현재 코드와 대조해야 한다.
- R3D-05(엔드포인트가 비면 AWS 로 접속)가 이후 고쳐졌는지는 이 문서가 말해 주지 않는다.
- 명세 "계획서 3.8, 명세 41 §2.2" 는 삭제된 문서라 git 이력에서 복원해야 한다.
- `google-cloud-storage` 버전·`generate_signed_url` 동작은 문서에 특정 버전이 없다.

## 관련 주제 페이지

[[scheduler-and-storage]] [[known-gaps-and-decisions]]
