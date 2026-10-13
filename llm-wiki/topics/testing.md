---
title: 시험
type: topic
updated: 2026-10-13
sources: [pyproject.toml, tests/conftest.py, tests/sqlsession.py, tests/request_identity.py, tests/unit/test_ko_catalog_complete.py, tests/unit/test_legacy_trees_removed.py, tests/unit/test_fax_archive_orm.py, tests/unit/test_migrations_match_models.py, tests/test_i18n.py, tests/fixtures/, tests/unit/test_login_throttle.py, tests/unit/test_session_secure_flag.py, tests/unit/test_remote_upload.py, tests/unit/test_env_file_wiring.py, tests/unit/test_serve_main_db.py, tests/unit/test_global_engine_removed.py, tests/unit/test_db_injection.py, tests/unit/test_multi_dialect_safety.py, tests/unit/test_state_changing_posts.py, tests/unit/test_logout_post.py, tests/unit/test_origin_guard.py, tests/unit/test_legacy_redirects.py, tests/unit/test_db_isolation_fixture.py, tests/unit/test_alembic_wiring.py, tests/unit/test_demo_data_optin.py, tests/unit/test_sso_and_2fa_login.py, tests/unit/test_active_mailer.py, tests/unit/test_pyramid_modals_action.py, tests/unit/test_user_account.py, tests/unit/test_webauthn_orm.py, tests/unit/test_totp_orm.py, src/namifax/views/modals.py, src/namifax/common/helpers.py, src/namifax/db/bootstrap.py, tools/migration_rehearsal/, "[[architecture-md-part2]]", "[[agents-md-legacy-instructions]]", "[[db-layer-refactor-log]]"]
verified: true
---

# 시험

## 구성
- 도구: `pytest`, `pytest-cov`, `webtest`(dev 의존성 그룹). 설정은 `pyproject.toml` 의 `[tool.pytest.ini_options]`: `--strict-markers`, `testpaths = ["tests"]`, `pythonpath = [".", "src"]`, `faulthandler_timeout = 20`(20초 넘게 끝나지 않는 시험은 모든 스레드 스택을 stderr 에 덤프하고 계속 진행). [코드] `pyproject.toml`
- 디렉터리: `tests/conftest.py`(공용 픽스처), `tests/sqlsession.py`, `tests/request_identity.py`, `tests/test_i18n.py`, `tests/test_helpers_media.py`, `tests/web/`(`test_web_addressbook.py`, `test_web_inbox_views.py`), `tests/unit/`(나머지 전부: `test_*.py` 213개, 2026-10-02 `git ls-files tests/unit` 로 셈), `tests/unit/linked_db.py`, `tests/unit/data/fax_archive_search_golden.json`, `tests/fixtures/`(`legacy_sendfax_commands.json`, `legacy_sql/create_tables.sql`, `legacy_sql/db-update-334.sql`). [코드] `git ls-files tests`
- 시험 개수: `uv run pytest --collect-only -q` 로 2026-10-02 에 **2390개 수집**됨(수집만 했고 실행하지 않음. 이전 판의 2314개에서 늘었다). 이 수치는 곧 낡는다. [코드] 같은 명령
- 이번 코드 변경(커밋 `ad5dc09..HEAD`)으로 새로 생긴 시험 파일과 수집된 개수(`uv run pytest --collect-only -q <파일>`, 2026-10-02): `test_login_throttle.py` 9(비밀번호 로그인 시도 제한: 계정은 기본 5회 실패로 잠기고 관리자만 해제, 주소는 그 10배(50회)·15분 잠금, 상태는 DB 에 저장; 아래 수치 중 "10회"는 2026-10-03 이전 값, 상태는 DB 에 저장), `test_session_secure_flag.py` 5(`session.secure` ini 가 `NAMIFAX_SESSION_SECURE` 보다 우선), `test_remote_upload.py` 8(S3 선택 시 수신 팩스 TIFF+PDF 를 `fax<fid>` 키로 업로드, 실패해도 수신은 성공, 원격 TIFF 만 남기는 정책, `delete_fax` 접두사 버그), `test_env_file_wiring.py` 17(`/etc/namifax.env` 가 systemd 단위·cron 4줄·훅 4종에 전달됨), `test_serve_main_db.py` 6(`serve_main` 의 스키마 보장과 `--config`/`NAMIFAX_INI`). 파일 이름과 첫 시험 이름·docstring 으로 확인했고 각 시험 본문을 모두 읽지는 않았다. [코드]
- 시험 이름이 `*_request_db.py`, `*_db.py`, `*_orm.py` 인 파일은 요청 세션 주입, 서비스 DB 주입, ORM 구현을 각각 확인하는 묶음이다. [코드] `ls tests/unit`
- 영역별 파일 예(실제로 있는 이름만): CLI 훅(`test_cli_faxrcvd*`, `test_cli_notify*`, `test_cli_cron*`, `test_cli_dynconf`, `test_cli_faxcover`), 보관함(`test_archive_*`), 인증(`test_auth_*`, `test_totp*`, `test_webauthn*`, `test_saml*`, `test_security_*`), 스케줄러(`test_scheduler*`), 저장소(`test_storage_*`, `test_cloud_storage`), 마이그레이션(`test_alembic_wiring`, `test_migrations_match_models`, `test_sqlite_upgrade`, `test_legacy_database_compat`), i18n(`test_ko_*`, `tests/test_i18n.py`). [코드] `git ls-files tests`

## 픽스처와 격리 ([코드] `tests/conftest.py`)
- 모듈 맨 위에서 `NAMIFAX_ARGON2_*` 를 `setdefault` 한다(아래 "시험 속도" 항목).
- `isolated_database`(autouse): 시험마다 `tmp_path` 의 SQLite 파일을 만들어 `DATABASE_URL`, `NAMIFAX_DB_PATH` 로 지정하고 `AFDB_URL` 은 지운다. 작업 트리의 `namifax.db` 는 건드리지 않는다.
- `_demo_data`(autouse): `NAMIFAX_DEMO_DATA=1`(샘플 계정과 행 생성; 앱 설정 `demo.data` 로도 켠다). 기본 동작을 시험할 때는 이 변수를 시험 안에서 지운다(`test_demo_data_optin.py` 의 `no_demo` 픽스처).
- `_secret_key`(autouse): 고정 `NAMIFAX_SECRET_KEY`. 키가 없는 경우를 시험할 때만 지운다(`test_secret_box.py`, `test_totp_enrollment.py` 가 `delenv`).
- 시험 속도를 위해 Argon2 비용을 낮춘다(`NAMIFAX_ARGON2_TIME_COST=1`, `MEMORY_COST=1024`, `PARALLELISM=1`; 운영은 라이브러리 기본값).
- `dbengine`, `app`(= `create_app(dbengine=engine)`), `tm`(실행 취소되는 트랜잭션 관리자), `dbsession`, `testapp`(WebTest, `HTTP_HOST=example.com`), `app_request`, `dummy_request`, `dummy_config`, `admin_call`(관리자 권한으로 뷰 직접 호출), `alembic_cfg`(마이그레이션 환경의 사본), `as_superuser`(`FaxAccess.for_request` 를 슈퍼유저로 바꿈). 쓰기는 `tm.doom()` 으로 시험 끝에 사라진다.
- `seeded_db`: 스키마와 시드가 들어간 메모리 `SqlSession`(`tests/sqlsession.py`, 옛 시험이 쓰는 원시 SQL 편의 메서드를 가진 `Session`). 기본으로 데모 데이터까지 넣는다(`seeded_session(seed=True)`). `tests/request_identity.py` 의 `set_identity` 는 `DummyRequest` 에 뷰가 실제로 보는 `identity` 를 심는다.
- PostgreSQL 용 보정: 따옴표 없는 혼합 대소문자 테이블 이름을 따옴표로 감싸는 리스너, MySQL 계열에서 예약어 `key` 를 백틱으로 감싸는 리스너, 시퀀스 보정(`sync_sequences`).
- 같은 이유로 원시 SQL 시험은 서버 DB 에서 돌 때 이 보정에 기대고 있다. [코드] 같은 파일

## 서버 DB 시험 (`serverdb` 마커)
- 마커 정의(영문 원문 `serverdb: runs against a throw-away database on a real PostgreSQL, MySQL or MariaDB server ... skipped when the server URL is not configured` 의 번역). [코드] `pyproject.toml`
- 환경변수(없으면 해당 시험은 skip): `NAMIFAX_TEST_PG_URL`(예 `postgresql+psycopg://user:pw@host:port/postgres`), `NAMIFAX_TEST_MYSQL_URL`(`mysql+pymysql://...`), `NAMIFAX_TEST_MARIADB_URL`(`mariadb+pymysql://...`). 접속 정보 값은 위키에 적지 않는다. [코드] `tests/conftest.py` `SERVER_DB_ENV`
- `throwaway_database(kind)` 가 `nami_test_<8자리>` DB 를 만들고(MySQL 계열은 `utf8mb4`) 끝나면 지운다. 픽스처 `server_db_url` 은 설정된 서버마다 1회씩 돈다. `legacy_db` 픽스처는 원본 AvantFAX 가 만든 DB(`3.3.5`, `3.2.0`)를 MySQL/MariaDB 에 재현한다(`tests/fixtures/legacy_sql`). [코드] `tests/conftest.py`
- **스위트 전체를 서버 DB 로 돌리기**: `NAMIFAX_SUITE_DB=postgresql|mysql|mariadb`(해당 `NAMIFAX_TEST_*_URL` 필요). 그러면 `serverdb` 마커가 없는 시험도 시험마다 일회용 서버 DB 에서 돌고, 데모 행은 `seed_demo_records` 로 직접 넣는다(앱은 SQLite 에서만 데모 데이터를 만든다). [코드] `tests/conftest.py` `isolated_database`, `src/namifax/db/bootstrap.py`
- 실행 예: `NAMIFAX_TEST_PG_URL=... uv run pytest -m serverdb`. [코드, 측정 2026-10-03] 이 명령 그대로 PostgreSQL 16 임시 컨테이너 하나만 주었을 때 32 passed, 136 skipped, 2309 deselected, 약 11초였다(MySQL·MariaDB 주소가 필요한 시험은 건너뜀).
- DB 쪽 설계는 [[database-and-migrations]].

## 실행 명령
- 전체: `uv run pytest` / 수집만: `uv run pytest --collect-only -q` / 한 파일: `uv run pytest tests/unit/test_ko_catalog_complete.py` / 키워드: `-k`. [코드] `pyproject.toml` 설정과 표준 pytest 사용법
- 주의: `tests/test_i18n.py::test_i18n_cli_compile` 은 `.mo` 파일을 다시 쓴다. [코드] [[i18n-and-ui]]
- 주의: 시험은 임시 DB 를 쓰고 WebTest 로 앱을 직접 호출하므로 개발 서버와 독립이다. 예외로 `tests/unit/test_active_mailer.py` 는 `127.0.0.1` 에 임시 소켓을 열어 메일 전송을 끝까지 시험한다. [코드] `tests/conftest.py`, `tests/unit/test_active_mailer.py`

## 골든 마스터는 삭제되었다
- 이전 방식의 골든 마스터(레거시 입출력, 웹 HTML/폼 계약 스냅샷)와 `dev/`, `legacy/` 는 저장소에 없다. 삭제 커밋: `dev/` → `01f2f64`(그 부모 `72a7324` 에서 `dev/` 를 읽는다), `legacy/` → `083920e`(그 부모 `9408385` 에서 읽는다), `golden_master`·`specs`·`prompts` 를 `dev/` 로 옮긴 커밋 `72a7324`. 필요하면 `git show <커밋>:<경로>` 로 읽는다. [코드] `git log`, `git ls-files`
- 영향:
  - 레거시 PHP 를 기준으로 한 차분 비교(원본과 같은 HTML/DOM, 같은 훅 출력)는 더 이상 시험이 자동으로 지켜 주지 않는다. 그 역할은 현재 시험이 기대값을 직접 박아 둔 방식(예: `tests/fixtures/legacy_sendfax_commands.json`)으로 부분적으로만 남아 있다. [코드] 파일 존재. 원본 HTML 이나 훅 출력과 비교하는 자료를 읽는 시험은 없다(2026-10-03 `grep -rn "contract.json\|response.html\|golden_master" tests` 는 `W04`, `W05` 같은 옛 화면 이름이 시험 설명 문구에 남은 것만 찾았다). 따라서 대체는 부분적이다.
  - 원본의 SQL 은 시험 기반 자료로만 남았다: `tests/fixtures/legacy_sql/*.sql`. [코드]
  - "골든" 이라는 이름은 한 군데 남아 있다: `tests/unit/data/fax_archive_search_golden.json` 는 옛 SQL 구현을 지우기 전에 기록한 보관함 검색 응답이며 ORM 쿼리가 같은 답을 내야 한다(서버 DB 시험에서도 같은 행렬이 돈다). 이것은 레거시 PHP 골든 마스터와 다른 것이다. [코드] `tests/unit/test_fax_archive_orm.py`
  - 원본과 새 코드를 나란히 돌리는 이관 리허설 도구는 `tools/migration_rehearsal/` 에 따로 있다(시험 스위트 밖). [코드] `git ls-files tools`
- 삭제 상태를 확인하는 시험: `test_legacy_trees_removed.py`(`avantfax` 패키지, `namifax.web` 부재, 배치 도구 5종(`ocr_import`, `create_thumbnails`, `import_users`, `import_blacklist`, `reroute`)이 `namifax.cli` 에 있음, `serve_main` 이 앱 생성 실패 시 대체 앱 없이 코드 1 로 끝남). [코드]
> 모순: [[architecture-md-part2]], [[agents-md-legacy-instructions]] 는 "모듈 하나를 교체할 때마다 골든 마스터 E2E 를 돌린다" 를 규칙으로 말한다. 지금은 골든 마스터가 없으므로 이 절차를 그대로 따를 수 없다. [코드] 위 삭제 근거.

## 시험이 지키는 주요 규칙
| 규칙 | 시험 | 비고 |
|---|---|---|
| 모든 메시지가 한국어로 번역됨 | `test_ko_catalog_complete.py::test_every_message_of_the_template_is_translated_into_korean` | `.pot` 기준, fuzzy 불가 |
| 번역이 자리표시자를 유지함(위키 지시문의 `placeholders_translated`) | 같은 파일 `test_translations_keep_the_placeholders_of_the_original_text` | `%(x)s`, `%d` 등 |
| 컴파일된 `.mo` 가 새 문구를 가짐 | 같은 파일 | `.mo` 재컴파일 필요 |
| 화면이 `?lang=ko` 로 한국어로 나옴 | `test_ko_pages.py` | |
| 로케일 24개, 별칭, 협상 우선순위 | `tests/test_i18n.py`(5개 시험) | `len(SUPPORTED_LOCALES) == 24` |
| 마이그레이션과 모델이 일치함 | `test_migrations_match_models.py`(`upgrade head` 뒤 `compare_metadata` 차이 없음. 모델에 없는 옛 테이블 `remove_table` 은 제외), `test_alembic_wiring.py`(Alembic 이 앱의 DB URL·메타데이터를 씀) | 모델만 바꾸고 리비전을 안 넣으면 SQLite 시험이 실패하는 구조(코드로 확인) |
| 요청 단위 DB 주입, 전역 엔진 없음 | `test_global_engine_removed.py`(주입한 세션 없이는 도메인 클래스가 다른 DB 를 쓰지 않음), `test_db_injection.py`(DB URL 해석 순서, 앱끼리 격리), `test_*_request_db.py` | |
| 스키마 초기화 실패를 숨기지 않음(`create_app`, CLI 세션) | `test_multi_dialect_safety.py` | 파일 docstring "fail fast on schema errors" |
| 데모 데이터는 명시적으로 켤 때만 | `test_demo_data_optin.py` | 기본 꺼짐 |
| 상태 변경은 세션 CSRF 토큰이 든 POST(회전, 회사 지정, 로그아웃) | `test_state_changing_posts.py`, `test_logout_post.py` | 출처(`Origin`/`Referer`) 검사는 `test_origin_guard.py` |
| 구형 트리 제거 유지 | `test_legacy_trees_removed.py` | |
| 옛 `*.php` 주소 리다이렉트 규칙이 앱 주소와 어긋나지 않음 | `test_legacy_redirects.py` | 규칙 자체는 실제 웹 서버로 시험 |
| 로그인 시도 제한 | `test_login_throttle.py` | 계정 5회(관리자만 해제)·주소 50회/15분 |
| 겹치는 요청에서 설정 키·로그인 실패 횟수 | `test_system_config_atomic.py` | 일부는 서버 DB 필요(`serverdb`) |
| 비밀번호 확인 전에 시도를 센다(한 번에 몰려도 한도만큼만 확인) | `test_login_throttle_reserve.py` | 일부는 서버 DB 필요(`serverdb`) |
| 세션 쿠키 Secure 플래그 | `test_session_secure_flag.py` | ini 우선 |
| 수신 팩스 S3 업로드와 원격 정책 | `test_remote_upload.py` | |
| env 파일 배선 | `test_env_file_wiring.py` | systemd·cron·훅 |
| 시험이 DB 를 건드리지 않음 | `test_db_isolation_fixture.py` | |
[코드] 파일 존재는 `git ls-files tests` 로, 시험 이름과 docstring 은 각 파일 앞부분을 읽어 확인했다(모든 시험 본문을 읽은 것은 아니고 실행하지 않았으므로 통과 여부는 주장하지 않는다). `test_db_isolation_fixture.py` 는 `cli_session` 과 기본 URL 이 작업 트리 DB 를 건드리지 않는지 확인한다.
- 관련: [[architecture-and-modules]], [[overview]]

## 마지막 실행 기록
- [코드] 2026-10-03, 커밋 `c87a87d`(계정 잠금을 관리자만 해제), SQLite 전체: 2307 passed, 169 skipped, 약 4분 39초. 서버 3종 전체: 각 2467 passed, 3 skipped, **6 failed**(PostgreSQL 약 20분 15초, MySQL 약 31분 27초, MariaDB 약 25분 20초). 실패 6건은 세 서버 모두 같은 두 시험 `test_failures_that_arrive_together_are_all_counted`, `test_failures_on_an_existing_counter_are_all_counted` 였고, 기본 한도가 10일 때 8번을 센다고 가정한 시험의 오류였다(5번째에서 잠기고 이후는 세지 않는 것이 새 동작). 한도를 100으로 올려 고쳤고, 고친 뒤에는 잠금 관련 4개 파일(`test_system_config_atomic`, `test_login_throttle_reserve`, `test_login_account_lock`, `test_login_throttle`)만 서버 3종에서 다시 돌려 각 65 passed 였다. **고친 뒤 서버 3종 전체 시험은 다시 돌리지 않았다.**
- [코드] 2026-10-02, 커밋 `baf16ca`, SQLite 전체: `.venv/bin/python -m pytest tests -q -p no:randomly` → 2290 passed, 169 skipped(서버 DB 시험은 서버 주소가 없어 건너뜀), 약 5분 8초.
- [코드] 같은 커밋, 서버 DB 전체: `NAMIFAX_SUITE_DB=<종류>` 와 `NAMIFAX_TEST_*_URL` 로 세 서버를 동시에 실행. 서버는 Docker 임시 컨테이너(`postgres:16` = 16.15, `mysql:8.4` = 8.4.11, `mariadb:10.11` = 10.11.16).
  | 서버 | 결과 | 시간 |
  |---|---|---|
  | PostgreSQL 16.15 | 2443 passed, 3 skipped | 약 18분 9초 |
  | MySQL 8.4.11 | 2443 passed, 3 skipped | 약 32분 12초 |
  | MariaDB 10.11.16 | 2443 passed, 3 skipped | 약 24분 56초 |
- [코드] 새 시험 `test_system_config_atomic.py`(서버 DB 시험 21개 포함)와 `test_login_throttle_reserve.py`(서버 DB 시험 6개 포함)는 서버 3종 + SQLite 에서 25번 연달아 돌려 실패 0건이었다(2026-10-02, 두 파일과 `test_login_throttle.py` 합계 48건).
- 앞선 실행(커밋 `0c77622`)에서는 MySQL·MariaDB 가 각각 2 failed 였다: `test_scheduler_admin.py` 의 시험 2건이 `SystemConfig` 의 `sched_heartbeat` 를 INSERT 하다 `Duplicate entry`(1062). 원인 확인 [코드]: MySQL 전역 격리 수준을 `READ-COMMITTED` 로 바꾸면 통과하고 `REPEATABLE-READ` 에서는 실패(두 수준으로 각각 실행). `SystemConfigService.set` 이 `merge`(읽은 뒤 INSERT) 라서 낡은 스냅샷에서 이미 있는 키를 INSERT 하려던 것이다. 이 원인이 로그인 제한에도 있어 병렬 로그인 실패가 덜 세어지는 것을 웹 요청으로 측정했고(아래), 둘 다 `c353db5` 에서 고쳤다. 방법과 실패한 시도는 [[database-and-migrations]] 7장.
- [코드] 로그인 실패 병렬 측정(2026-10-02, 로그인 화면에 틀린 비밀번호를 동시에 N개, 새 사용자·새 IP, 당시 한도 10, 지금은 계정 5·주소 50): 고치기 전 MySQL 은 N=3~40 에서 기록 1~3회, 요청의 70~90% 가 "database unavailable" 화면; PostgreSQL 은 N=10 에서 기록 3~5회. 고친 뒤 두 DB 모두 오류 화면 0건, 기록 횟수가 한도(10)까지 정확하고 한도에 닿으면 잠긴다(N=3 은 3회, N=10·40 은 10회에서 잠금). 동시에 출발시킨 최악의 경우이고, 같은 프로세스 안의 스레드로 보낸 요청이라 네트워크 지연은 없다. 그 뒤 비밀번호 확인 전에 시도를 먼저 세도록 바꿨고(`baf16ca`), 로그인 화면에 틀린 비밀번호를 동시에 30개 보내는 시험에서 비밀번호 확인은 한도(시험은 3)만큼만 일어나고 나머지는 "too many attempts" 화면을 받는다(세 서버).
- 같은 날 선생님이 4개 DB 통합 시험을 직접 실행했다고 알려 주셨다(구두 보고, 결과 세부는 기록 없음). 위 실행은 그와 별개로 AI 가 같은 방법으로 다시 돌린 것이다.
- 골든 마스터는 기본 실행 대상에서 빠졌고 원본 트리도 삭제되어 실행하지 않았다.

## mock 시험의 함정 (원문 14.12~14.14, 14.19)

[[db-layer-refactor-log]](원본 삭제됨, `git show 54dd654:docs/history/db-layer-refactor-log.md`)에서 mock 이 결함을 가렸던 사례 중 시험 작성에 쓸 교훈만 옮겼다. 해결된 결함 자체의 설명은 뺐다.

| mock 이 한 일 | 가려진 결함(원문) | 대신 한 것 |
|---|---|---|
| `NFUserAccount`·서비스·세션을 가짜로 대체한 로그인 시험 | 앱에 HTTP 세션 팩토리가 없어 2FA 사용자 로그인이 500, 패스키 챌린지 미저장, SAML·패스키 뷰가 없는 메서드를 호출, 로그인이 인증 토큰이 아니라 세션만 기록(14.19) | 실제 앱·DB·WebTest 로 로그인까지 가는 `test_sso_and_2fa_login.py`. 파일 docstring 이 위 이유를 적고 있다 |
| 웹 "팩스 이메일 전송" 시험이 `Mailer` 를 가짜로 대체 | 뷰가 없는 `mailer.send_mail(...)` 을 불러 `AttributeError`(14.6) | 뷰가 `send_mail` 헬퍼를 호출하고, 발송 자체는 시험 안의 가짜 SMTP 서버(실제 소켓)로 끝까지 확인(`test_active_mailer.py`) |
| `db.query()` 가 리스트를 반환한다고 가정한 mock | 서비스도 같은 잘못된 가정을 해서 패스키 목록·OCR 색인이 한 번도 동작하지 않음(14.14; OCR 색인 `FaxOCR` 은 2026-10-13 에 제거) | 실제 세션 시험(`test_webauthn_orm.py`, `test_totp_orm.py`) |
| 결함 있는 동작을 기대값으로 고정한 시험 | 계정 삭제가 `username IS NULL` 갱신을 기대(NOT NULL 열이라 실제 DB 에서는 실패)(14.13) | 기대값을 새 동작(`deleted.<uid>` 등)으로 수정. 현재 `test_user_account.py::test_remove_account` 가 그렇다 |

교훈
- mock 이 반환 **형태**까지 정하면 서비스와 시험이 같은 오해를 공유해 통과한다. 경계(DB, 메일 서버, 파일 시스템)는 가능하면 진짜(임시 SQLite, 임시 소켓)로 두고, 가짜는 외부 서비스에만 쓴다.
- 존재하지 않는 속성을 `MagicMock()` 으로 만들면 오타·삭제된 API 도 통과한다. 쓰려면 `spec=`/`autospec=` 로 실제 객체의 모양을 강제한다. [코드, 측정 2026-10-03] `MagicMock()` 은 없는 메서드 호출도 통과하고 `MagicMock(spec=클래스)` 는 `AttributeError` 를 낸다(실행 확인). 이 저장소의 `tests/` 에는 `MagicMock(` 이 196곳이고 `spec` 을 준 것은 0곳, `autospec` 은 2곳이어서 일괄 적용된 규칙은 아니다.
- 사용자 흐름(로그인, 저장, 발송)은 mock 시험 외에 **실제 앱 + WebTest 한 번**의 끝-끝 시험을 둔다. `testapp`, `dbsession` 픽스처가 있다(위 "픽스처" 절).
- 시험이 결함 있는 동작을 정답으로 박았는지 의심한다. 결함을 고칠 때 먼저 그 기대값 시험이 있는지 찾는다.

> 관찰: 현재도 `tests/unit/test_pyramid_modals_action.py` 의 `dummy_request` 픽스처는 `request.db = MagicMock()` 으로 `request.db` 를 만든다. 지금 앱에는 `request.db` 가 없다(`grep -rn "request\.db\b" src` 결과 없음). 읽는 쪽이 없으므로 무해하지만, 낡은 mock 이 남아 있는 예다. 이 파일은 `request.dbsession = MagicMock()` 도 쓴다. [코드]
> 관찰: 위 mock 사용 시험 파일은 `grep -rln "MagicMock\|mock.patch\|monkeypatch.setattr" tests/unit` 로 75개가 나온다(2026-10-02). 모두 문제라는 뜻은 아니다. [코드]
