---
title: HylaFAX & AvantFAX 연동 아키텍처 및 스토리지 관리
type: source
updated: 2026-10-02
sources: ["git show 614f7b0:docs/hylafax_avantfax_integration_architecture.md (삭제됨; 옮긴 내용은 [[hylafax-operations-notes]], 나머지는 [[hylafax-integration]], [[scheduler-and-storage]])"]
verified: false
---

> 원본 문서는 2026-10-02 에 저장소에서 삭제했다(위 `git show` 로 읽는다). 위키에 없던 부분(스풀 이동, 파일 구조, 첨부 형식, print-to-fax)은 [[hylafax-operations-notes]] 로 옮겼다. 이 요약은 삭제 시점의 문서가 주장한 바이며 현재 코드와 다를 수 있다.

## 요약

HylaFAX(C/C++ 팩스 통신 데몬)과 NamiFAX(Python/Pyramid 웹 관리 시스템) 간의 상호작용을 CLI 바이너리 호출, 이벤트 훅, 공유 스풀 파일시스템, TCP 소켓의 4가지 채널로 기술한 명세서. 팩스 발송/수신 파이프라인, HylaFAX 훅(`faxrcvd`, `notify`, `dynconf`) 구현 패턴, 레거시 Cron 기반 수명주기 관리에서 APScheduler 전환 아키텍처, 다중 클라우드(AWS S3/GCP GCS) 연동 및 원격 객체 스토리지 라이프사이클 동기화를 상세히 설명. 수신 팩스 1통당 파일 구성(원본 TIFF, PDF, 페이지별 PNG 썸네일) 및 네트워크 프린터 양방향 연동(수신 팩스 → 실물 프린터 출력, PC 인쇄 → NamiFAX 가상 프린터 수신)도 포함.

## 핵심 내용

**§2 전체 연동 아키텍처**
- HylaFAX와 NamiFAX는 4가지 채널(CLI 호출, 훅, 공유 스풀, TCP 4559)로 유기적 결합
- 웹 인터페이스(Pyramid) ↔ CLI 훅(`faxrcvd`, `notify`, `dynconf`) ↔ HylaFAX 데몬(`hfaxd`, `faxq`, `faxgetty`)

**§2.1~2.5 팩스 흐름 및 훅**
- 발송(Outbound): 웹 UI → `sendfax` CLI → HylaFAX `/sendq` 스풀
- 수신(Inbound): 모뎀 ← TIFF `/recvq` 저장 → `faxrcvd` 훅 실행 → 원본 복사, PDF 변환, 아카이브 이동
- 발송 결과 알림(`notify`), 동적 수신거부(`dynconf`), 실시간 모뎀 상태 조회(`faxstat` + TCP 4559)

**§3 수신 스풀 경로(`/var/spool/hylafax/recvq`) 변경 방법**
- 심볼릭 링크 또는 바인드 마운트로 물리 스토리지 변경 가능
- AvantFAX 아카이브 디렉터리는 설정으로 완전 자유(레거시 `local_config.php`, NamiFAX `production.ini`)

**§4 레거시 Cron 기반 파일 청소(`avantfaxcron.php`)**
- 임시 파일 정리(`-t`), 수신함 자동 아카이빙(`-i`), 아카이브 영구 삭제(`-d`) 세 가지 파라미터
- 기본값: 임시 2일, 수신함 30일, 아카이브 90일

**§5 수신 팩스 1통의 파일 저장 구조**
- HylaFAX 수신 단계: 단일 멀티페이지 TIFF 파일(`fax000000042.tif`)
- AvantFAX/NamiFAX 아카이브 단계: 날짜/발신번호/ID별 디렉터리(`faxes/YYYY/MM/DD/<발신번호>/<FaxID>/`)
- 저장 파일: `fax.tif`, `fax.pdf`, `thumb.png`, `preview0.png` ~ `preview(N-1).png` (페이지당 1개)

**§6 스토리지 부하 및 신규 기능 연계**
- 문제: 페이지별 PNG 파일 폭증으로 아이노드 고갈 및 중복 스토리지
- 신규 로드맵: S3 호환 오브젝트 스토리지(#8), TIFF 자동 정리(#9)

**§7 Cron → APScheduler 전환**
- 레거시: OS crontab 수동 편집 필요
- NamiFAX: 웹 UI(`/admin/maintenance`)에서 동적 설정, 즉시 실행, 이력 대시보드

**§8 HylaFAX 훅(`faxrcvd`, `notify`, `dynconf`) 구현 상세**
- 훅 파일명/경로는 HylaFAX 설정(`FaxRcvdCmd`, `NotifyCmd`, `DynamicConfig`)으로 변경 가능
- 훅 실행 파일 형식: Python 스크립트, 컴파일 바이너리, Bash 래퍼 등 모두 지원
- 패턴 A(동일 서버, CLI 래퍼), 패턴 B(컨테이너 분리, HTTP 웹훅)

**§9 멀티 클라우드 연동 및 3단계 무결성 보장**
- 1단계: HylaFAX 통신 라이프사이클 보장(훅 실행 = 수신 완료 확인)
- 2단계: TIFF 포맷 헤더/에러 파라미터 무결성 검증
- 3단계: 로컬 PDF 변환 완료 후 클라우드 업로드(`boto3`/GCS 서비스 계정)

**§9.4 스토리지 수명주기 청소와 클라우드 원격 객체 삭제 연동**
- 원격 삭제 메커니즘: `archive_retention_days` 초과 시 `DeleteObject` API 호출
- 원격 수명주기 정책: `REMOTE_KEEP_FOREVER`, `REMOTE_SYNC_LIFECYCLE`, `REMOTE_PURGE_TIFF_ONLY`
- 선별적 원격 TIFF 삭제로 클라우드 비용 70~80% 절감

**§10 팩스 발송 시 첨부파일 지원 포맷**
- 기본 지원: PDF(Ghostscript), PostScript, TIFF(G3/G4), 평문 텍스트
- 이미지(`png`, `jpg`): PDF/PostScript로 래핑
- 오피스 문서: 클라이언트 사전 변환 권장 또는 LibreOffice Headless 자동 변환

**§11 OS별 Print-to-Fax 아키텍처**
- 핵심 과제: 수신 팩스 번호를 인쇄 대화상자로부터 전달받기
- CUPS 네트워크 프린터(`ipp://서버:631/printers/namifax`) + 문서 내 태그 인식(`[[FAX: 번호]]`)

## 문서가 주장하는 수치·상태

- 레거시 Cron 기본값: 임시 파일 2일, 수신함 30일, 아카이브 90일
- 수신 팩스 1통 파일 구성: 1페이지(4개 파일), 5페이지(8개 파일), 30페이지(33개 파일), 100페이지(103개 파일)
- 팩스 표준 해상도: 204×98dpi(표준) 또는 204×196dpi(고해상도)
- PDF 변환 후 TIFF 선별 삭제 시 로컬 디스크 사용량 최대 80% 이상 절감 가능
- 원격 S3/GCS의 대용량 TIFF만 삭제할 경우 클라우드 비용 70~80% 절감

## 낡았을 가능성이 큰 부분

- S3/GCS 연동 및 APScheduler 기반 수명주기 엔진은 문서 작성 시점(2026-10)에 "설계됨" 상태이지만, 실제 구현 및 배포 상태는 변경되었을 수 있음
- Cron 기반 청소 메커니즘 언급(§4, §7)은 이미 삭제되었을 수 있음(2026-10-02 개발 상태 기준)
- 문서의 요청 방법(예: 표지 템플릿 HTML/CSS, CUPS PPD 설정)과 실제 배포 환경의 웹 서버(nginx/apache) 설정이 불일치할 수 있음

## 관련 주제 페이지

[[architecture-and-modules]] [[scheduler-and-storage]] [[hylafax-integration]] [[authentication-and-security]] [[operations-and-deployment]]
