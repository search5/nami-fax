---
title: 이미 확인된 결함과 1·2라운드 상세 요약
type: source
verified: false
sources:
  - git show 01f2f64:docs/numfax-defects-details/known.md
  - git show 01f2f64:docs/numfax-defects-details/round1-admin.md
  - git show 01f2f64:docs/numfax-defects-details/round1-core.md
  - git show 01f2f64:docs/numfax-defects-details/round1-security.md
  - git show 01f2f64:docs/numfax-defects-details/round1-ui.md
  - git show 01f2f64:docs/numfax-defects-details/round1-user.md
  - git show 01f2f64:docs/numfax-defects-details/round2-acct.md
  - git show 01f2f64:docs/numfax-defects-details/round2-ops.md
  - git show 01f2f64:docs/numfax-defects-details/round2-parity.md
  - git show 01f2f64:docs/numfax-defects-details/round2-recv.md
  - git show 01f2f64:docs/numfax-defects-details/round2-send.md
updated: 2026-10-02
---

## 요약

초기 확인(known.md 16건)과 1·2라운드 조사(121+105=226건)에서 당시 보고된 구체적 결함입니다. 1라운드는 영역별 점검(관리자, 코어/DB, 보안, UI, 사용자 화면), 2라운드는 업무 흐름별 점검(수신, 발송, 계정/권한, 레거시 패리티, 운영/테스트)을 수행했습니다.

## 이미 확인된 결함 (K01~K16, 16건)

당시 직접 확인한 초기 결함들:

- **K01**: 관리자 4개 화면(smtp, printers, storage, saml)에서 request.db 부재로 저장 미반영
- **K02**: 앱에 세션 팩토리 미등록(request.session 25곳 사용)
- **K03**: AFUserAccount에 load_by_username 등 핵심 메서드 부재 (WebAuthn, SAML provision 호출 불가)
- **K04**: SAML 응답 서명/Audience/NotOnOrAfter/InResponseTo/Issuer 검증 없음 (위조 로그인 가능)
- **K05**: SAML 관리자 설정(SystemConfig saml_*)을 views/saml.py가 읽지 않음
- **K06**: CloudStorageManager가 관리 화면에만 사용, 팩스 업로드/다운로드에 미연결
- **K07**: CoverStudioService를 호출하는 곳 없음
- **K08**: TOTP 활성화 UI 경로 없음(/login/totp?setup=1 미처리, QR/백업코드 화면 없음, qrcode 의존성 없음)
- **K09**: WebAuthn DDL이 MySQL 전용 문법 → SQLite에서 실패 후 은폐(except pass)
- **K10**: login_post_view에 admin/password 하드코딩 우회 (시드 비밀번호 평문 "password")
- **K11**: /inbox 템플릿의 /archive/move/{id}, /delete/{id} 링크 404
- **K12**: faxrcvd.py의 OCR 호출에서 faxname 미정의(F821)
- **K13**: MailerService.set_cc, set_bcc 없음, attach_file 인자 불일치
- **K14**: ARCHITECTURE.md가 src/avantfax 경로 지시, src/avantfax와 src/namifax 이중 트리
- **K15**: 테스트 대부분 MagicMock/DummyRequest 기반, 골든 마스터는 폼 필드만 비교
- **K16**: mypy에서 존재하지 않는 메서드 호출(del_fax, archivefax, update_settings, get_dynconf, load_category, rename), QueryResult 반복 불가

## 1라운드 결함 (121건)

### 1라운드-A: 관리자 화면 (ADM, 30건)

**치명**:
- ADM-01: 앱 시작마다 seed/migration이 운영 데이터 덮어쓰기 (모뎀 샘플로 대체, fid=1 강제 설정, DistroList 복원)

**높음 (15건)**:
- ADM-02: 시스템 로그 화면 SQL 인젝션 (kw, year, month, day f-string 조립)
- ADM-03: 사용자 관리 삭제가 NOT NULL 위반으로 조용히 실패
- ADM-04: any_modem이 항상 1, 모뎀/DID/분류 권한 저장 안 됨 (체크박스 미읽기)
- ADM-05: 빈 비밀번호로 생성 시 'password' 고정, 수정 시 실패 무시
- ADM-06: 관리자 자기 강등 방지 없음, 권한 변경이 기존 세션에 미반영
- ADM-07: 바코드 라우팅 수정/삭제 불가 (PK 불일치: barcode_id vs bcr_id)
- ADM-08: DynConf 테이블 스키마에 없음 (DynamicConfig로 생성, 검색 실패)
- ADM-09: Fax2Email 관리 화면이 규칙 저장 못 함
- ADM-10: 시스템 기능(sysfunc) 화면 4개 버튼 무동작, 메시지 가짜
- ADM-11: 스토리지 수명주기에서 음수 일수 저장 시 모든 TIFF 즉시 삭제
- ADM-12: 스토리지 수명주기 서비스의 만료 삭제가 실제 팩스에 미적용/오동작 (6가지 결함)
- ADM-13: Cover Studio 렌더링 (Jinja2 코드 실행, PS 주입, 토큰 충돌)
- ADM-14: print-to-fax CLI가 큐 등록 안 하고 성공 메시지만 출력
- ADM-15: OCR 인덱싱이 실제로 저장 안 함 (QueryResult 반복 불가, MySQL DDL 오류)

**중간/낮음 (15건)**:
- ADM-16: 저장된 네트워크 프린터 값 미소비
- ADM-17: SMTP 게이트웨이 설정이 실제 메일 발송에 미사용
- ADM-18: SMTP 설정 저장 시 HTML 서명 삭제, 비밀번호 평문 노출
- ADM-19: 스토리지/SAML 설정 저장이 SQLite 전용 SQL (MySQL 미동작)
- ADM-20: DB 스키마와 엔티티 불일치 (비밀번호 이력, 시스템 로그 PK)
- ADM-21: 빈 테이블 시 가짜 데이터 표시 (수정/삭제 불가)
- ADM-22: DID/카테고리/모뎀/커버 액션 실패해도 성공 메시지 (존재하지 않는 ID 삭제도 성공)
- ADM-23: 모뎀 화면에서 삭제 버튼, devid, faxcatid 필드 폼에 없음
- ADM-24: Local/Cloud 스토리지 경로 탈출 가능, 연결 테스트 오판
- ADM-25: 프린터 화면 입력 검증 부재 (포트 범위, protocol 임의값)
- ADM-26: 시스템 로그 화면 년도 하드코딩(2024-2027), 페이지네이션 없음
- ADM-27: SAML 관리 설정 검증 없음 (javascript: 스킴, 잘못된 PEM)
- ADM-28: 패키징에서 avantfax 누락 (wheel에 namifax만)
- ADM-29: 설정 화면 안내/태그 불일치 (Cover Studio 태그 체계 혼재)
- ADM-30: 커버 관리에서 파일명 검증 없음, 중복 등록 가능

### 1라운드-B: 코어/DB 계층 (COR, 33건)

**치명 (4건)**:
- COR-01: SQLite 단일 연결/커서를 여러 스레드 공유 → SIGSEGV
- COR-02: 기동마다 seed/migration이 실제 운영 데이터 변조 (ADM-01과 동일 원인)
- COR-03: notify CLI가 모든 사용자에 AttributeError로 종료 (user.email 속성 없음)
- COR-04: send_mail이 SMTP 없이 메모리 스풀만 사용 → 메일 미발송

**높음 (16건)**:
- COR-05: AFAddressBook.loadbyfaxnum이 튜플 반환 → 항상 참 (신규 회사 미생성)
- COR-06: AddressBookFAX 스키마에 레거시 컬럼 누락 (email, printer, faxcatid 등)
- COR-07: AddressBook.abook_id가 신규 행에서 NULL (PK는 ab_id) → 조회/삭제 불가
- COR-08: DynConf 테이블 이름 불일치 (스키마 DynamicConfig, 서비스 DynConf)
- COR-09: QueryBuilder.quote가 bool을 'True'/'False' 문자열로 저장 → 계정 비활성/비관리자 변환
- COR-10: faxqueue 명령 주입 (shell=True, 사용자 입력 그대로 보간)
- COR-11: SQL 조립/이스케이프 결함 (LIKE 인젝션, MySQL 백슬래시 미처리)
- COR-12: MySQL 백엔드 사실상 불가능 (pymysql 미선언, SQL 전부 SQLite 전용)
- COR-13: DB 경로 기본값이 cwd 기준 → 호출 위치마다 별개 DB 생성 (seed도 매번 실행)
- COR-14: 보관 일시(archstamp)를 '/' 구분자로 저장 → 정리(prune) 동작 불가
- COR-15: tiff2pdf/convert2pdf/faxinfo가 실패를 성공으로 위장 (가짜 PDF/썸네일/정보)
- COR-16: faxcover 토큰 접두어 치환 충돌 (XXXX-to가 XXXX-to-company 안에서 먼저 치환)
- COR-17: createuser CLI 갱신 분기가 비밀번호 미변경 (old==old 검증)
- COR-18: 비밀번호 이력(UserPasswords) 스키마 불일치 (upid vs pwd_id)
- COR-19: AFUserAccount.remove가 NOT NULL 제약 위반으로 실패하는데 True 반환
- COR-20: faxrcvd가 레거시에서 벗어남 (TIFF 복사 실패 무시, 회사명 중복 미처리, 환경변수 읽기만)
- COR-21: FaxQueue 사용자 속성 존재 불일치 (name/username 속성 없음)

**중간/낮음 (13건)**:
- COR-22: DatabaseEngine 의미론 결함 (transaction 무력, SELECT 판별 오류, 예외 은폐)
- COR-23: 스케줄러/서비스 기동 결함 (서비스 중복, 정책 미적용, 인자 무시)
- COR-24: 설정 키 체계 불일치 (AVANTFAX_*, NAMIFAX_* 혼재)
- COR-25: 이중 트리/패키징 (namifax가 avantfax import, wheel에는 avantfax 없음, CLI 5개 avantfax 전용)
- COR-26: print_in이 큐 넣지 않고 진입점 미등록
- COR-27: OCR 서비스 미연결 엔진 + MySQL DDL → 인덱싱 영구 불능
- COR-28: archive_base 파일 삭제 불능, 미리보기 파일명 불일치, 회전 미동작
- COR-29: 스키마 PK/컬럼 불일치 (BarcodeRoute, SysLog 등)
- COR-30: 사용하지 않는 PHP 브리지 48개 + bridge_cli 보안 (임의 바이너리 실행/SQL)
- COR-31: 의존성 선언 불일치 (pymysql, tesseract, qrcode 미선언)
- COR-32: purge_expired_faxes 미연결 엔진 + 잘못된 디렉터리 규칙
- COR-33: 파일 경로/권한, 로그 처리 (mkdirs 실패 미확인, syslog 스레드 안전 미보장)

### 1라운드-C: 보안 (SEC, 6건 + K04)

**치명**:
- SEC-01: 비인증 SQL 인젝션 (주소록 검색 `/ajax/book`, UNION 기반 데이터 탈취)

**높음**:
- SEC-02: 상태 변경 AJAX/업로드 엔드포인트에 permission 미지정 (비인증 조작 가능)
- SEC-03: 팩스 상세/다운로드/주석/회전 등 IDOR (모뎀 제한 우회)
- SEC-04: 반사 XSS (`/ajax/deletefaxes`의 fids 파라미터)
- SEC-05: 비밀번호 만료/강제 재설정 정책이 로그인에 미강제
- SEC-06: 비밀번호 해시가 salt 없는 MD5 (레인보우 테이블 취약)
- SEC-07: TOTP 비밀키/백업코드가 DB 평문 저장

### 1라운드-D: UI 계층 (UI, 7건)

**높음**:
- UI-01: 설정 화면이 아무것도 저장하지 않으면서 성공 표시
- UI-02: admin_layout.jinja2가 message 렌더하지 않음 (피드백 사라짐)
- UI-03: 시스템 기능 화면 버튼이 뷰와 계약 어긋남 (무동작)
- UI-04: 빌드된 main.css가 템플릿과 어긋나 다수 클래스 스타일 없음 (버튼 흰 글씨 무배경)
- UI-05: 템플릿이 쓰는 문자열 68개가 번역 카탈로그와 전 로케일에 없음
- UI-06: 로그인 없는 요청이 로그인 화면 대신 원시 JSON 401 반환
- UI-07: /viewfax가 실제 팩스 대신 하드코딩 가짜 문서 표시

### 1라운드-E: 사용자 화면 (USR, 6건)

**치명 (2건)**:
- USR-04: 사용자별 모뎀/카테고리 기반 접근 제한이 완전 비동작 (타 사용자 팩스 전체 노출)
- USR-06: `/ajax/faxalter`가 인증 없이 접근 + 파라미터가 쉘 명령에 그대로 삽입

**높음**:
- USR-01: 아카이브 검색이 필터링 없으면 결과 항상 숨겨짐
- USR-02: 검색 0건 시 가짜(placeholder) 레코드를 실제 결과처럼 표시
- (F1-01 ~ F1-10: 2라운드에서 상세)

## 2라운드 결함 (105건)

### 2라운드-A: 수신 팩스 (F1, 11건)

**높음**:
- F1-01: 마이그레이션이 발신자 미식별 팩스를 매번 "Acme Corp의 팩스번호(faxnumid=1)"로 귀속
- F1-02: 마이그레이션이 발신 팩스의 modemdev를 'ttyS0'으로 채움
- F1-03: faxinfo 출력 해석 실패가 모두 "더미 팩스 정보"로 대체
- F1-04: DB 잠금 시간(5초 초과) 훅이 종료코드 0으로 끝남 (아카이브 고아)
- F1-08: 수신함이 최신 25건만 보여 26번째 이후 팩스 접근 불가

**중간/낮음**:
- F1-10: 보관 수신 팩스가 보관함 화면에 나타나지 않음

### 2라운드-B: 발송 팩스 (F2, 20건)

**높음 (11건)**:
- F2-01: sendfax 제출에 소유자(-o)와 발신자(-f) 바인딩 없음 (모든 작업이 서비스 계정 소유)
- F2-02: 다중 수신처가 하나의 -d 문자열로 전달 (엉뚱한 번호로 발신)
- F2-03: sendfax 실패를 사용자에게 알리지 않고 성공 리다이렉트
- F2-04: outbox 작업 취소가 실제로 아무것도 하지 않고 성공 메시지 표시
- F2-05: outbox가 로그인한 모든 사용자에게 전체 사용자의 송신 작업 노출
- F2-07: 작업 수정(/ajax/faxalter)이 항상 작업 #1을 대상 (기본값 1 때문)
- F2-08: 재전송(refax) 모달이 아무것도 제출하지 않음 (작업번호 1001 성공 처리)
- F2-09: 업로드 검증 부재 (MIME/크기 제한 미적용, 빈 파일 허용)
- (F3-01 ~ F3-26: 2라운드 후반부 별도)
- F4-01: 팩스 재전송/답장(refax)이 스텁 (잡 ID 1001 반환, 전송 없음)
- F4-02: "비밀번호 찾기"가 스텁 (메일/재설정 없음)

**중간/낮음 (9건)**:
- F2-06, F4-03 ~ F4-07, F4-10 등

### 2라운드-C: 계정과 권한 (F3, 26건)

계정 생성/로그인/비밀번호/권한 주기를 통합 점검:

**높음 (11건)**:
- F3-01: 2FA(TOTP)가 로그인에서 전혀 강제 안 됨 (TotpService 연결 없는 엔진 사용)
- F3-02: 일반 사용자가 자기 비밀번호 바꿀 경로 전무, 3개 화면 모두 성공 위장
- F3-03: can_del 권한이 어디에서도 검사 안 됨 (삭제 경로 3곳 + UI)
- F3-04: 주소록/배포목록/이메일북/모뎀 상태가 로그아웃 상태에서 조회 가능
- F3-05: superuser만 있는 계정이 관리자 영역 전부 접근, 저장 시 is_admin 영구 부여
- F3-06: 아카이브 검색이 권한 조건(모뎡/카테고리/userid)을 전혀 넘기지 않음
- F3-07: 팩스 발송이 사용자별 모뎡 권한 무시
- F3-08: 발송 시 사용자 신원(-o 사용자, -f 이메일) 미전달
- F3-09: 송신 큐(outbox)가 모든 사용자에게 전체 사용자 작업 노출
- F3-10: 관리자 하드코딩 로그인이 비밀번호 변경/비활성화 무력화 (K10 변형)
- F3-11: 비활성화/삭제/비밀번호 변경이 이미 발급된 세션에 미반영

**중간/낮음 (15건)**:
- F3-12: 관리자 폼에 활성화, 비밀번호 주기, 재사용 금지 필드 없음
- F3-13: 설정 화면이 모든 사용자에게 하드코딩된 관리자 프로필 표시
- F3-14: 2FA 상태가 항상 "미사용" (uid vs user_id 키 불일치)
- F3-15: SAML/패스키 로그인 후 세션 미생성, RelayState 오픈 리다이렉트
- F3-16: SAML 사용자 매핑이 로컬 계정 우회 가능 (admin@anything → uid 1)
- F3-17: PAM/pwauth/웹서버 인증 미연결 (python-pam 없음)
- F3-18: 계정 이벤트가 SysLog에 전혀 기록 안 됨 (감사 추적 불가)
- F3-19: HylaFAX 사용자 동기화(faxadduser/faxdeluser) 없음
- F3-20: remember()가 bool() 해석 → login()과 어긋남
- F3-21: 사용자명/이메일 대소문자 구분 (같은 이름 공존 가능)
- F3-22: 로그인 실패 사유와 복귀 경로(next) 유실
- F3-23: createuser CLI 기본값 위험 (--admin store_true + default=True)
- F3-24: 헤더 받은편지함 배지가 TypeError로 항상 0
- F3-25: 관리자 사용자 생성/수정 검증 오류 (중복, 약한 비밀번호 무시)
- F3-26: 세션 쿠키에 Secure 속성 없고, 메모리에만 존재

### 2라운드-D: 레거시 패리티와 이전 (F4, 24건)

**높음**:
- F4-05: 이메일→팩스(email2fax) 기능 전체 누락
- F4-06: sendfax 화면이 레거시 옵션 대부분 미처리
- F4-12: 팩스 다운로드가 파일 없어도 "합성 PDF" 반환
- F4-14: 아웃박스 작업 삭제가 호출 불가능한 메서드 사용
- F4-15: 레거시 주소록 팩스번호/이메일 미표시, 폼 비어 있음
- F4-16: AJAX 자동완성이 결과 없을 때 가짜 데이터 반환
- F4-17: 바코드 라우팅이 영구 비활성 (bardecode 항상 None)
- F4-19: import_archive 도구가 스텁 (진입점도 없음)
- F4-24: MySQL 레거시 스키마 이전 경로/도구/문서 없음
- F4-26: 레거시 '|' 구분자와 수신함 모뎀 필터 ',' 분리 불일치

**중간/낮음 (14건)**:
- 대조 항목 98개 중 구현 2개, 부분 60개, 스텁 20개, 누락 16개

### 2라운드-E: 운영과 테스트 품질 (F5, 24건)

**높음**:
- F5-01: 운영 기동 경로(systemd, namifax serve)가 wsgiref 개발 서버 (waitress 아님)
- F5-02: 임포트/앱 생성 오류가 조용히 JSON 스텁 앱으로 대체 (모든 URL 200 텍스트)
- F5-03: DB 열기/스키마 초기화 실패를 삼키고 200 + 가짜 데이터
- F5-04: 팩스 전송 결과 무시 + sendfax 바이너리 부재 시 가짜 성공
- F5-05: 테스트 48개 파일이 wheel에 미포함 avantfax 트리 검증
- F5-06: Web golden master가 자기 참조적 + 가짜 데이터를 "정답"으로 고정

**중간/낮음 (18건)**:
- 의존성, 설정, 빌드 파이프라인, 문서 불일치

## 보고서가 주장하는 수치

- **K01~K16**: 16건 (초기 확인)
- **1라운드**: 121건 (ADM 30, COR 33, SEC 6+K04, UI 7, USR 6, F1~F4 39)
- **2라운드**: 105건 (F1 5, F2 15, F3 26, F4 9, F5 6, 기타)
- **심각도**: 1라운드는 치명 8, 높음 39; 2라운드는 높음 47, 중간 39

## 한계·시험하지 못한 것

당시 조사의 미실행 항목:
- 공격 페이로드(셸 주입, SQL 주입)는 원칙적으로 실행하지 않음
- 실제 HylaFAX, 실제 IdP(SAML), S3/GCS 연동 검증 불가
- 테스트 코드 69개 파일 중 약 13개만 줄 단위로 읽음
- PHP 브리지는 메서드 이름 대조만
- namifax-server 포트 미개방 현상 원인 미분석

## 관련 주제 페이지

- [[authentication-and-security]]
- [[database-and-migrations]]
- [[scheduler-and-storage]]
- [[operations-and-deployment]]
- [[testing]]
- [[migration-from-avantfax]]
