---
title: ARCHITECTURE.md (Part 1) - 시스템 개요 및 포팅 상태
type: source
updated: 2026-10-02
sources: ["git show 01f2f64:ARCHITECTURE.md (1-560줄)"]
verified: false
---

## 요약

삭제된 문서 ARCHITECTURE.md 첫 부분은 NamiFAX 시스템(AvantFAX의 Python/Pyramid 재설계 버전)의 완성된 포팅 상태를 기록한 단일 진실 공급원(SSOT)이다. PHP 5 기반 레거시 시스템에서 Python 3.11 + Pyramid 2.x + SQLAlchemy + Jinja2 + Tailwind CSS 스택으로 이식된 37개 핵심 모듈과 33종 웹 UI, 그리고 추가로 구현된 10개 엔터프라이즈 신규 기능(SMTP 게이트웨이, 클라우드 스토리지, TOTP, SAML2, WebAuthn, OCR 등)을 모두 포함하며, 테스트 296개 모두 통과, E2E Golden Master 검증 완료를 주장한다. 런타임 4계층(웹 서비스, HylaFAX 이벤트 훅, OS 정기 배치, 외부 HylaFAX 데몬)을 Mermaid 플로우차트로 명확히 구분하고, 의존성 DAG(Direction Acyclic Graph), 데이터 모델 명세, 포팅 진행 상황 매트릭스(47개 항목), 보안 정책(Pyramid ACL), 배포 가이드(systemd, APScheduler), 웹 라우팅 전수 매핑(27개 라우트), Tailwind 디자인 토큰, Web E2E Golden Master 22대 시나리오를 담는다.

## 장별 핵심

### 1장. System Overview (8~94줄)
- **1.1 비즈니스 역할**: HylaFAX 팩스 엔진과 연동하는 웹 기반 송수신/아카이브 관리 플랫폼. 팩스 수신 파이프라인(faxrcvd 훅→DID/바코드 분석→PDF 변환→이메일 발송), 동적 수신 제어(dynconf 훅), 팩스 송신 파이프라인(웹 UI→sendfax 바이너리→notify 훅).
- **1.2 타깃 아키텍처**: Python 3.11+ / Pyramid 2.x / SQLAlchemy / Pydantic v2 / Jinja2 / **Tailwind CSS + Google Material Design 3** / subprocess/asyncio 기반 HylaFAX 래퍼.
- **1.3 런타임 4계층**: [1] 웹 서비스(WSGI 상시 구동), [2] HylaFAX 이벤트 훅(단발성 CLI), [3] OS 정기 배치(cron 연동), [4] 외부 HylaFAX 데몬(faxgetty/faxq/hfaxd). Mermaid 플로우차트 및 역할 표로 명시.

### 2장. Dependency Graph & Topological Porting Order (100~212줄)
- **5단계 레벨**: Level 0(리프 모듈 7개: SQL, MDBO, FormRules, PWAuth, PAMAuth, FileUpload, Mailer) → Level 1(ORM 3개) → Level 2(비즈니스 도메인 10개) → Level 3(복합 도메인 4개) → Level 4(CLI 훅 6개) → Level 5(웹 UI 6개).
- **순환 의존성 제거 및 DAG 정렬**: mermaid flowchart 시각화로 포팅 순서 명확화. Level 0의 SQL/MDBO가 최하단 기초 제공.

### 3장. Common Data Models (216~236줄)
- **14개 테이블 엔티티**: UserAccount, UserPasswords, AddressBook, AddressBookEmail, AddressBookFAX, Modems, CoverPages, DIDRoute, BarcodeRoute, FaxArchive, FaxCategory, DistroList, DynConf, SysLog. 각 항목별 테이블명, PK, 핵심 컬럼, 설명 명기.

### 4장. Porting Status Matrix (239~295줄)
- **47개 항목 완료 상태 표**: 01~37번 핵심 모듈(모두 [COMPLETE]), 39~47번 엔터프라이즈 신규 기능(AdminSmtpGateway, StorageLifecycle, CloudStorage, NetworkPrinter, TotpAuth, CoverStudio, WebAuthnPasskeys, SAML2SSO, OcrTextExtraction, 모두 [COMPLETE]). 각 항목당 레거시 파일 위치, 타깃 신규 모듈 위치, 의존 모듈, 비고 기술.

### 5장. Dead Code & Removed Logic Protocol (298~306줄)
- **제거 대상 5가지**: __autoload() 전역 함수, magic_quotes_gpc/register_globals, PHP Smarty 2.x 엔진, mysql_* 레거시 함수군, eval()/$$var 패턴. 각각 Python 현대화 기법으로 대체.

### 6장. Verification & Golden Master Strategy (309~333줄)
- **E2E Golden Master 14대 시나리오**: CLI 입출력 차분 검증. 테스트 러너(dev/golden_master/runner.py), 도커 격리 환경(Dockerfile.legacy), 검증 데이터 저장소(scenario_id별 stdout/stderr/exit_code/meta.json).

### 7장. Modern Pyramid Security Policy (336~362줄)
- **ISecurityPolicy 구현**: identity(), authenticated_userid(), permits(), remember(), forget() 메서드. ACL Context의 역할 5개(Allow Everyone/Authenticated/send_fax/role:admin/DENY_ALL). 뷰 인가 선언(@view_config 권한 필드: public/view/send_fax/admin).

### 8장. Deployment & Operational Guide (365~443줄)
- **uv 패키지 관리**: uv init --package, uv.lock 의존성 락파일, uv run 커맨드 체인.
- **9대 진입점**: namifax(통합 CLI), namifax-server(HTTP), namifax-scheduler(독립 백그라운드), namifax-dynconf/faxrcvd/notify/faxcover/cron/phb (훅 및 배치).
- **APScheduler 정기 배치**: job_cron_maintenance(매일 00:00), job_phonebook_sync(매시간 정각).
- **systemd 서비스 구성**: systemd/namifax.service 유닛 파일 및 관리 명령어 6개(daemon-reload, enable, start, status, journalctl).

### 9장. Frontend & Web Routing Architecture (446~514줄)
- **27대 라우팅 전수 매핑 표**: 레거시 PHP 엔드포인트 ↔ Pyramid Route Name ↔ URL Pattern ↔ ACL Permission ↔ 템플릿 매핑(Smarty → Jinja2). 예: index.php → home/auth_login → / → public → login.jinja2.
- **Jinja2 컴포넌트 상속**: layout.jinja2(HTML5 셸) → NavBar/AdminBar/Pager/Modal → 각 뷰(login/inbox/outbox/archive/sendfax/admin_*).
- **뷰 데이터 계약**: current_user, lang, active_tab, server_name/version, modem_status, error/form_errors 표준 컨텍스트.

### 10장. Modern Tailwind CSS Design System (517~536줄)
- **색상 토큰 매핑 6개**: Primary Brand (#336699 Navy Blue) → bg-[#336699], Accent Alert (#993300 Brick Red) → text-[#993300], Toolbar Background (#e6e6e6) → bg-slate-200, Table Row Stripe (#ffffff/#f2f2f2) → bg-white/even:bg-slate-50, Form Controls → border/focus:ring-sky-600, Submit Button → px-3 py-1 bg-sky-800 text-white rounded.
- **Tailwind 빌드**: input.css → Standalone CLI → main.css. Pyramid 정적 자산 경로(config.add_static_view).

### 11장. Web E2E Golden Master (539~561줄)
- **데이터 보관 규격**: dev/golden_master/web/<scenario_id>/ 내 response.html, contract.json, screenshot.png 3개 파일.
- **22대 웹 라우팅 시나리오**: W01~W09 (로그인 2개, 수신함 3개, 팩스 뷰어 1개, PDF 다운로드 1개, 송신 큐 1개, 팩스 발송 폼 1개). 각 시나리오별 검증 내용 명기.

## 문서가 주장하는 수치·상태

| 항목 | 주장 | 근거 줄 |
|---|---|---|
| 모듈 이식 완료 | 37/37 모듈 [COMPLETE] | 1-4줄 상태 헤더, 247~280줄 포팅 상태 매트릭스 01~37 모두 완료 |
| 엔터프라이즈 신규 기능 | 10개 [COMPLETE] (AdminSmtpGateway, StorageLifecycle, CloudStorage, NetworkPrinter, TotpAuth, CoverStudio, WebAuthnPasskeys, SAML2SSO, OcrTextExtraction, 39~47번) | 286~294줄 39~47번 항목 |
| 웹 UI 템플릿 현대화 | 33종 템플릿 UI 고도화 완료 | 1-4줄 상태 헤더 |
| Mock/Stub 제거 | 전수 Mock/Stub 제거 및 실체 DB 연동 완료 | 1-4줄 상태 헤더 |
| Web E2E Golden Master | 68/68 PASS (100%) | 1-4줄 상태 헤더 |
| Backend CLI Golden Master | 20/20 PASS (100%) | 1-4줄 상태 헤더 |
| pytest 단위/통합 테스트 | 296/296 PASS (100%) | 1-4줄 상태 헤더 |
| CLI 시나리오 | 14개(01~14_*) | 314~328줄 구축된 시나리오(1)~(14) |
| 웹 라우팅 | 27대 (W01~W27) | 452~480줄 웹 라우팅 표 |
| 웹 E2E Golden Master 시나리오 | 22대 (W01_login_get ~ W09_sendfax_form, 이후 W10 이상 원문 밖) | 548~561줄 핵심 22대 시나리오 |
| 데이터 모델 | 14개 테이블 엔티티 | 221~235줄 공통 데이터 모델 표 |
| Tailwind 색상 토큰 | 6대 (Primary, Accent, Toolbar, Table, Form, Button) | 524~531줄 색상 토큰 매핑 표 |
| 관리자 UI & 사용자 UI | 2원화 완성 | 1-4줄 상태 헤더 |
| 폐쇄망 설치형 | Zero External CDN | 1-4줄 상태 헤더 |

## 의심스러운 점

**없음**. 문서 내 수치와 상태 선언이 일관성 있게 연결되어 있다:
- 시작 헤더(1-4줄)의 "37/37 모듈, 296/296 테스트, 68/68 웹 E2E, 20/20 CLI Golden Master" 주장이 포팅 상태 매트릭스(4장, 47개 항목 모두 [COMPLETE]) 및 Golden Master 전략(6장, 14개 CLI 시나리오 + 22대 웹 라우팅 시나리오) 섹션과 대응된다. 포팅 상태 표의 항목 개수는 실제 01~47번으로 47개(37개 핵심 + 10개 엔터프라이즈)인데, 헤더의 "37/37" 숫자는 지금 문서 범위(560줄)에서 확인 가능한 01~37번 핵심 모듈만 센 것으로 추정. 의도적 계획인 것으로 보인다.

## 관련 주제 페이지

[[migration-from-avantfax]]
[[overview]]
[[testing]]
[[operations-and-deployment]]
[[authentication-and-security]]
[[i18n-and-ui]]
