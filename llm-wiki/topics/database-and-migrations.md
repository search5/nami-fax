---
title: 데이터베이스와 마이그레이션
type: topic
updated: 2026-10-13
verified: true
sources:
  - src/namifax/db/provider.py
  - src/namifax/db/bootstrap.py
  - src/namifax/db/adopt.py
  - src/namifax/db/sqlite_upgrade.py
  - src/namifax/db/seed.py
  - src/namifax/db/missing.py
  - src/namifax/db/repository.py
  - src/namifax/db/orm_repository.py
  - src/namifax/db/textsearch.py
  - src/namifax/models/__init__.py
  - src/namifax/models/meta.py
  - src/namifax/models/types.py
  - src/namifax/models/useraccount.py
  - src/namifax/models/systemconfig.py
  - src/namifax/services/system_config.py
  - src/namifax/services/login_throttle.py
  - src/namifax/services/scheduler_config.py
  - src/namifax/services/saml.py
  - src/namifax/services/cloud_storage.py
  - src/namifax/services/storage_lifecycle.py
  - src/namifax/models/systemsettings.py
  - src/namifax/common/settings.py
  - src/namifax/main.py
  - src/namifax/__init__.py
  - tests/fixtures/legacy_sql/
  - src/namifax/alembic/env.py
  - src/namifax/alembic/versions/
  - src/namifax/views/no_database.py
  - tests/conftest.py
  - pyproject.toml
  - src/namifax/services/archive_orm.py
  - src/namifax/services/syslog.py
  - src/namifax/models/faxocr.py
  - src/namifax/models/syslog.py
  - tests/sqlsession.py
  - tests/unit/test_routes_and_modems.py
  - tests/unit/test_orm_repository.py
  - tests/unit/test_system_config.py
  - tests/unit/test_fax_archive_orm.py
  - tests/unit/test_boolean_flags.py
  - tests/unit/test_schema_seed_safety.py
  - tests/unit/test_schema_seed_first_run.py
  - tests/unit/test_demo_data_optin.py
  - "[[db-layer-refactor-log]]"
  - "[[migrating-from-avantfax3]]"
  - "[[architecture-md-part1]]"
---

# 데이터베이스와 마이그레이션

2026-10-02 시점의 `src/`·`tests/` 를 직접 읽고 쓴 것이다. 시험은 이 세션에서 실행하지 않았으므로 아래 시험 이름은 "이 동작을 지키려고 있는 시험"이라는 뜻이며 통과 여부는 확인하지 않았다. 관련 주제: [[architecture-and-modules]], [[authentication-and-security]], [[migration-from-avantfax]], [[operations-and-deployment]], [[testing]], [[known-gaps-and-decisions]].

## 1. 지원 DB와 엔진 생성

- 지원: SQLite(기본), MySQL, MariaDB, PostgreSQL. 서버 드라이버는 선택 설치다: `pyproject.toml` 의 선택 의존성 `postgresql`(`psycopg[binary]`)과 `mysql`(`pymysql`). 개발 그룹에는 둘 다 들어 있다. [코드] `pyproject.toml`
- URL 우선순위: ini 의 `sqlalchemy.url` > 환경변수 `DATABASE_URL` > `AFDB_URL` > `NAMIFAX_DB_PATH`(SQLite 파일) > 현재 디렉터리의 `namifax.db`. [코드] `src/namifax/db/provider.py::resolve_database_url`; 시험 `tests/unit/test_db_injection.py` (`test_url_prefers_settings_over_env`, `test_url_database_url_beats_afdb_url`, `test_url_falls_back_to_namifax_db_path`, `test_url_default_is_cwd_namifax_db`)
- 엔진: `create_sa_engine(url)`. SQLite 는 `check_same_thread=False`, 메모리 DB(`sqlite://`)는 `StaticPool` 로 한 DB 를 공유한다. 서버 DB 는 `pool_pre_ping=True`. [코드] `provider.py`; 시험 `test_db_injection.py::test_memory_engine_shares_one_database_across_connections`
- 엔진은 앱 시작 때 한 번 만들어 `registry["dbengine"]` 에 두고, 전역 싱글턴은 없다. 서로 다른 URL 로 만든 두 앱은 격리된다. [코드] `src/namifax/models/__init__.py::includeme`; 시험 `test_db_injection.py::test_two_apps_with_different_urls_are_isolated`, `tests/unit/test_global_engine_removed.py`
- CLI 는 요청이 없으므로 `cli_session(settings, environ, ensure_schema)` 로 같은 URL 규칙의 세션을 연다. 블록이 정상 종료하면 커밋, 예외면 롤백하고, 끝날 때 세션을 닫고 엔진 풀을 해제(`engine.dispose()`)한다(엔진을 돌려주지 않고 세션을 넘긴다). `ensure_schema=True` 이면 세션을 열기 전에 `ensure_schema(engine)` 을 부르는데 이때 `settings` 를 넘기지 않으므로 ini 의 `demo.data` 는 CLI 경로에서 보이지 않는다(환경변수 `NAMIFAX_DEMO_DATA` 만 유효). 열린 세션은 컨텍스트 변수(`active_session()`)로 공유해 `avantfaxlog()`·`send_mail()` 이 같은 연결을 쓰게 한다(SQLite 에서 두 번째 쓰기 연결이 잠기는 것을 피함). [코드] `provider.py`; 시험 `tests/unit/test_cli_session.py`, `tests/unit/test_db_isolation_fixture.py`
- DB 에 연결할 수 없으면(`OperationalError`/`DBAPIError`) 503 과 "no database" 페이지(10초마다 재시도)를 보인다. 세부 오류는 로그에만 남긴다. [코드] `src/namifax/views/no_database.py`; 시험 `tests/unit/test_no_database_page.py`

> 모순: [[db-layer-refactor-log]] 는 `request.db`, `cli_db()`, `cli_unit()`, `DatabaseEngine`, `_DEFAULT_ENGINE` 을 전환 경과로 적는다. 현재 `src/` 에는 이 이름이 하나도 없다(grep 확인). 요청은 `request.dbsession`, CLI 는 `cli_session()` 이다. 같은 문서의 "SQLite 외 DB 는 시작 불가"(§14.2)도 과거 상태이며, 지금은 Alembic 으로 네 DB 를 만든다. `src/avantfax/`, `src/namifax/web/` 도 없다(`ls src`: `namifax` 하나).

## 2. 스키마 부트스트랩(`ensure_schema`)과 Alembic

`ensure_schema(engine, settings)` 는 앱 시작과 CLI(`ensure_schema=True`), 훅 호출 때 실행되는 멱등 함수다. [코드] `src/namifax/db/bootstrap.py`, 호출 `src/namifax/__init__.py`

1. `UserAccount` 테이블이 없으면 새 DB(`fresh`)로 본다.
2. 새 DB가 아니고 `alembic_version` 이 현재 head 와 같으면 SQLite 의 옛 테이블 보정만 하고 바로 돌려보낸다(빠른 경로). 시험 `tests/unit/test_schema_fast_path.py` (`test_the_second_start_does_not_run_the_migrations`)
3. 그 밖에는 순서대로: (SQLite만) `upgrade_existing_sqlite` → `adopt_existing_tables` → `upgrade_to_head`(Alembic `upgrade head`, 열린 연결을 `cfg.attributes["connection"]` 로 넘김) → 시드.
4. 시드: 데모 데이터를 켠 SQLite 에서는 `seed_if_empty`, 그 외 새 DB 에서는 기본 레코드(표지 3종)만. 기존 데이터는 바꾸지 않는다.
5. 어떤 단계든 실패하면 `RuntimeError("Database initialisation failed: ...")` 로 즉시 실패한다(조용히 넘어가지 않음). 시험 `tests/unit/test_multi_dialect_safety.py`, `tests/unit/test_bootstrap.py::test_a_failure_to_initialise_is_loud`

- 데모 데이터: `NAMIFAX_DEMO_DATA=1`(또는 ini `demo.data = true`)이고 SQLite 이고 사용자가 0명일 때만 생긴다. 서버 DB 에서 요청해도 경고하고 무시한다. 서버 DB 의 첫 관리자는 `namifax createuser` 로 만든다. 시험 `tests/unit/test_demo_data_optin.py`, `tests/unit/test_schema_seed_safety.py`, `test_bootstrap.py::test_server_database_gets_the_schema_and_default_records_only` [코드]
- Alembic 환경: `src/namifax/alembic/env.py`. ini 없이 호출되면(앱 내부 호출) 열린 연결을 받아 쓰고, CLI(`alembic -c development.ini ...`)에서는 앱과 같은 규칙으로 URL 을 푼다. `target_metadata` 는 `Base.metadata`. 시험 `tests/unit/test_alembic_wiring.py`, `test_bootstrap.py::test_alembic_environment_accepts_an_existing_connection`
- 리비전: 파일 이름 `YYYYMMDD_NNNN_설명.py`, 리비전 ID 는 `0001`~`0027` 의 직선 체인(분기 없음). 현재 head 는 **`0027`**(`20261013_0027_drop_fax_ocr.py`: 쓰는 곳이 없던 `FaxOCR` 테이블 삭제, 없으면 건너뜀, `downgrade` 는 다시 만든다. 2026-10-13). 그 앞 `0026`(`20261002_0026_password_hash_width.py`: `UserAccount.password` 와 `UserPasswords.pwdhash` 를 `String(64)`→`String(255)` 로 확장, Argon2id 해시용). 바로 앞은 `0025`(`page_size_no_default`: `UserAccount.faxperpageinbox`/`faxperpagearchive` 의 서버 기본값 `10` 제거), `0024`(`fax_number_address`: `AddressBookFAX` 에 `to_address`/`to_zip`/`to_city`, 열이 이미 있으면 건너뜀), `0023`(`syslog_key_name`: `SysLog.log_id`→`syslogid` 이름 변경, 이미 원본 이름이면 건너뜀), `0022`(`smtp_password_length`), `0021`(`totp_lockout`). [코드] `src/namifax/alembic/versions/*.py` 의 `revision`/`down_revision` 값을 직접 읽어 체인 확인(2026-10-02, 이번 세션 코드 변경 이후 HEAD `740e12e` 에서 재확인; `git diff abb144f..HEAD -- src/namifax/alembic` 가 비어 있어 이번 세션 중 새 리비전은 없음). head 가 하나뿐임은 시험 `tests/unit/test_system_config_migration.py::test_there_is_exactly_one_head_revision` 이 지킨다.
- 리비전 `0001` 은 `SystemConfig`, `0002` `SystemSettings`, `0003` 네트워크 프린터, `0004` `SysLog`, `0005` 팩스 카테고리, `0006` 표지, `0007` `DynConf`, `0008` `Modems`, `0009` DID 경로, `0010` 바코드 경로, `0011` 배포 목록, `0012` `UserPasswords`, `0013`~`0015` 주소록 3테이블, `0016` `UserAccount`, `0017` `UserTOTP`, `0018` `UserWebAuthnCredentials`, `0019` `FaxOCR`(뒤에 `0027` 이 삭제), `0020` `FaxArchive` 다. `0021`~`0026` 은 기존 테이블의 열 변경이고 `0027` 은 테이블 삭제다. [코드] 각 파일의 `op.create_table("...")` 첫 인자를 grep 으로 읽어 테이블 이름 대응을 확인(2026-10-02). `0001`~`0020` 은 테이블이 이미 있으면(`has_table`) 만들지 않고 건너뛰는 가드가 있다 — 레거시 DB 를 그대로 받아들이기 위한 것이다(`0001`, `0004`, `0016` 등에서 확인, `0016` 은 본문까지 읽음).
- 모델과 마이그레이션이 어긋나지 않는지 비교하는 시험: `tests/unit/test_migrations_match_models.py` (SQLite, 서버 DB 두 가지).
- 리비전을 만들 때: `alembic -c development.ini revision --autogenerate -m "..."`, 적용은 `alembic -c development.ini upgrade head`. [코드] `src/namifax/alembic/versions/README.txt`

> 모순: [[architecture-md-part1]] 등 과거 문서에 "초기화 DDL 20개가 SQLite 전용" 같은 서술이 있다면 과거 상태다. 현재는 Alembic 이 DDL 을 만들고 `INSERT OR REPLACE` 는 `src` 에서 `services/system_config.py` 의 설명문에만 남아 있고(`db/seed.py` 에는 `INSERT OR IGNORE` 설명문만 있다), 실행 코드의 SQLite 전용 구문(`sqlite_master`, `pragma_table_info`, `AUTOINCREMENT`)은 SQLite 전용 보정 모듈 `db/sqlite_upgrade.py` 에만 있다(`grep -rn "INSERT OR\|AUTOINCREMENT\|sqlite_master\|PRAGMA\|pragma" src/namifax`, `alembic/` 제외, 2026-10-02). 이전 판은 `AUTOINCREMENT` 도 주석에만 있다고 썼으나 `sqlite_upgrade.py` 의 `AddressBook` 재구성 DDL 에 실제로 들어 있다.

## 3. 모델 구조와 테이블

- 모든 모델은 `namifax.models.meta.Base`(SQLAlchemy 2 `DeclarativeBase`, 이름 규칙 `NAMING_CONVENTION`)를 상속한다. `models/__init__.py` 가 모든 모델을 import 하고 `configure_mappers()` 를 부른다. [코드]
- 테이블은 현재 `models/*.py` 의 `__tablename__` 을 세어 **20개**다(2026-10-02, `grep -c __tablename__`). 그룹별:
  - 원본 AvantFAX 에서 온 14개: `AddressBook`, `AddressBookFAX`, `AddressBookEmail`, `BarcodeRoute`, `CoverPages`, `DIDRoute`, `DistroList`, `DynConf`, `FaxArchive`, `FaxCategory`, `Modems`, `SysLog`, `UserAccount`, `UserPasswords`. (시험 `tests/unit/test_legacy_database_compat.py` 의 `LEGACY_TABLES` 목록과 같다.)
  - 이식본이 추가한 5개: `SystemConfig`(키-값), `SystemSettings`(SMTP, 한 행), `NetworkPrinters`, `UserTOTP`, `UserWebAuthnCredentials`. (`FaxOCR` 은 `0019` 가 만들었으나 쓰는 곳이 없어 `0027` 이 지웠다 — OCR 텍스트는 원본처럼 `FaxArchive.faxcontent` 에만 둔다. 2026-10-13)
- 테이블·열 이름은 레거시 SQL 의 철자 그대로(대소문자 포함)다. MySQL/MariaDB 가 리눅스에서 대소문자를 구분하므로 원시 SQL 이 계속 맞도록 하기 위해서다. [코드] `models/systemconfig.py`, `models/useraccount.py` 주석
- 공통 컬럼 타입 [코드] `src/namifax/models/types.py`:
  - `LegacyBoolean`: 옛 코드가 문자열 `'False'` 로 쓴 값도 거짓으로 읽는다(`Boolean` 은 비어 있지 않은 문자열을 참으로 읽어 권한 상승이 됨). 시험 `tests/unit/test_boolean_flags.py`
  - `IsoText`: 원본의 `TIMESTAMP`/`DATE` 열이든 이식본의 `VARCHAR` 든 앱에서는 ISO 문자열(`YYYY-MM-DD HH:MM:SS`)로 읽고 쓴다. 시험 `test_legacy_database_compat.py::test_dates_come_back_as_iso_text`
  - `LegacyHtmlString`/`LegacyHtmlText`: 원본이 `htmlentities` 로 저장한 문자(`m&uuml;ller`)를 읽을 때 되돌린다. 검색은 입력 그대로와 원본식 인코딩 두 패턴을 모두 쓴다(`db/textsearch.py::like_patterns`). 시험 `tests/unit/test_legacy_html_entities.py`
- 서비스는 `Repository("모델이름", db=session)`(별칭 `MDBOData`)로 `OrmRepository` 를 쓴다. 호출 방식은 원본 PHP 의 `find/new_entry/update_entry/delete_entry` 를 유지하되 값은 바인드 파라미터이고, DB 오류는 `False` 가 아니라 예외다. 숫자 문자열은 정수 열에 맞게 변환한다. 원시 `query` 는 지원하지 않는다. [코드] `db/repository.py`, `db/orm_repository.py`; 시험 `tests/unit/test_orm_repository.py`
- 사용자 입력 SQL 주입 방어: 주소록·팩스 큐·로그 조회 등에 대한 시험 `tests/unit/test_addressbook_search_injection.py`, `test_faxqueue_db_injection.py`, `test_services_db_injection.py`, `test_db_injection.py`. 과거 보고서의 SEC-01(주소록 검색 SQL 주입)·74곳 f-string SQL 지적은 값이 바인드되는 ORM 경로로 바뀌었다. 다만 `db/adopt.py` 와 `db/sqlite_upgrade.py`, `db/bootstrap.py` 에는 상수에서 만든 DDL·보정용 `text()` 가 남아 있다(입력값이 아님). [코드]

## 4. 레거시 AvantFAX DB 이어 쓰기 규칙

목적: 원본 AvantFAX 3.x(MySQL/MariaDB)가 만든 DB 에 이식본을 붙여 쓰고, 원본 PHP 도 같은 DB 를 계속 읽을 수 있게 한다([[migrating-from-avantfax3]]).

- `adopt_existing_tables` 규칙 [코드] `src/namifax/db/adopt.py`: 이미 있는 테이블은 Alembic 이 건드리지 않으므로, 모델이 필요로 하는 것을 덧붙인다 — (1) 없는 컬럼은 NULL 허용(모델이 서버 기본값을 주면 그 값과 함께) 컬럼으로 추가, (2) 모델이 선언한 인덱스 중 같은 열을 덮는 인덱스가 없으면 생성(유니크 인덱스는 제외), (3) 너무 좁은 열은 넓힘(MySQL/MariaDB 에서만 `UserAccount.last_ip` 를 45자로). **삭제·이름 변경·타입 변경과 기존 행 수정은 하지 않는다**(이 모듈 기준). 같은 DB 에 Alembic 리비전도 돌므로 예외가 둘 있다: `0025` 는 `UserAccount` 쪽 보관 쪽수 열의 서버 기본값을 없애고, `0026` 은 `UserAccount.password`/`UserPasswords.pwdhash` 의 길이를 255 로 넓힌다(둘 다 `UserAccount`/`UserPasswords` 가 레거시 DB 에 이미 있어도 적용되는 `batch_alter_table`; 기존 행 값은 그대로 둔다. `0026` 의 모듈 설명은 "MD5 값은 소유자가 이 프로그램에 다음에 로그인할 때까지 그대로 남아 원본이 계속 동작한다"고 한다. 실제 레거시 MySQL DB 에서 `0025`/`0026` 이 도는 결과는 이 세션에서 확인하지 않았다). 시험 `tests/unit/test_legacy_database_compat.py` (서버 DB 시험: `test_starting_on_a_legacy_database_keeps_every_legacy_row`, `test_nothing_is_added_to_a_database_that_already_has_its_data`, `test_a_second_start_changes_nothing`, `test_every_column_the_models_need_exists_afterwards`, `test_the_legacy_column_types_are_left_alone`)
- 예외가 아닌 한 컬럼·테이블 이름은 원본 SQL 의 철자를 바꾸지 않는다. 새 기능이 필요한 컬럼은 "추가"만 한다(예: 주소록의 추가 필드, `0024`). 이를 어기면 원본 PHP 가 깨진다. 이 규칙은 코드 주석(`adopt.py` 모듈 docstring, `models/*.py` 주석)에 명시돼 있다. [코드]
- 한 가지 의도된 비호환: 이식본에서 로그인했거나 비밀번호를 바꾼 계정은 Argon2id 해시가 되어 원본이 읽지 못한다. 병행 운영이면 `NAMIFAX_PASSWORD_HASH=md5`. 자세히는 [[authentication-and-security]] 1절, [[migrating-from-avantfax3]] 4.3 [문서].
- 원본 설치의 기본 관리자 계정은 로그인 시 비밀번호 변경을 강제한다. 시험 `test_legacy_database_compat.py::test_the_legacy_administrator_can_log_in_and_must_change_the_password`
- 레거시 DB 위에서 수신·검색·주소록·계정·모뎀·경로·목록 관리가 모두 되는지 확인하는 시험이 같은 파일에 있다(`test_faxes_can_be_received_searched_and_listed`, `test_accounts_modems_routes_and_lists_can_be_managed`, `test_the_web_application_serves_a_legacy_database`, IPv6 주소 기록, 상대 `faxpath` 해석 등).
- 시험 데이터는 원본 설치 SQL `create_tables.sql` 과 3.3.4 업그레이드 스크립트 `db-update-334.sql` 두 파일을 `tests/fixtures/legacy_sql/` 에 고정해 두고, 3.2.0(`create_tables.sql` 만)·3.3.5(`create_tables.sql` + `db-update-334.sql`) × MySQL·MariaDB 4가지로 DB 를 만든다. [코드] `tests/conftest.py::legacy_db`(파라미터 `("mysql","3.3.5")` 등), `LEGACY_VERSIONS = {"3.3.5": ["db-update-334.sql"], "3.2.0": []}`, 상수 `LEGACY_ROOT`; `ls tests/fixtures/legacy_sql` 로 두 파일만 있음을 확인(2026-10-02). 이전 판의 "3.2.0/3.3.5 업그레이드 스크립트"는 틀렸다.

### SQLite 의 옛 테이블 보정(`sqlite_upgrade`)

이식본 초기 버전이 만든 SQLite 파일만 해당한다. `alembic upgrade` 보다 먼저 돌며 새 DB 에서는 아무것도 하지 않는다. 멱등이다. [코드] `src/namifax/db/sqlite_upgrade.py`; 시험 `tests/unit/test_sqlite_upgrade.py`

- 옛 테이블 이름 `DIDRouting`→`DIDRoute`, `FaxPDFCategory`→`FaxCategory`로 이름 변경(원본 철자에 맞춤).
- `UserPasswords` 의 `pwd_id`/`password` → `upid`/`pwdhash` 열 이름 변경.
- `AddressBook` 기본키 `ab_id` → `abook_id` 로 테이블을 재구성(모든 id 보존, 자식 테이블 연결 열 채움).
- 빠진 열 추가, 이식본이 중복으로 만든 id 열의 NULL 값을 원본 열에서 채움, `UserAccount` 플래그의 문자열 `'True'/'False'` 를 0/1 로 정규화(문자열인 값만). 시험 `tests/unit/test_boolean_flags.py`

> 이 이름 변경·재구성은 이식본이 자기 이전 버전의 SQLite 파일을 고치는 것이고, 원본 AvantFAX 의 MySQL DB 에는 적용되지 않는다. 원본 DB 에는 "이름 변경 금지, 추가만" 규칙이 그대로다. [코드] `sqlite_upgrade.py` 는 SQLite 전용(`ensure_schema` 가 `dialect.name == "sqlite"` 일 때만 호출).

## 5. SystemConfig 키 저장 방식

- 테이블 `SystemConfig(key String(255) PK, value Text)`. 접근은 `SystemConfigService(session)` 의 `get(key, default)`, `set(key, value)`, `lock(key)`, `locked_update(key, change)` 이다. `set` 은 DB 별 **원자적 upsert 한 문장**이다(MySQL·MariaDB `ON DUPLICATE KEY UPDATE`, PostgreSQL·SQLite `ON CONFLICT`; 그 밖의 DB 는 `merge`). 문장의 대상이 테이블이 아니라 **매핑된 클래스**여서 ORM 문장이 되고, 요청 트랜잭션(`zope.sqlalchemy`)이 이를 변경으로 보고 커밋한다(테이블 대상 Core 문장은 "변경 없음"으로 보고 롤백했다). `lock` 은 행이 없으면 만들고 `SELECT ... FOR UPDATE` 로 읽어 그 행을 돌려준다(여러 키를 잠글 때는 항상 같은 순서로). `locked_update` 는 값을 이전 값에서 바꿀 때(카운터) 쓴다: `lock` 한 행의 값을 바꾸므로 같은 키를 동시에 바꾸는 요청이 차례로 처리된다. 값이 `NULL` 이면 기본값을 돌려준다. 따옴표·역슬래시는 그대로 저장한다. [코드] `src/namifax/services/system_config.py`; 시험 `tests/unit/test_system_config.py`, `tests/unit/test_system_config_atomic.py`, `tests/unit/test_system_config_migration.py`
- 비밀 값은 `set_secret`/`get_secret` 가 `secretbox` 로 암호화(`enc:v1:`)해 저장한다(`cloud_secret_key`). 키가 없으면 `SecretKeyError`. 자세히는 [[authentication-and-security]] 7절.
- 코드가 쓰는 키(2026-10-02, `src` 에서 `SystemConfigService` 사용처를 모두 열어 확인): 클라우드 `cloud_storage_type`, `cloud_bucket_name`, `cloud_endpoint_url`, `cloud_region_name`, `cloud_prefix`, `cloud_access_key`, `cloud_secret_key`(암호화); 수명주기 `storage_retention_days`, `storage_purge_tiff_days`, `storage_remote_sync_delete`, `storage_remote_tiff_only`(`storage_lifecycle.py` 가 읽는다. 관리자 화면(`views/admin.py`)에는 저장하는 곳이 없어 DB 에 직접 넣어야 한다 — `grep -rn storage_remote_tiff_only src`); 스케줄러 `sched_<설정>`(`sched_tmp_enabled`/`_time`/`_days`, `sched_inbox_enabled`/`_time`/`_days`, `sched_lifecycle_enabled`/`_time`, `sched_phonebook_enabled`/`_minutes`), `sched_engine_state`, `sched_stopped`, `sched_heartbeat`, 작업별 동적 키 `sched_running_<job>`·`sched_cancel_<job>`·`sched_last_<job>`(`services/scheduler_config.py`); 로그인 시도 제한 `login_throttle:user:<해시>`·`login_throttle:ip:<해시>`(`services/login_throttle.py`, 값은 JSON 카운터); SAML 의 `saml_*` 15개(`saml_enabled`, `saml_idp_entity_id`, `saml_idp_sso_url`, `saml_idp_x509_cert`, `saml_jit_provisioning`, `saml_default_role`, `saml_role_mapping`, `saml_role_attribute`, `saml_role_admin`, `saml_role_superuser`, `saml_role_can_del`, `saml_role_any_modem`, `saml_attr_modems`, `saml_attr_faxcats`, `saml_attr_didroutes` — `services/saml.py::saml_settings` 에서 세어 15개; [[authentication-and-security]] 5절). 이전 판의 목록에는 스케줄러 설정·`storage_remote_tiff_only`·로그인 제한 키가 빠져 있었다. 문자열 조립 키(`f"..."`)는 위 패턴으로만 있고 그 밖에는 확인하지 못했다.
- `key` 는 MySQL/MariaDB 예약어라 원시 SQL 에서는 따옴표가 필요하다(시험 도우미 `tests/conftest.py::_quote_key_column`). ORM 경로는 알아서 인용한다. [코드]
- SMTP 설정은 `SystemConfig` 가 아니라 별도 단일 행 테이블 `SystemSettings`(id=1)에 둔다. 비밀번호 열은 암호화 토큰이 들어가도록 `String(512)`(마이그레이션 `0022`). [코드] `src/namifax/models/systemsettings.py`
- `AVANTFAX_*`, `ENABLE_*`, `MAX_PASSWD_SIZE` 같은 원본 `local_config.php` 설정은 DB 가 아니라 환경변수에서 읽는다. [코드] `src/namifax/common/settings.py` (`flag`, `text`, `number`)

## 6. 세션 주입(`request.dbsession`)

- `models.includeme` 가 `pyramid_tm`(요청 단위 트랜잭션), `pyramid_retry`, `zope.sqlalchemy` 를 붙이고 `request.dbsession`(reify)을 만든다. 요청이 정상 끝나면 커밋, 예외면 롤백한다. `tm.manager_hook` 은 `pyramid_tm` include 전에 설정해야 한다. [코드] `src/namifax/models/__init__.py`; 시험 `tests/unit/test_models_includeme.py` (`test_tm_manager_hook_is_configured_before_pyramid_tm_is_included`, `test_aborted_request_transaction_discards_session_writes`)
- zope.sqlalchemy 는 변경이 감지된 세션만 커밋한다. 원시 SQL 로 쓴 변경은 `mark_changed` 없이 롤백된다. 시험 `test_models_includeme.py::test_raw_sql_without_mark_changed_is_rolled_back` [코드 + 문서 [[db-layer-refactor-log]]]
- 서비스 클래스는 세션을 생성자로 받는다(`Service(db=request.dbsession)`). 세션 없이 만들면 `MissingDatabase` 자리표시자가 되어 첫 사용에서 `RuntimeError`("no database session injected")로 크게 실패한다. 다른 DB 를 조용히 쓰지 않는다. [코드] `src/namifax/db/missing.py::resolve_db`; 시험 `tests/unit/test_global_engine_removed.py::test_repository_without_db_is_a_loud_placeholder`
- 시험 훅: 환경(`environ`)의 `app.dbsession` 이 있으면 요청이 그 세션을 쓰고, 설정 `dbengine` 이 있으면 그 엔진을 쓴다. 시험이 세션·엔진을 공유하기 위한 것이다. [코드] `models/__init__.py::includeme`; 시험 `test_models_includeme.py::test_environ_hook_lets_tests_share_a_session`, `test_dbengine_setting_hook_is_honoured`

## 7. 서버 DB 시험

- 표시: pytest 마커 `serverdb`(`pyproject.toml` 의 `markers`, `--strict-markers`). 서버 주소가 설정돼 있지 않으면 건너뛴다. [코드] `pyproject.toml`, `tests/conftest.py`
- 서버 URL 환경변수: `NAMIFAX_TEST_PG_URL`(PostgreSQL, `postgresql+psycopg://...`), `NAMIFAX_TEST_MYSQL_URL`(`mysql+pymysql://...`), `NAMIFAX_TEST_MARIADB_URL`(`mariadb+pymysql://...`). 값은 여기 적지 않는다. [코드] `tests/conftest.py::SERVER_DB_ENV`
- 도우미: `throwaway_database(kind)` 가 `nami_test_<임의>` 이름의 빈 DB 를 만들고(MySQL 은 `utf8mb4`) 시험 후 삭제한다. `server_db_url` 픽스처는 설정된 서버마다 한 번씩 돌린다. `legacy_db` 픽스처는 원본 AvantFAX 가 만든 MySQL/MariaDB 상태를 재현한다.
- 전체 시험을 서버 DB 로 돌리기: 환경변수 `NAMIFAX_SUITE_DB=postgresql|mysql|mariadb` 를 주면 `isolated_database` autouse 픽스처가 시험마다 임시 서버 DB 를 만들고 앱으로 스키마를 만든 뒤 데모 행을 넣는다(앱은 서버 DB 에 데모 데이터를 만들지 않으므로 시험 쪽에서 `_seed_server_database`). PostgreSQL 에서는 대소문자 혼합 테이블 이름을 따옴표로 감싸고, 시퀀스를 `sync_sequences` 로 맞춘다. [코드] `tests/conftest.py`
- 기본 실행은 시험마다 임시 SQLite 파일을 쓰고 작업 디렉터리의 `namifax.db` 는 건드리지 않는다(`DATABASE_URL`/`NAMIFAX_DB_PATH` 를 임시 경로로 설정). 시험 `tests/unit/test_db_isolation_fixture.py`
- 서버 시험이 있는 파일(`serverdb` 마커 또는 `server_db_url` 사용)은 `grep -rl "serverdb\|server_db_url" tests` 로 24개(그중 `conftest.py` 1개이므로 시험 파일 23개, 2026-10-02)가 나온다(예: `test_bootstrap.py`, `test_system_config_migration.py`, `test_orm_repository.py`, `test_user_account_orm.py`, `test_totp_orm.py`, `test_webauthn_orm.py`, `test_syslog.py`, `test_legacy_database_compat.py`). 개수는 시점에 따라 달라진다.
- 서버 DB 시험 결과(2026-10-02, 커밋 `baf16ca`, AI 가 Docker 임시 컨테이너로 직접 실행) [코드]: PostgreSQL 16.15, MySQL 8.4.11, MariaDB 10.11.16 이 각각 2456 passed, 실패 0건이다. 서버 버전, 시간, 앞선 실행(MySQL 계열 각 2 failed)의 기록은 [[testing]] 의 "마지막 실행 기록". 선생님이 같은 날 4개 DB 통합 시험을 직접 실행했다는 구두 보고도 있다(결과 세부는 기록 없음).
- **겹치는 요청에서의 쓰기 규칙** [코드]: (1) 읽고 나서 INSERT 하는 `merge` 는 두 연결이 같은 새 키를 함께 만들면 한쪽이 기본키 중복으로 실패한다. MySQL·MariaDB 는 `REPEATABLE-READ` 라서 트랜잭션이 처음 읽은 시점의 스냅샷이 고정되므로, 그 뒤에 다른 연결이 커밋한 키를 못 보고 INSERT 하다 실패하기도 한다(로그인 화면은 요청 첫머리에서 카운터를 읽으므로 요청이 끝날 때까지 이 창이 열려 있다). PostgreSQL 의 기본 `READ COMMITTED` 는 새 행을 보지만, 둘 다 "없다"고 읽은 경우는 같다. (2) 저장점 안에서 INSERT 하고 오류를 무시하는 방법과 존재하지 않는 행을 `SELECT ... FOR UPDATE` 로 잠그는 방법은 **MySQL·MariaDB 에서 교착(InnoDB 1213)을 낸다**: 틈새 잠금 때문에 두 요청이 서로를 기다리고 InnoDB 가 한쪽 트랜잭션 전체를 되돌려서, 이어지는 저장점 해제가 `1305 SAVEPOINT does not exist` 로 보인다. 40번 반복에서 13번 실패해서 버렸다. (3) 그래서 만들기와 덮어쓰기를 한 문장 upsert 로 하고, 이미 있는 행만 `FOR UPDATE` 로 잠근다. (4) 문장은 반드시 매핑된 클래스를 대상으로 해야 요청 트랜잭션이 커밋한다. [코드] `SystemConfigService` 를 쓰는 곳(2026-10-03 `grep`): 스케줄러 상태(`scheduler_config.py`: 실행 표지, 취소 요청, 마지막 결과, 정지 상태, 하트비트), 로그인 시도 제한(`login_throttle.py`), 관리자 화면의 설정(`views/admin.py`, `views/admin_scheduler.py`), 스토리지 수명주기·클라우드·SAML 설정 읽기. 겹치는 요청이 같은 새 키를 만들 수 있는 경로는 이 가운데 스케줄러의 키들과 로그인 카운터이고, 로그인 카운터는 시험으로 재현했다([[authentication-and-security]], [[testing]]).
- 이전 과거 문서의 "PostgreSQL 16 / MySQL 8.4 검증" 서술은 [[db-layer-refactor-log]] [문서]에 있고, 이번 실행의 서버 버전(PostgreSQL 16.15, MySQL 8.4.11)과 같은 계열이다.

## 8. 방언 주의점 (SQLite·MySQL·MariaDB·PostgreSQL에서 같게 돌리기)

원문 14.2(다중 DB 조사)와 14.11(NULL 정렬)에서 지금도 코드가 지키는 규칙만 옮겼다. 과거의 실패 목록(DDL 20개 실패, `INSERT OR REPLACE` 분포, 74곳 `quote()`)은 해결된 이력이라 뺐다(원문 14.2, 14.21).

**NULL 정렬(원문 14.11)**
- 문제: 오름차순에서 SQLite·MySQL 은 NULL 을 먼저, PostgreSQL 은 나중에 둔다. 규칙: **NULL 은 오름차순이면 먼저, 내림차순이면 나중**에 오게 고정한다.
- 구현 위치 두 곳. (1) `OrmRepository.select(order_by, descending)`: 정렬 열이 `nullable` 이면 `CASE WHEN col IS NULL THEN ...` 순위를 첫 정렬 키로 넣고, 그다음 열, 마지막에 기본키(동률 안정화). [코드] `src/namifax/db/orm_repository.py::select`. (2) 받은편지함 모뎀별 정렬은 `F.modemdev.is_(None).desc(), F.modemdev, F.fid.desc()` 로 NULL 을 항상 앞에 둔다("레거시 순서"라는 코드 주석). [코드] `src/namifax/services/archive_orm.py::list_inbox`
- 시험: `tests/unit/test_routes_and_modems.py::test_select_puts_null_values_first_when_ascending_on_every_backend`(NULL 별칭 행이 오름차순 맨 앞, 내림차순 맨 뒤). 이 시험에는 `serverdb` 마커가 없다. 서버 DB 에서 도는 것은 `NAMIFAX_SUITE_DB` 로 스위트 전체를 서버에 돌릴 때뿐이다(원문은 "서버 3종 테스트"라고 적음). [코드] 시험 파일 읽음, 실행 안 함.
- 새 쿼리 규칙: 널 가능 열로 정렬하는 쿼리는 `Repository.select` 를 쓰거나 위처럼 NULL 순서를 직접 명시한다. 모든 정렬 끝에 기본키 같은 유일 열을 붙여 순서를 고정한다(PostgreSQL 은 순서를 보장하지 않는다). [코드] `select`, `find`, `search_text` 가 모두 기본키로 마무리.
- 문자열 정렬(한글·영문 혼합)은 DB collation 이 정하므로 계약에 넣지 않는다. 시험은 ASCII 항목의 상대 순서만 확인한다. [코드] `tests/unit/test_orm_repository.py::test_server_database_repository_behaviour`(`# collation decides where 한글 goes`)

> 모순: `search_text(column, text, order_by=...)` 는 `order_by` 열이 NULL 가능이어도 위 NULL 보정을 하지 않고 `order_by(order_col, pk)` 만 쓴다(`orm_repository.py::search_text`). 현재 호출처가 NULL 열로 정렬하는지는 확인하지 않았다. 새로 쓸 때는 이 점에 주의. [코드]

**대소문자·이름 접힘·예약어(원문 14.2, 14.3)**
- 테이블·열 이름은 레거시 철자(대소문자 혼합)를 유지한다. 이유: MySQL/MariaDB 리눅스는 테이블 이름 대소문자를 구분하고, PostgreSQL 은 따옴표 없는 이름을 소문자로 접는다. ORM 은 이름을 인용해 문제없지만 **손으로 쓴 원시 SQL 은 PostgreSQL 에서 실패**한다. 그래서 서버 DB 시험은 원시 SQL 대신 모델 기반 쿼리(`select(func.count()).select_from(Model)`)를 쓰고, 옛 원시 SQL 시험은 conftest 의 보정 리스너가 따옴표를 씌운다. [코드] `tests/conftest.py::_quote_bare_tables`, `_quote_key_column`
- 예약어 `key`(`SystemConfig.key`)는 ORM 이 알아서 인용하며(MySQL 은 백틱), DDL 컴파일 시험이 이를 확인한다. [코드] `tests/unit/test_system_config.py`(`"`key`" in ddl`)
- 모든 `String` 열은 길이를 가진다(MySQL/MariaDB 는 길이 없는 `VARCHAR` 를 못 만든다). [코드] `tests/unit/test_system_config.py::test_every_string_column_has_a_length`
- 긴 본문은 `Text().with_variant(LONGTEXT, "mysql", "mariadb")`(일반 `TEXT` 는 MySQL 에서 64KB). [코드] `src/namifax/models/faxocr.py::LongText`

**값·타입(원문 14.2, 14.8, 14.13, 14.15)**
- 값은 항상 바인드 파라미터다. 문자열 이스케이프(`quote()`)는 코드에서 사라졌다. MySQL 계열의 역슬래시 이스케이프 문제는 "값을 문자열에 끼워 넣지 않는다"로 풀렸다. 시험은 `x\' OR 1=1 --` 같은 값이 그대로 저장·조회되는지 본다. [코드] `grep "def quote" src` 결과 없음; `tests/unit/test_system_config.py::test_service_stores_quotes_and_backslashes_verbatim`
- 정수 열 비교에 `"5"` 문자열을 주면 PostgreSQL 은 자동 변환하지 않아 실패한다 → `OrmRepository._coerce` 가 열 타입에 맞게 변환하고, 변환할 수 없는 값(`"abc"`)과 `None` 은 아무것도 일치시키지 않는다(`sa.false()`). 정수 열과 `''` 를 비교하지 않는다(archive_orm 의 `_eq_int` 도 숫자가 아니면 일치 없음). [코드] `orm_repository.py::_coerce`, `find`; `services/archive_orm.py` 29~35행; 시험 `test_orm_repository.py` (`catid: "abc"`)
- 불리언: 옛 코드가 텍스트 `'False'` 를 저장했고 `Boolean` 은 비어 있지 않은 텍스트를 참으로 읽어 권한 상승이 됐다(원문 14.13). 지금은 `LegacyBoolean` 이 드라이버 원시 값을 읽어 알 수 없는 문자열은 거짓으로 처리한다. 새 불리언 열은 이 타입을 쓴다. [코드] `src/namifax/models/types.py`; 시험 `tests/unit/test_boolean_flags.py`
- 날짜·시각: 앱은 ISO 문자열로 다루고(`IsoText`), 날짜 접두어 검색은 `startswith(..., autoescape=True)` 다. 원문 14.4 는 `SysLog.logdate` 를 문자열로 둔 이유를 "PostgreSQL timestamp 에는 날짜 접두어 `LIKE` 가 안 된다"로 적는다. [코드] `models/types.py::IsoText`, `models/syslog.py`(`IsoText(32)`), `services/syslog.py`(`startswith`) / [문서] 이유 부분
- 부분 일치 검색: `lower(col) LIKE 패턴 ESCAPE '!'`, 입력의 `%`·`_`·`!` 는 리터럴. `ESCAPE '!'` 는 모든 DB 에서 같은 뜻이다. [코드] `src/namifax/db/textsearch.py`, `OrmRepository.search_text`; 시험 `test_orm_repository.py::test_search_text_is_case_insensitive_ordered_and_literal_on_both_backends`, `tests/unit/test_addressbook_search_injection.py`
- 페이지 나누기는 `LIMIT/OFFSET`(SQLAlchemy `.limit().offset()`). MySQL 식 `LIMIT a, b` 는 쓰지 않는다. [코드] `archive_orm.py` 77, 175행
- `find` 는 `None` 비교를 `= NULL` 처럼 취급해 일치 0건(레거시 의미 보존). 갱신·삭제는 대상이 없어도 성공. DB 오류(고유 제약 등)는 `False` 가 아니라 예외. [코드] `orm_repository.py::find`; 시험 `test_orm_repository.py` (`= NULL matches nothing`, `IntegrityError`)

**원시 SQL 이 남은 곳**: 상수에서 만든 DDL·보정(`db/adopt.py`, `db/sqlite_upgrade.py`)뿐이다(위 3절). SQLite 전용 구문은 `sqlite_upgrade.py` 에만 둔다.

## 9. 시드 안전 규칙 (시작할 때마다 기존 데이터를 건드리지 않는다)

배경(원문 14.9): 옛 `db/schema.py` 는 **앱을 시작할 때마다** 데모 값을 다시 적용했다 — `admin` 비밀번호 기본값 복원, 모뎀·카테고리·표지를 `INSERT OR REPLACE` 로 덮어씀, 1번 행(DID·주소록·목록·`DynConf`)을 데모 값으로 덮어씀, 받은 팩스가 없으면 **실제 팩스 #1 을 데모 행으로 교체**, NULL 인 `faxnumid`/`modemdev` 를 데모 값으로 채움. 지금 이 파일들은 없고 규칙만 남았다.

규칙(현재 코드):
1. 시드는 시작·훅 호출마다 돌 수 있으므로 **이미 있는 데이터를 바꾸지 않는다**. [코드] `src/namifax/db/seed.py` 모듈 docstring("Both run on every start, so they must never alter data that already exists.")
2. 데모 데이터는 **SQLite 이고 사용자가 0명인 새 DB 이고 명시적으로 켰을 때만**(`NAMIFAX_DEMO_DATA=1` 또는 `demo.data`). 서버 DB 는 요청해도 경고하고 무시한다. 기존에 사용자가 있는 DB 에는 켜도 데모 행이 들어가지 않는다. [코드] `db/bootstrap.py::demo_data_wanted`, `db/seed.py::seed_if_empty`; 시험 `test_demo_data_optin.py`(`test_the_switch_never_touches_a_database_that_already_has_users`, `test_the_demo_data_is_not_created_on_servers_even_if_asked`)
3. 기본 레코드(표지 3종)는 **테이블이 비어 있을 때만** 넣는다. 카테고리는 만들지 않는다(원본 설치도 카테고리 없음). [코드] `seed.py::seed_default_records`; 시험 `test_schema_seed_safety.py::test_the_original_default_cover_pages_are_provided_and_no_categories_are_made_up`
4. 행 추가는 `_add_missing`(키가 있으면 건너뜀, `INSERT OR IGNORE` 의미)이고, 모든 개별 시드 블록은 "테이블이 비었을 때"(`_count(...) == 0`, 모뎀·DID 는 `< 2`) 또는 "그 이름의 행이 없을 때"만 실행한다. `INSERT OR REPLACE`, 복구용 `else: UPDATE`, 데모 마이그레이션 UPDATE 는 없다. [코드] `seed.py`
5. 기본 시드는 새 DB(`UserAccount` 테이블이 없던 DB)에서만 돈다(`elif fresh`). [코드] `bootstrap.py::ensure_schema`
6. 새 DB 는 **첫 시작에서** 완전해야 한다(두 번째 시작에서야 채워지면 안 됨). 예: 데모 받은 팩스 #1 의 `companyid` 는 같은 시드 호출 끝에서 Acme 주소록 항목에 연결한다. [코드] `seed.py` 끝부분; 시험 `tests/unit/test_schema_seed_first_run.py` (원문 13.5, 14.9)
7. 서버 DB 에는 데모 계정(알려진 비밀번호)을 만들지 않는다. 첫 관리자는 `namifax createuser`. [코드] `bootstrap.py` docstring, `test_demo_data_optin.py`

지키는 시험:
- `tests/unit/test_schema_seed_safety.py`: 데모 행을 "관리자가 고친 운영 데이터"로 바꾼 뒤(비밀번호 변경, 모뎀 삭제·수정, 바코드 기본키 변경, 팩스 삭제·수정 등) `upgrade_schema()` 를 다시 돌려 **모든 테이블 스냅샷이 같아야** 한다(`test_restarting_changes_nothing_in_a_database_with_real_data`). 사용자가 이미 있는 DB 는 데모 행이 늘지 않는다. 새 DB 재시작은 멱등.
- `tests/unit/test_schema_seed_first_run.py`: 첫 시작에 팩스 #1 이 Acme 에 연결되고, 두 번째 시작에서 건수가 같다.
- 새 시드를 추가할 때: 위 스냅샷 시험이 새 테이블까지 자동으로 보지만, 데모 행을 "고친 데이터"로 바꾸는 목록(`_as_edited_production_data`)에는 새 행을 직접 추가해야 보호가 확인된다. [코드] 그 목록은 손으로 쓴 UPDATE·DELETE 문 14개이고(`tests/unit/test_schema_seed_safety.py` 31~51행), 시드된 테이블과 대조하는 시험은 없다(그 파일의 시험은 4개). 그래서 새 시드 행은 직접 추가해야 보호된다.

> 모순: 원문 14.9 는 구조용 백필 `_backfill_alias_columns` 를 "마이그레이션 직후와 시드 직후"에 돌린다고 적었다. 지금은 `db/sqlite_upgrade.py::_backfill_alias_columns` 로 존재하지만 SQLite 옛 테이블 보정 단계에서만 호출된다(`sqlite_upgrade.py` 53행, 시드 뒤가 아님). 또 원문은 기본 카테고리 3개와 표지 2개를 시드한다고 적었으나(14.16) 지금은 표지 3개뿐이다. [코드]
> 관찰: 새 SQLite 데모 DB 의 `admin`/`password` 는 데모를 켠 개발·시험 전용이다. 기본(꺼짐)에서는 만들어지지 않는다. [코드] `test_demo_data_optin.py::test_nobody_can_log_in_with_the_old_demo_password_on_a_default_start`
