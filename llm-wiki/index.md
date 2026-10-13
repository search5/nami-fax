# NamiFAX LLM Wiki - 목차

질문이 있으면 이 목차에서 관련 페이지를 찾아 읽는다. 규칙은 [[CLAUDE]] 에 있고, 변경 이력은 [[log]] 에 있다.
**topics/** 는 코드와 대조해 쓴 종합(주장마다 `[코드]`/`[문서]`/`[추정]` 표시), **sources/** 는 원본 문서가 주장하는 바의 요약(`verified: false`, 낡았을 수 있음)이다.
문서와 코드가 다르면 topics/ 의 `> 모순:` 블록을 본다.

## 주제 (topics/)

- [[overview]] - 시스템이 무엇이고 어떻게 맞물리는지(웹, HylaFAX 훅, 정기 작업), 기술 스택, 코드 트리, 위키 안내
- [[architecture-and-modules]] - src/namifax 의 계층과 모듈 책임, 진입점, 라우트·뷰 구조
- [[database-and-migrations]] - 지원 DB 4종, 스키마 부트스트랩과 Alembic, 모델·테이블, 기존 AvantFAX DB 이어 쓰기 규칙
- [[authentication-and-security]] - 비밀번호 해시, 2단계 인증, 패스키, SAML, 권한 모델, 비밀 저장, 세션·CSRF, 현재 한계
- [[scheduler-and-storage]] - APScheduler 정기 작업과 관리자 화면(정지·시작·작업별 중지), 로컬/S3 스토리지와 수명주기
- [[hylafax-integration]] - HylaFAX 훅·송신·수신 처리와 모뎀 상태, 실제 HylaFAX 로 시험하지 못한 범위와 대체 검증
- [[hylafax-operations-notes]] - HylaFAX 쪽 운영 지식(수신 스풀 이동, faxqclean, 팩스 한 통의 파일 구조), 발송 첨부 형식, print-to-fax 구현과 목표 설계
- [[i18n-and-ui]] - 다국어(번역 절차와 규칙), Jinja2·Tailwind(CSS 재빌드), 레이아웃 규칙
- [[testing]] - 시험 구성과 실행법, 서버 DB 시험, 삭제된 골든 마스터의 영향, 시험이 지키는 규칙
- [[operations-and-deployment]] - 실행·배포(ini, 환경 변수, 웹 서버, systemd, cron), 운영 점검
- [[migration-from-avantfax]] - 기존 AvantFAX 3.x 에서 이어 쓰는 방법과 달라 보이는 점, 원본 소스 복원법
- [[known-gaps-and-decisions]] - 알려진 미구현·한계와 과거 결함의 현재 상태, 의도한 제거·보류와 이유

## 원본 문서 요약 (sources/)

### 구조·이력 문서

- [[architecture-md-part1]] - ARCHITECTURE.md (Part 1) - 시스템 개요 및 포팅 상태
- [[architecture-md-part2]] - ARCHITECTURE.md 뒤 절반(561-1069줄) 요약
- [[db-layer-refactor-log]] - DB 계층 전환 기록 (아키텍처 스냅샷)
- [[hylafax-integration-architecture]] - HylaFAX & AvantFAX 연동 아키텍처 및 스토리지 관리
- [[new-features-plan]] - NamiFAX 신규 엔터프라이즈 기능 구현 계획
- [[cover-upload-plan]] - 팩스 표지 업로드·찾아보기 계획(구현 전, 결정 대기 3건)
- [[porting-gaps]] - 레거시 대비 미구현·결함 목록 (전수 조사)
- [[agents-md-legacy-instructions]] - 삭제된 AI 작업 규칙 (AGENTS.md 레거시 지침)

### 운영·이전 가이드

- [[install-hylafax]] - HylaFAX 연동 설치 가이드
- [[operations-checklist]] - 운영 전·운영 중 점검 목록
- [[migrating-from-avantfax3]] - AvantFAX 3.x에서 NamiFAX로 옮기기
- [[setup-email2fax]] - E-mail to fax with Postfix 설정
- [[future-gcs-storage]] - Google Cloud Storage 구현 보류 메모

### 감사·결함 보고(과거 시점)

- [[legacy-divergence-audit]] - NamiFAX 시스템 전수 정밀 감사 보고서
- [[defects-report-summary]] - 삭제된 결함 보고서 종합 요약
- [[defects-rounds-1-2]] - 이미 확인된 결함과 1·2라운드 상세 요약
- [[defects-rounds-3]] - 3라운드 결함 요약 (A-H)
- [[defects-rounds-4-5]] - 4·5라운드 결함 요약

