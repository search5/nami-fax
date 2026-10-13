---
title: ARCHITECTURE.md 뒤 절반(561-1069줄) 요약
type: source
updated: 2026-10-02
sources: ["git show 01f2f64:ARCHITECTURE.md (561-1069줄)"]
verified: false
---

## 요약

이 원문 절반은 NamiFAX 웹 프런트엔드와 데이터 계층의 최종 이식 상태를 기술한다. 68개 Golden Master 웹 시나리오(W01-W68)와 형식 명세, 전면 리브랜딩, 24개 언어 i18n 지원, DB 계층의 실체화, 원본 MySQL/MariaDB 호환성, 인증·보안 구조, 17가지 방면의 보안·기능 결함 수정 사항을 포함한다. 핵심은 모든 뷰가 100% DB와 연결되고, 웹과 CLI 모두 Golden Master 검증을 무회귀로 통과한다는 것.

## 장별 핵심

### 11장 Web UI Porting Status Matrix (웹 프런트엔드 포팅 현황)
- 68개 웹 라우트/템플릿을 4개 상태(`[PENDING]`, `[IN_PROGRESS]`, `[FFI_BRIDGED]`, `[COMPLETE]`)로 추적 (11.1)
- 68개 웹 시나리오 `W01-W68`: 로그인, 수신함, 발송함, 아카이브, 주소록, 관리자 대시보드, 모달, AJAX, 헬퍼, 업로드 (11.2~11.4)
- CLI 배치 도구 5개 시나리오 (OCR 임포트, 썸네일, 사용자 임포트, 블랙리스트, 재라우팅) (11.3)
- 웹 차분 검증 러너: HTTP 응답코드, DOM 계약, 폼 필드, 버튼 일치 검증 (11.4, 라인 53-59)

### 12장 Web UI Porting Status Matrix (웹 포팅 현황 표)
- 레이아웃·인증·메인(인박스·발송·아웃박스·아카이브)·주소록·설정·관리자·모달·AJAX·헬퍼·업로드·액션 21개 그룹 (라인 69-132)
- 모든 라우트/템플릿이 레거시 파일(`header.tpl`, `inbox.php` 등)과 신규 Pyramid 뷰/Jinja2 템플릿을 1:1 대응
- 상태: 모두 `[COMPLETE]`라고 표기(라인 72-132)

### 13장 Form Structure & JS Dynamic States Golden Master Specification
- 44개 핵심 웹 시나리오에 엄격 폼 구조 및 자바스크립트 동적 상태 계약 적용 (라인 136-151)
- 검증 항목: 정확한 `<form>` 개수, 입력/버튼 개수, 필드/버튼 순서, JS 이벤트 트리거와 영향받는 필드 (13.1)
- 결과: E2E Golden Master 68/68 PASS, pytest 374/374 PASS (13.2)

### 14장 NamiFAX Full System Rebranding (리브랜딩)
- 33개 Jinja2 템플릿의 제목, 로고, 푸터를 `NamiFAX`로 전환 (라인 159-161)
- 12개 Pyramid 뷰 컨트롤러의 컨텍스트 `title` 및 이메일 발신자명 전환 (라인 162-166)
- 원본 골든 마스터 기준 데이터 100% 보존하면서 신규 화면 E2E 68/68 PASS, 단위 테스트 374/374 PASS (14.3)

### 15장 Internationalization (i18n) & Localization Architecture
- Pyramid `pyramid.i18n`, Babel, Jinja2 `i18n` 익스텐션 표준 스택 (라인 172-180)
- 24개 로케일 지원: `ar`, `bg`, `cs`, `de`, `el`, `en`, `es`, `fr`, `hu`, `it`, `ja`, `ko`, `nl`, `no`, `pl`, `pt_BR`, `pt_PT`, `ro`, `ru`, `sr`, `sv`, `tr`, `zh_CN`, `zh_TW` (15.1 라인 185-188)
- 한국어 416개 UI 토큰 100% 정밀 번역, 영문 Golden Master 무회귀 보증 (15.1 라인 189-191)

### 16장 Full Stub Materialization & Core Service Integration (스텁 실체화)
- LibTIFF/HylaFAX 바이너리 + Pillow 하이브리드: `tiff2pdf`, `faxinfo`, `convert2pdf`, `static_preview`, `pdf_preview` (16.1)
- 웹 뷰 계층 DB 서비스 전면 연동: 관리자(`AFUserAccount`), 모뎀(`FaxModem`), 주소록(`AFAddressBook`), 배포 목록(`DistributionList`), 아카이브(`FaxPDFArchive`) (16.2)
- 잔여 스텁/모의 데이터/가짜 폴백: 0건 (16.3)
- 회귀 검증: E2E 68/68 PASS, 단위·통합 402/402 PASS (16.4)

### 17장 데이터 계층과 시작 절차 (최종 상태)
#### 17.1 구성
- Pyramid `pyramid_tm` → `request.dbsession`, CLI `cli_session()` (라인 249-250)
- 서비스는 `db=Session` 파라미터로 받음, 원시 SQL 문자열 경로 없음 (라인 256-258)

#### 17.2 시작 절차 (`db/bootstrap.ensure_schema`)
- SQLite 새 DB: 0번 판단, 1번 보정, 2~4번 채택·마이그레이션 (라인 269-276)
- MySQL/MariaDB/PostgreSQL: 같은 경로, 단 보정 단계 생략
- 기본 데이터(카테고리 3, 표지 2)는 새 DB에만 (라인 273)

#### 17.3 테이블·모델·리비전
- 13개 테이블, 24개 Alembic 리비전 (0001~0024), 모두 SQLite/MySQL/MariaDB/PostgreSQL 공통 (라인 283-300)

#### 17.4 이식성 규칙
- 모든 `String`에 길이, 날짜는 ISO 텍스트, NULL 정렬 통일, 명시 id는 PostgreSQL 시퀀스 처리 (라인 303-308)
- 검증: 서버 DB 테스트가 PostgreSQL 16, MySQL 8.4, MariaDB 11에서 실행 (라인 308)

#### 17.5 인증·보안 구조
- 토큰 쿠키 하나(`namifax_session`, `NamiFaxSecurityPolicy`) (라인 312)
- 흐름 상태용 세션(`namifax_flow`, 서명 쿠키, HttpOnly, SameSite=Lax) (라인 313)
- 2FA(TOTP): 사용자 설정, 틀린 코드 DB 집계, 5회 실패 시 15분 잠금 (라인 314)
- SAML: 이메일로만 매칭, JIT 계정은 관리자 아님 (라인 315)
- 비밀값 암호화: `Fernet` 토큰, 키 필수(없으면 평문 거부) (라인 316)
- 비밀번호 변경 강제: `wasreset`, 만료, 최초 로그인 계정은 `/pwdexpired`로 이동 (라인 317)

#### 17.5a 기존 AvantFAX 설치 이전 (호환성)
- 원본 DB 그대로 사용, 추가만 하고 삭제/변경 없음 (라인 322)
- 절차 5단계, 검증 테스트 포함 (`test_legacy_database_compat.py`) (라인 336-338)
- 알려진 한계: PHP 세션/로그인 쿠키 불일치 (라인 340)

#### 17.5b 팩스 접근 권한 (16개 뷰)
- 슈퍼유저는 모든 팩스, 일반 사용자는 자신의 모뎀·카테고리·발송 팩스만 (라인 350)
- 슈퍼유저 받은 팩스함도 "설정된 모뎀/라우트만"(원본 규칙) (라인 352)
- 패리티 검증: 원본 실행으로 7종 계정 35건 테스트 (라인 359)

#### 17.5c 답장과 연락처 업로드
- 답장 `/sendfax?refax=<fid>`: 권한 확인, 상대 번호 채움, 원본 PDF 첨부 (라인 363-366)
- 작업 수정 `/ajax/faxalter`: 원본 항목(수신처, 우선순위, 모뎀, 시도, 만료, "지금"/예약), 로그인한 사용자 이름으로 실행 (라인 367)
- vCard 업로드: 결과/오류 화면 표시, 앞 카드 ORG 누수 해결 (라인 370)

#### 17.5d 팩스 전송 명령 (`sendfax_command.py`)
- 원본 `submit_fax()` 6개 시나리오 명령줄과 비교 테스트 (라인 373-374)
- 우선순위·재시도·만료·예약·TSI·발신자 정보·알림 모두 HylaFAX에 전달 (라인 376-377)

#### 17.5e 비밀번호 찾기 (`/forgot`)
- 이메일로 새 임시 비밀번호 발송, `wasreset` 켜기, 로그인 후 강제 변경 (라인 383-384)
- 발송 실패 시 기존 비밀번호 되돌림 (라인 385)

#### 17.6 명령과 설정
- 9개 메인 명령(`serve`, `scheduler`, `createuser`, `reset-2fa`, `encrypt-secrets`, `import-archive`, `cron`, `faxrcvd`, `notify`, `faxcover` 등) (라인 390-398)
- 스토리지 라이프사이클: 관리자가 정책 저장했을 때만 실행 (라인 400)

#### 17.7 테스트 구조
- 테스트 DB별 격리, 고정 `NAMIFAX_SECRET_KEY`, Pyramid `testapp` 픽스처 (라인 404-405)
- 서버 DB 테스트: 환경변수 기반(`NAMIFAX_TEST_PG_URL` 등) (라인 406)
- E2E: 빈 DB로 앱 띄워 관리자 생성, 로그인, 주요 페이지 확인 (라인 406)
- 원본 PHP 대조: 실제 PHP 5.6 + MDB2 + MariaDB 실행 (`avantfax-legacy-test` 이미지) (라인 409)
- 골든 마스터: 임시 SQLite DB(데모 데이터), 68개 시나리오, 폼 검사, 비밀번호 변경 실제 흐름 검증 (라인 410)

#### 17.8 제거된 로직 (Dead Code)
- 죽은 PHP 파일: `rubrica.php`, `rubrica_edit.php` (라인 418)
- PHP→Python 브리지 24개 파일 제거 (라인 419)
- 레거시 DB 계층, 임의 SQL, 서비스 mock (라인 420-421)

#### 17.9 열린 항목 (`[NEEDS_CLARIFICATION]`)
- ~~SQLite 데모 계정~~ → 해결: 데모 옵트인 (라인 426)
- ~~기존 MySQL DB~~ → 해결: 17.5a (라인 427)
- ~~모뎀·카테고리 없는 계정 범위~~ → 해결: 원본 실행 검증 (라인 428)

### 18장 발견·수정한 결함 요약 (17가지)
- 보안: SQL 인젝션, 문자열 이스케이프, 불리언 `'False'` 텍스트, MD5 해시 로그인, SAML NameID, TOTP 무제한 대입, 비밀값 평문, 로그인 권한 없음, 팩스 권한 검사 없음 (라인 441-467)
- 기능: 답장·출력함·비밀번호 변경·보관함·작업 수정·vCard 업로드·팩스 발송 옵션·비밀번호 찾기 (라인 468-489)
- 호환: 원본 DB 테이블·컬럼·날짜·경로·권한·DID (라인 465-474)

### 17.6 전수 조사 결함 목록 처리 (36개 항목)
- 관리자, 목록, 보기, 배포 그룹, 훅, 설정, 보안, 화면, 운영 (라인 496-509)
- 의도적 차이: 관리자 판정, WWWUSER 기본값, POST+CSRF (라인 508)

## 문서가 주장하는 수치·상태

| 항목 | 수치·상태 | 라인 |
|---|---|---|
| 웹 Golden Master 시나리오 | 68개 (W01-W68) | 11.2 |
| CLI 배치 시나리오 | 5개 (15~19) | 11.3 |
| 핵심 폼 구조 검증 시나리오 | 44개 | 13.2 |
| E2E Golden Master 테스트 결과 | 68/68 PASS | 13.2, 14.3, 16.4 |
| pytest 단위·통합 테스트 결과 | 374/374 PASS (또는 402/402 PASS) | 13.2, 16.4 |
| 웹 라우트/템플릿 포팅 현황 | 모두 `[COMPLETE]` | 12장 |
| 지원 로케일 | 24개 | 15.1 |
| 한국어 UI 토큰 | 416개 100% 번역 | 15.1 |
| DB 테이블 | 13개 | 17.3 |
| Alembic 리비전 | 0001~0024 (24개) | 17.3 |
| 발견·수정한 결함 | 17가지 방면, 36~55개 항목 | 18장 |
| 서비스 DB 테스트 대상 | PostgreSQL 16, MySQL 8.4, MariaDB 11 | 17.4 |
| 팩스 접근 권한 패리티 테스트 | 7종 계정, 35건 | 17.5b |
| 팩스 전송 명령 시나리오 | 6개 | 17.5d |
| 제거된 PHP 파일 | 26개 이상 (브리지 24 + 죽은 코드) | 17.8 |
| 신규 서비스/뷰 모듈 | 10개 이상 | 17.6 표 |
| 입력창 placeholder 번역 대상 | 40곳 | 17.7 |
| vCard 업로드 개선 항목 | 4개 | 17.5c |

## 의심스러운 점

### 수치 불일치

1. **pytest 통과 개수**
   - 13.2에서: "374/374 PASS"
   - 16.4에서: "402 Passed, 0 Failed" (신규 TDD 테스트 40개 추가)
   - 해석: 후속 작업 중 28개 테스트 추가로 374→402 증가. 13.2는 그 시점 기준일 가능성.

2. **단위/통합 테스트 수치 재언급**
   - 11.4 라인 58에서: "374/374 PASS"라고 별도 표기
   - 16.4 라인 233에서: "402개 테스트"
   - 같은 문서 안에서 동일한 스위트를 두 가지로 표기한 듯.

3. **폼 검증 범위**
   - 13.2에서: "44개 핵심 웹 시나리오"
   - 그런데 전체 68개 웹 시나리오 중 44개만 폼 구조 검증이라는 뜻인지, 확실하지 않음.

### 기능 중복·혼동 가능 영역

1. **"모든 라우트 COMPLETE" vs 실제 상태**
   - 12장 매트릭스에서 모든 항목이 `[COMPLETE]`로 표기
   - 하지만 17.9 "열린 항목"이 3개 있음(다만 모두 "해결됨"으로 표기)
   - 모순 아님, 하지만 "완료"의 정의가 명확하지 않음(테스트 통과 의미인지, 코드 작성 의미인지).

2. **서버 DB 검증 범위**
   - 17.4에서 "서버 DB 테스트가 PostgreSQL 16, MySQL 8.4, MariaDB 11에서 실행"
   - 하지만 17.7에서 "환경변수가 있을 때만 실행"
   - 즉, CI 환경에는 이 테스트가 없을 수 있음(선택적).

## 관련 주제 페이지

- [[testing]] — Golden Master 프레임워크, E2E 검증, 원본 대조
- [[database-and-migrations]] — DB 계층, Alembic, 레거시 호환성
- [[authentication-and-security]] — 2FA, SAML, 팩스 권한, 비밀번호 정책
- [[i18n-and-ui]] — 24개 로케일, 한국어 번역, Jinja2 템플릿
- [[hylafax-integration]] — 훅, 명령, 전송 파이프라인
- [[known-gaps-and-decisions]] — 제거된 로직, 의도적 차이
