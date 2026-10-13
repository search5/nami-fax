---
title: NamiFAX 신규 엔터프라이즈 기능 구현 계획
type: source
updated: 2026-10-02
sources: ["git show 61c3663:docs/NEW_FEATURES_PLAN.md (삭제됨; 현재 상태는 [[scheduler-and-storage]], [[authentication-and-security]], [[known-gaps-and-decisions]])"]
verified: false
---

> 원본 문서는 2026-10-02 에 저장소에서 삭제했다(위 `git show` 로 읽는다). 이 요약은 삭제 시점의 문서가 주장한 바이며 현재 코드와 다를 수 있다.

## 요약

레거시 AvantFAX(PHP 5 + MySQL + HylaFAX) 대비 NamiFAX(Python/Pyramid)에서 구현할 9대 엔터프라이즈 기능의 비교 분석 및 설계 로드맵. 기존 코어 시스템 완성(24개 다국어 지원, E2E Golden Master 68개 검증 완료) 후 추가할 보안, 스토리지, 클라우드 연동, 사용자 편의성 기능들을 3단계 마일스톤(A: 인프라·스토리지 안정화, B: 클라우드·하드웨어, C: 엔터프라이즈 인증)으로 구성. 각 기능별 레거시 한계, 신규 아키텍처, DB 스키마 확장안, 단계별 구현 로드맵 및 무회귀 검증 원칙 기술.

## 핵심 내용

**§1 개요**
- 현재 NamiFAX 코어 시스템 완성(E2E Golden Master 68개, pytest 291개 통과)
- 신규 9대 기능 도입으로 현대적 기업 환경의 보안, 스토리지 효율성, 클라우드 연동, 사용자 편의성 강화

**§2 9대 기능 비교 매트릭스**
1. 네트워크 프린터 추가: 레거시 제한(간접·CUPS 이름만) → 신규 완전(IPP, LPD, RAW 9100 직접 지원)
2. TOTP 로그인: 레거시 미지원 → 신규 RFC 6238(QR 코드, 백업 복구 코드)
3. WebAuthn 로그인: 레거시 미지원 → 신규 FIDO2/Passkeys(Touch ID, Face ID, YubiKey)
4. SSO 로그인: 레거시 Apache REMOTE_USER만 → 신규 SAML 2.0(Entra ID, Okta, Keycloak, ADFS)
5. 팩스 커버 업로드: 레거시 제한(메타데이터만) → 신규 완전(웹 드래그앤드롭, 썸네일, 동적 필드)
6. PDF 자동 변환: 레거시 부분(시스템 바이너리 의존) → 신규 완전(Pillow/PyMuPDF 이중화)
7. 외부 SMTP 설정: 레거시 미지원(설정 파일 하드코딩) → 신규 완전(관리자 UI, 연결 테스트)
8. 오브젝트 스토리지: 레거시 미지원 → 신규 완전(AWS S3, GCS, MinIO, R2 등 멀티 클라우드)
9. 스토리지 수명주기: 레거시 제한(전체 삭제만) → 신규 완전(PDF 변환 후 TIFF 선별 정리, 원격 동기화)

**§3.1 네트워크 프린터 연동**
- 아웃바운드: 수신 팩스 → 실물 프린터 자동 출력(RAW 9100, LPR/LPD, IPP/IPPS)
- 인바운드: 클라이언트 인쇄 → NamiFAX 가상 프린터(CUPS 네트워크 공유) → 팩스 자동 발송
- 문서 내 태그 인식(`[[FAX: 번호]]`) 및 웹 드래프트 폴백

**§3.2 TOTP 2단계 인증**
- 사용자 활성화 플로우: QR 코드 발급 → Authenticator 스캔 → 6자리 검증
- 로그인 인터셉터: ID/PW 검증 → 2FA 챌린지 → 완전 세션 발급
- 8개 1회용 백업 복구 코드(Emergency Recovery Codes) 발급

**§3.3 WebAuthn 로그인**
- 디바이스 등록: `/settings/security`에서 보안 키(YubiKey, Touch ID 등) 등록
- 패스워드리스 로그인: 지문/Face ID/보안키 인증으로 원클릭 로그인
- 2차 인증(2FA) 수단으로도 활용 가능

**§3.4 SSO 엔터프라이즈 통합**
- SAML 2.0 Service Provider 구현(`python3-saml`)
- 호환 IdP: Microsoft Entra ID, Okta, Keycloak, ADFS, PingIdentity, Google Workspace
- 핵심 엔드포인트: `/metadata`, `/login`, `/acs`(Assertion Consumer Service), `/sls`(Single Logout)
- JIT(Just-In-Time) 사용자 자동 프로비저닝

**§3.5 팩스 커버 템플릿 스튜디오**
- 레거시 한계: 파일 업로드 기능 없음, 서버 CLI로 직접 복사 필요
- 신규: 드래그앤드롭 업로드, 실시간 썸네일 미리보기, 동적 치환 변수 가이드
- 템플릿 형식 다양화: PostScript, HTML/CSS(Jinja2), PDF 지원

**§3.6 고품질 PDF 실시간 자동 변환**
- 하이브리드 변환 엔진: LibTIFF `tiff2pdf`(우선) → Pillow 폴백(내장 보장)
- 자동 파이프라인: TIFF 수신 → PDF 생성 → 페이지별 PNG 썸네일 래스터화 → OCR 텍스트 추출

**§3.7 관리자 웹 기반 SMTP 이메일 서버 설정**
- 레거시 한계: `local_config.php` 상수 수동 코딩, 오류 시 이메일 유실
- 신규: 호스트, 포트, TLS/SSL, 인증정보 설정 + "연결 및 테스트 메일 발송" 진단

**§3.8 멀티 클라우드 오브젝트 스토리지 연동**
- 추상화 인터페이스: `upload_file()`, `download_file()`, `delete_file()`, `generate_presigned_url()`
- 지원 프로바이더: AWS S3, MinIO, SeaweedFS, GCS(HMAC 또는 서비스 계정), Cloudflare R2, Ceph
- 업로드 파이프라인: 팩스 수신/발신 완료 시 로컬 저장과 동시에 백그라운드 워커로 S3/GCS 자동 업로드

**§3.9 통합 스토리지 라이프사이클**
- 로컬 디스크 최적화: PDF 변환 및 S3/GCS 업로드 완료 후 원본 TIFF 선별 삭제
- 원격 수명주기 정책: 하이브리드 보존, 동기화 삭제, 선별적 TIFF 삭제
- APScheduler 기반 자동 백그라운드 실행(매일 자정 등)

**§4 DB 스키마 확장**
- `SystemSettings`: SMTP 호스트, 포트, TLS/SSL, 인증정보
- `NetworkPrinters`: 프린터 이름, 호스트, 포트, 프로토콜, 용지 규격
- `FaxCoverTemplates`: 표지 파일, 타입, 썸네일, 기본값 여부
- `UserTOTP`: 시크릿 키, 백업 코드(JSON), 활성화 여부, 확인 시각
- `UserWebAuthn`: Credential ID, 공개키, Sign Count, 장치명
- `UserSAMLIdentity`: IdP Entity ID, NameID, Session Index, 이메일

**§5 단계별 구현 로드맵**
- **Phase A(완료)**: PDF 자동 변환, SMTP 설정, TIFF 정리 정책
- **Phase B(완료)**: 네트워크 프린터, 팩스 커버 스튜디오, S3 호환 오브젝트 스토리지
- **Phase C(완료)**: TOTP 2FA, WebAuthn Passkeys, SAML 2.0 SSO, OCR 검색 엔진

**§6 무회귀 검증 및 호환성 원칙**
- 신규 기능 추가 후에도 기존 68개 E2E Golden Master 및 291개 pytest 100% PASS 유지
- 신규 기능은 초기 설정 시 비활성화/기본 모드로 기존 로컬 환경에 영향 없음
- 각 기능을 서비스 계층으로 모듈화하여 특정 기능 장애가 팩스 송수신 코어에 영향 미치지 않도록(Fail-Safe)

## 문서가 주장하는 수치·상태

- 현재 상태: 코어 시스템 100% 완성, 24개 다국어 지원, E2E Golden Master 68개 검증, pytest 291개 통과
- 신규 기능 복잡도: 1(중간), 2(중간), 3(보통~높음), 4(중간), 5(중간), 6(보통), 7(낮음~중간), 8(중간~높음), 9(보통)
- 원격 TIFF만 삭제할 경우 클라우드 비용 70~80% 절감

## 낡았을 가능성이 큰 부분

- 문서 작성 시점(2026-10) 기준으로 3단계 Phase A/B/C 모두 "완료" 상태로 표기되어 있으나, 실제 구현 및 배포 상태가 다를 수 있음
- SAML 2.0 구현(§3.4)에서 언급한 IdP(Entra ID, Okta 등)는 각 환경의 메타데이터 형식 및 속성명이 상이할 수 있음
- GCS HMAC 방식의 호환성이 Google Cloud의 정책 변경에 따라 영향받을 수 있음
- OCR 검색 엔진(Spec 47, Phase C)의 Tesseract 언어 패키지 및 한국어 인식 정확도는 배포 환경별로 다를 수 있음

## 관련 주제 페이지

[[overview]] [[authentication-and-security]] [[scheduler-and-storage]] [[hylafax-integration]] [[database-and-migrations]] [[operations-and-deployment]] [[known-gaps-and-decisions]]
