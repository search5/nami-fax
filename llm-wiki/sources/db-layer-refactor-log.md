---
title: DB 계층 전환 기록 (아키텍처 스냅샷)
type: source
updated: 2026-10-02
sources: ["git show 54dd654:docs/history/db-layer-refactor-log.md (삭제됨; 지금도 유효한 규칙은 [[database-and-migrations]] 8·9절과 [[testing]] 'mock 시험의 함정' 으로 옮김)"]
verified: false
---

> 원본 문서는 2026-10-02 에 저장소에서 삭제했다(위 `git show` 로 읽는다). 과정 기록 중 `DatabaseEngine`, `cli_unit`, `bridge_cli` 등 지금 코드에 없는 이름은 옮기지 않았다. 이 요약은 삭제 시점의 문서가 주장한 바이며 현재 코드와 다를 수 있다.

## 요약

NamiFAX의 DB 계층을 전역 싱글턴 `_DEFAULT_ENGINE`(결함 F5-12, R4F-13/F5-08)에서 벗어나 요청당 주입(`request.db`), CLI 명령당 별도 컨텍스트(`cli_db()`, `cli_unit()`) 기반으로 전환한 3주간의 리팩터링 과정 기록. 13~14장에 걸쳐 웹 계층 V 루프(V1~V12), CLI 계층 C 루프(C0~C6), 글로벌 엔진 제거(F), B 트랙 준비(Pyramid 스타터 구조 도입), ORM 모델화 진행표(14개 테이블 중 4개 완료), 기능 결함 수정(SMTP 설정 미반영, 로그 미기록), 서비스 생성자 양쪽 지원, 스키마 시드 훼손 방지 등 상세히 기록. 단순히 DB 라이브러리 교체가 아닌 아키텍처 전환의 판단과 근거를 문서화한 의사결정 기록.

## 핵심 내용

**§13 DB 엔진 주입 리팩터링 (Spec 48)**
- 목적: 전역 싱글턴 제거 후 연결만 주입(DatabaseEngine 유지)
- 웹: `create_app` → `request.db` (풀 커넥션을 감싼 엔진, 요청 종료 시 반환)
- CLI: `cli_db()` 컨텍스트 또는 `cli_unit()`(ORM+레거시 혼합)
- URL 우선순위: `sqlalchemy.url` > `DATABASE_URL` > `AFDB_URL` > `NAMIFAX_DB_PATH`

**§13 루프 단계(웹 V, CLI C, 감사 V-audit, 레거시 제거 F)**
- V1: `views/inbox.py` 5개 뷰 + 공유 헬퍼에 `request.db` 주입
- V2: `views/modals.py` 6개 뷰
- V3: `views/ajax.py` 9개 뷰 (`conftest.py::seeded_db` 도입으로 전역 DB 시드 의존 제거)
- V4: `views/admin.py` 19개 클래스 19곳 + 헬퍼
- V5~V12: 나머지 뷰들 순차 전환
- C0~C6: CLI 스크립트(`faxrcvd`, `notify`, `cron`, 배치 도구) 컨텍스트 매니저 도입
- F: `Repository`의 `get_default_engine()` 폴백 제거, 미주입 시 `RuntimeError` 발생

**§13.1~13.3 발견된 결함**
- `services/ocr.py`, `services/webauthn.py`의 `CREATE TABLE`이 MySQL 전용 DDL(SQLite에서 생성 안 됨)
- `src/namifax/web/*` 폴백 앱(JSON/WSGI)의 DB 주입 필요 여부 미결정
- `src/avantfax/*` 복사본 패키지(56개 .py)가 테스트 48개 파일에 임포트 중(배포 패키지가 아님)

**§13.4~13.7 P3 테스트 전환 결과**
- `avantfax` 대상 테스트 41개 파일을 `namifax`로 전환, 실패는 3건만(모두 개선)
- `isolated_database` autouse 픽스처로 테스트별 격리 DB
- 발견 결함: `AddressBook`의 `ab_id`/`abook_id` 이름 불일치, `abook_id` NULL 백필 미완
- Dead Code 제거: `src/avantfax/` 전체, `src/namifax/web/` 전체, JSON 폴백 앱

**§14 B 트랙 준비 (Pyramid starter 도입)**
- 의존성 추가: `pyramid_tm`, `pyramid_retry`, `transaction`, `zope.sqlalchemy`, `alembic`
- `models.includeme` 완성: `tm.manager_hook` 설정 순서 정정, `pyramid_retry` include
- `app.dbsession` 테스트 훅, `ImportError` 폴백 제거
- Alembic 설정 및 마이그레이션 구조 정립

**§14.1 B0에서 확정된 계약**
- zope.sqlalchemy는 변경 감지 세션만 커밋(raw SQL은 `mark_changed()` 호출 필요)
- managed 엔진은 commit/close를 하지 않음(tm에 위임)
- 요청 예외 시 모든 쓰기 함께 롤백(이전: 쓰기마다 즉시 commit)

**§14.2 다중 DB 지원 조사**
- **현재 SQLite 외 DB는 시작 불가**: 초기화 DDL 20개가 PostgreSQL에서 전부 실패(`AUTOINCREMENT`)
- SQLite 전용 구문 분포: `INSERT OR REPLACE/IGNORE` 23곳, `AUTOINCREMENT` 20곳, `sqlite_master`/`PRAGMA` 5곳
- 보안 결함: 74곳 f-string SQL의 `quote()`가 작은따옴표만 처리(MySQL 역슬래시 이스케이프 미처리)
- 결론: 다중 DB는 모델(SQLAlchemy), Alembic 마이그레이션으로만 확보 가능(B 트랙 전제)

**§14.3 파일럿: `SystemConfig`**
- 모델 + 서비스 + Alembic 리비전 + 서버 3종 검증(SQLite, PostgreSQL 16, MySQL 8.4)
- 변경: `INSERT OR REPLACE` → `Session.merge`(이식 가능 upsert)
- 저장소 계층에 `OrmRepository` 추가(`DatabaseEngine` ↔ `Session` 자동 선택)
- 모델화 모듈은 PostgreSQL에서도 서비스·마이그레이션 수준 동작 가능

**§14.4~14.6 ORM 모델화 진행표(14개 테이블)**
- **완료(ORM)**: 그룹 1 전체(4개: SystemConfig, SystemSettings, NetworkPrinters, SysLog) + 그룹 2/3 일부
- **상태**: `[LEGACY]` raw SQL / `[ORM]` 모델 + Session 서비스 + Alembic 리비전
- 서버 검증: SQLite(자동) + PostgreSQL 16·MySQL 8.4·MariaDB 11.8 선택
- **파일럿에서 확정된 절차**: 모델 작성 → 서비스(Session 주입) → 뷰(`request.dbsession`) → Alembic 리비전(멱등) → 테스트(SQLite 자동 + 서버 선택)

**§14.6~14.7 기능 결함 수정**
- SMTP 설정이 실제 발송에 반영 안 됨: `MailerService.get_active_mailer(session)` 도입
- CLI의 모든 메일이 실제 발송 안 됨: 기본 설정 없으면 로컬 MTA 폴백
- `avantfaxlog()` 미작동: `SysLogService.add()` 복원 + `cli_session()` 자동 호출

**§14.8 `OrmRepository`: 서비스 재작성 없이 이식**
- `Repository(테이블, db=Session|DatabaseEngine)` 디스패치로 양쪽 구현
- `find()`, `new_entry()`, `update_entry()`, `delete_entry()`, `query()` 동일 시그니처
- 레거시 의미 보존(느슨한 타입 변환, 갱신/삭제 시 대상 부재도 성공, 알 수 없는 키 무시)

**§14.9 스키마 시드 훼손 방지**
- **문제**: 서버 시작할 때마다 `admin`/`password`, 데모 모뎀/카테고리, 실제 팩스 #1을 데모 값으로 덮어씀
- **수정**: 데모 데이터는 **새 DB에만** 삽입, `INSERT OR REPLACE` → `INSERT OR IGNORE`, 마이그레이션 복구 UPDATE 제거
- 구조 백필(`abook_id` 등) 전용 함수 추가

**§14.10 CLI에서 레거시와 ORM 혼합: `cli_unit()`**
- **문제**: SQLite 쓰기 연결 2개 시 서로를 잠금(로그 미기록)
- **해결**: `provider.cli_unit()`: 레거시 엔진과 ORM 세션이 **한 연결 공유**(웹의 `request.db` + `request.dbsession` 모델)
- `provider.active_session()`: ContextVar로 실행 중인 세션 추적(간단한 훅이 별도 세션 열기 회피)

**§14.11~14.13 발견·수정한 결함**
- **주소록 검색 SQL 인젝션**: `LIKE` 패턴을 인용 처리(양쪽 저장소)
- **비밀번호 이력 미작동**: `AFUserPasswords` 컬럼명 일치 모델화
- **새 주소록 회사 ID 미조회**: `abook_id`를 실제 기본키로 재구성
- **불리언이 문자열 저장**: `quote(bool)` → `1`/`0` + `LegacyBoolean` 타입 도입
- **저장된 해시가 비밀번호로 통용**: 평문 비교 대체 경로 삭제
- **계정 삭제 미반영**: NULL 대신 `deleted.<uid>` 값으로 갱신

## 문서가 주장하는 수치·상태

- 웹 계층 루프: V1~V12 총 12개, 각 단계마다 `[COMPLETE]` 표시 + 단위 테스트 증가(루프 1: 413 통과 → 루프 12: 521 통과)
- CLI 계층 루프: C0~C6 총 7개, 전체 546 통과 + P3에서 565 통과
- Dead Code 제거: `src/avantfax/` 56개 .py 파일, `src/namifax/web/` 일부 파일, JSON 폴백 앱
- ORM 모델화: 14개 테이블 중 **4개 완료**(그룹 1), 나머지는 `[LEGACY]` 표시
- 서버 검증: SQLite(자동) + PostgreSQL/MySQL/MariaDB(선택), 모든 서버에서 마이그레이션-모델 드리프트 검사 통과
- Alembic 리비전: 0001~0004(완료), 0005 이후(진행 중)

## 낡았을 가능성이 큰 부분

- 문서가 3주간 진행된 작업의 스냅샷이며, 2026-10-02 이후 추가 ORM 모델화가 진행되었을 수 있음 (문서에서 "완료" 표시는 그 시점의 상태)
- §13.1, 13.2, 13.3의 "미결정", "결정 필요", "제외" 항목들이 이미 해결되었을 가능성 높음
- `src/avantfax/` 복사본 제거 여부, JSON 폴백 앱 제거 여부가 실제 코드에서 확인 필요
- B 트랙(ORM 전환)이 당시 "준비" 단계였으므로, 현재 모델화 진행 상황이 크게 달라졌을 수 있음
- "남은 한계"(§14.3)에서 비 SQLite DB는 모든 테이블이 ORM으로 옮겨질 때까지 지원 불가라고 했으므로, 현재 다중 DB 지원 상태 확인 필요

## 관련 주제 페이지

[[database-and-migrations]] [[architecture-and-modules]] [[operations-and-deployment]] [[testing]]
