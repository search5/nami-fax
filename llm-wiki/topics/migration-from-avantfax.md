---
title: AvantFAX 3.x 에서 옮기기
type: topic
updated: 2026-10-03
sources: [src/namifax/models/types.py, src/namifax/common/passwords.py, src/namifax/common/settings.py, src/namifax/db/provider.py, src/namifax/db/bootstrap.py, src/namifax/db/adopt.py, src/namifax/db/textsearch.py, src/namifax/views/auth.py, src/namifax/views/admin_users.py, src/namifax/services/user_account.py, src/namifax/services/smtp_settings.py, src/namifax/common/secretbox.py, src/namifax/origin_guard.py, src/namifax/services/login_throttle.py, systemd/namifax.service, tools/migration_rehearsal/run.sh, src/namifax/alembic/versions/20261002_0026_password_hash_width.py, src/namifax/cli/import_archive.py, src/namifax/main.py, deploy/legacy-redirects/nginx.conf, deploy/legacy-redirects/apache.conf, tests/unit/test_legacy_redirects.py, tests/unit/test_legacy_database_compat.py, tests/unit/test_legacy_html_entities.py, tests/fixtures/legacy_sql/, tools/migration_rehearsal/, "[[migrating-from-avantfax3]]", "[[install-hylafax]]", "[[operations-checklist]]", "[[porting-gaps]]"]
verified: true
---

기존 AvantFAX 3.x(MySQL/MariaDB) DB 와 팩스 보관 폴더를 NamiFAX 로 이어 쓰는 방법과 규칙. 근거 문서는 [[migrating-from-avantfax3]] 이고 코드와 대조했다.
관련: [[database-and-migrations]] [[authentication-and-security]] [[operations-and-deployment]] [[i18n-and-ui]] [[known-gaps-and-decisions]] [[overview]].

## 0. 먼저 알아둘 것
- [코드] 원본 PHP 소스(`legacy/`)는 현재 저장소에 없다. 원본 설치 SQL 두 개(`create_tables.sql`, `db-update-334.sql`)만 시험 자료로 `tests/fixtures/legacy_sql/` 에 남아 있다. 원본 전체는 `git show 9408385:legacy/...` 또는 `git checkout 9408385 -- legacy` 로 복원한다. `9408385` 는 `git cat-file -t` 로 커밋임을 확인했고 그 트리에 `legacy/avantfax`, `legacy/create_tables.sql` 등이 있다. 삭제 커밋은 `083920e`(부모가 `9408385`, `git rev-parse 083920e^` 로 확인).
- [문서] AvantFAX 2.x 는 지원하지 않는다(3.x 이후 DB 만 대상. `docs/ko/install/migration.md` 에 있고 코드에서 버전을 검사하는 곳은 확인하지 못했다). 시험은 3.3.5 와 3.2.0 설치 스키마만 다룬다(`tests/conftest.py` `LEGACY_VERSIONS`) [코드].
- [문서] 실제 HylaFAX 와 수년치 대용량 보관소의 첫 기동 시간은 확인하지 못했다.

### 0.1 이전 연습 도구 `tools/migration_rehearsal/` 의 현재 상태
> 모순: [[install-hylafax]] 와 [[migrating-from-avantfax3]] 요약 페이지는 이 디렉터리가 "삭제됨(커밋 72a7324)"이라고 쓴다. 실제로는 **삭제되지 않았다**. `git ls-files tools` 가 `Dockerfile`, `check_text.py`, `make_faxes.py`, `parity.py`, `php-quiet.ini`, `populate_legacy.py`, `register_faxes.php`, `run.sh`, `two_way.py` 9개를 보여 주고 작업 트리에도 있다 [코드]. 72a7324 는 `golden_master`, `specs`, `prompts` 를 `dev/` 로 옮긴 커밋이고 `dev/` 는 01f2f64 에서 지워졌다. `tools/migration_rehearsal/` 은 마지막으로 `aa17252` 에서 바뀌었고 `083920e` 는 같은 `tools/` 아래 `tools/i18n_import_legacy.py` 만 지웠다(`git log -- tools/migration_rehearsal`, `git show --stat 083920e -- tools`).

- [코드] 그러나 **그대로는 실행되지 않는다.** `tools/migration_rehearsal/run.sh` 는 `$ROOT/legacy/avantfax/.` 를 복사하고 `$ROOT/legacy/create_tables.sql`, `db-update-330/334/335.sql` 을 읽는다. 지금은 `legacy/` 가 없다. 실행하려면 먼저 `git checkout 9408385 -- legacy` 로 원본을 되살려야 한다(이 안내는 `docs/ko/install/migration.md`, `docs/ko/install/operations-checklist.md` 에 있고 스크립트 주석에는 없다). 또 `db-update-330/335.sql` 은 `tests/fixtures/legacy_sql/` 에 없다(`db-update-334.sql` 만 있음). 이 파일들은 `legacy/` 에서 와야 한다. 실행하지는 않았다(Docker와 네트워크가 필요하고, 이 세션은 상태를 바꾸는 실행을 하지 않음).
- [코드] 이 도구는 PHP 5.6 + MDB2 + MariaDB 10.3(`--sql-mode=` 비엄격)에서 원본을 띄워 데이터를 채우고, NamiFAX 를 같은 DB·폴더에 붙여 `parity.py`(수신함·PDF 열람 비교), `two_way.py`(양방향 읽기·쓰기), `check_text.py`(HTML 엔티티 이름 점검)로 비교한다. 결과는 [[migrating-from-avantfax3]] 2장에 있으며, 이 세션에서 다시 돌려 검증하지 않았다 [문서].

## 1. 같은 DB·폴더를 이어 쓰는 규칙

| 항목 | 규칙 | 근거 |
|---|---|---|
| DB 주소 | 우선순위: 앱 설정 `sqlalchemy.url`(ini, `namifax serve --config`/`NAMIFAX_INI` 로 읽음) → `DATABASE_URL` → `AFDB_URL` → `NAMIFAX_DB_PATH`(SQLite 파일, 없으면 현재 폴더 `namifax.db`). 원본 DB 를 쓰려면 앞의 셋 중 하나로 지정 | [코드] `src/namifax/db/provider.py` |
| 보관 폴더 | `AVANTFAX_ARCHIVE`(받은, 기본 `$HYLASPOOL/archive`), `ARCHIVE_SENT`(보낸, 기본 `$HYLASPOOL/sent`), `AVANTFAX_INSTALLDIR`(저장된 상대 경로의 기준, 표지 이미지 폴더), `AVANTFAX_TMPDIR`(기본 `/tmp/avantfax/`) | [코드] `common/settings.py`(`archive_dir`, `sent_dir`), `services/archive_base.py`, `cli/cron.py`, `cli/notify.py` |
| 첫 기동 | `ensure_schema` 가 기존 원본 테이블을 "채택(adopt)"하고 Alembic 을 최신으로 올림. 새 테이블·인덱스 추가 | [코드] `db/bootstrap.py`(`ensure_schema` 가 `db/adopt.py` 의 `adopt_existing_tables` 와 `bootstrap.py` 의 `upgrade_to_head` 를 부름. 이미 최신 리비전이면 바로 돌아옴) |
| 기본 레코드 | 이미 `UserAccount` 가 있는 DB 에는 기본 카테고리·표지를 추가하지 않음(DB 가 "새것"일 때만) | [코드] `db/bootstrap.py` 의 `fresh` 판정 |
| 데모 계정 | MySQL/MariaDB/PostgreSQL 에서는 만들지 않음 | [코드] `db/bootstrap.py` |
| 되돌리기 | 이식본은 기존 행을 지우거나 바꾸지 않는다고 문서는 말함. 단 `UserAccount.password`·`UserPasswords.pwdhash` 열 폭 확장과 로그인 시 해시 변경은 있음 | [문서] + [코드] 마이그레이션 0026, `services/user_account.py` 로그인 시 재해시 |
| 백업 | 첫 기동 전에 `mysqldump` 와 보관 폴더 백업. 스키마 보정이 일어난다 | [문서] [[operations-checklist]] |

- [코드] `tests/unit/test_legacy_database_compat.py` 는 실제 MySQL·MariaDB 서버에서 3.3.5 와 3.2.0 설치 스키마로 호환을 시험하도록 작성돼 있다(`pytest.mark.serverdb`). 서버 URL 이 없으면 건너뛴다(`pyproject.toml` 의 마커 설명). 이 세션에서 실행하지 않았다.
- [코드] 새로 생기는 테이블: `SystemConfig`, `SystemSettings`, `NetworkPrinters`, `UserTOTP`, `UserWebAuthnCredentials` + `alembic_version` (`FaxOCR` 은 `0027` 이 지웠다). 문서가 말한 "6개"와 일치한다. 인덱스 12개, `AddressBook` 열 10개 추가는 개수를 직접 세지 않았다 [문서].
- [코드] 기존 보관 폴더를 DB 없이 들여오는 명령은 `namifax import-archive <폴더> <카테고리ID> [--user-id N] [--modem 장치] [--callid CallID1]` 이다(기본값 `--user-id 1`, `--modem ttyS0`, `--callid CallID1`; 실행 때 스키마를 먼저 맞춤. `src/namifax/cli/import_archive.py`). 같은 DB 를 이어 쓰면 이미 들어 있으므로 필요 없다. 사용자 목록 가져오기는 `namifax import-users`(탭 구분 텍스트), 블랙리스트는 `import-blacklist` 다 [코드: `main.py`].

> 모순(경미): [[migrating-from-avantfax3]] 는 비밀번호 열 원본이 `VARCHAR(32)` 라 0026 이 255자로 늘린다고 쓴다. 마이그레이션 코드는 `String(64)` 에서 `String(255)` 로 바꾼다(`alembic/versions/20261002_0026_password_hash_width.py`). 결론(Argon2id 가 들어갈 만큼 넓어짐)은 같다.

## 2. 비밀번호 해시 정책
- [코드] 새로 저장하는 비밀번호는 Argon2id 다(`common/passwords.py`: `NAMIFAX_ARGON2_TIME_COST` 등으로 비용 조정). 원본의 MD5 32자리 16진수는 계속 로그인에 인정된다(`verify_password` 가 32자리 hex 이면 MD5 비교).
- [코드] MD5 계정은 **그 계정이 로그인할 때** `needs_rehash` 로 판정해 Argon2id 로 바뀐다(`services/user_account.py` `login` 이 `update_info["password"]` 를 갱신, `passwords.py` 머리글). 로그인하지 않은 계정은 MD5 그대로다. `NAMIFAX_PASSWORD_HASH=md5` 이면 `needs_rehash` 가 MD5 에 대해 False 라 바뀌지 않는다.
- [코드] 원본 PHP 는 Argon2id 를 읽지 못한다. 병행 운영이나 되돌릴 가능성이 있으면 `NAMIFAX_PASSWORD_HASH=md5` 로 두면 새 비밀번호도 원본 형식이 된다(`hash_password`). 전환이 확정되면 설정을 지운다 [문서].
- [코드] 비밀번호 길이 한도는 원본과 같게 8~15자이며 `MIN_PASSWD_SIZE`, `MAX_PASSWD_SIZE` 로 바꾼다(`common/settings.py`).
- [코드] 비밀번호 만료(`pwdexpire` 지남 + `pwdcycle` 이 0 이 아님), 한 번도 로그인하지 않은 계정(`last_login` 이 NULL), `wasreset=1` 계정은 로그인 직후 `/pwdexpired` 에서 새 비밀번호를 정해야 로그인 쿠키가 나간다(`views/auth.py` `login_post_view`, `pwdexpired_post_view`; 판정은 `services/user_account.py` `login`). 관리자가 비밀번호 없이 만든 사용자는 임의 비밀번호가 생성되어 메일로 가고 `wasreset=1` 이 된다(`services/user_account.py` `create`, `views/admin_users.py`).
- [코드] 비밀번호 로그인은 실패가 쌓이면 잠긴다(`services/login_throttle.py`: 계정은 `NAMIFAX_LOGIN_MAX_FAILURES` 기본 5회 연속 실패로 잠기고 시간이 지나도 풀리지 않으며 관리자만 해제한다. 접속 주소는 10배 한도에 `NAMIFAX_LOGIN_LOCK_MINUTES` 기본 15분 동안만 잠근다. 카운터는 `SystemConfig` 에 저장). 원본에는 없던 동작이다(원본에 있었는지는 이 세션에서 확인하지 않았다). 이전 직후 다시 로그인하는 사용자가 한꺼번에 실수하면 걸릴 수 있다.

## 3. 달라 보이는 점
### 3.1 HTML 엔티티로 저장된 이름
- [코드] 원본은 폼 값을 `htmlentities(ENT_QUOTES, "UTF-8")` 를 거쳐 저장했다(`M&uuml;ller &amp; S&ouml;hne GmbH`). NamiFAX 는 **읽을 때** 완전한 엔티티(`&uuml;`, `&#039;`, `&#xFC;`)만 풀어서 보여 준다. `models/types.py` 의 `LegacyHtmlString`/`LegacyHtmlText`(`TypeDecorator`)와 `legacy_decode` 가 한다. DB 값은 건드리지 않는다.
- [코드] 검색은 입력어(`legacy_encode` 로 원본 저장 형태로 바꾼 것)와 입력 그대로의 두 LIKE 패턴을 모두 쓴다(`db/textsearch.py` `like_patterns`; 패턴은 소문자로 바꿈). 대소문자 구분 안 함은 문서 주장이다 [문서].
- [코드] NamiFAX 가 새로 쓰는 값은 순수 UTF-8 이다(디코드만 하고 인코드는 검색에만 쓴다. 저장 경로는 이 세션에서 끝까지 추적하지 않았다).
- [문서] 한계: 원본이 이중 인코딩해 이미 깨진 값은 복원하지 못한다. 사용자가 `&uuml;` 라는 글자를 그대로 입력해도 `ü` 로 보인다. 중복 이름 검사의 경계 경우는 시험하지 않았다. PHP 5.6 만 확인했다.

### 3.2 기존 팩스의 미리보기
- [문서] 원본의 `thumb.gif`·`prev*.gif` 는 쓰지 않고, 처음 볼 때 Ghostscript 로 `thumb.png`, `page*.png` 를 팩스 폴더 안에 만든다. 웹 서비스 사용자가 팩스 폴더에 쓸 수 있어야 하고 Ghostscript 가 필요하다. 미리 만들려면 `namifax create-thumbnails`(명령은 [코드] `main.py` 에 있음).

### 3.3 그 밖의 차이
- [문서] 화면은 Tailwind 로 새로 만들었고 원본 테마·`custom.css` 는 지원하지 않는다. 대화상자는 별도 창이 아니라 페이지다. 변경 요청(삭제·보관 등)은 POST + CSRF 토큰이며 원본의 `ajax/*.php?fid=…` GET 방식은 동작하지 않는다. 일부 화면에서 토큰 검사가 `check_csrf_token` 으로 쓰이는 것은 확인했다 [코드: `views/auth.py`, `views/modals.py`, `views/inbox.py`].
- [코드] 변경 요청(POST/PUT/PATCH/DELETE)은 `Origin`(없으면 `Referer`) 이 있는데 이 사이트(요청 호스트, `X-Forwarded-Host`, 설정 `csrf.trusted_origins`)가 아니면 403 으로 막는다. 헤더가 아예 없는 요청은 통과하고 SAML 콜백(`/auth/saml/acs`, `/auth/saml/sls`)은 제외다(`src/namifax/origin_guard.py`).
- [문서] 수신함·보관함 날짜는 고정 형식(원본의 `ARCHIVE_DATE_FORMAT` 없음). 메일·표지 날짜 형식은 파이썬 형식이다(기본 `%d.%m.%Y %H:%M`, `common/settings.py`). 원본의 MySQL 형식(`%i`=분)과 문법이 달라 값을 그대로 옮기면 안 된다 [코드: 기본값 확인].
- [문서] 번역: 한국어 외에는 일부만 번역(문서 수치 695개 중 292~333개). 수치는 이 세션에서 다시 세지 않았다.

## 4. `local_config.php` 설정 대응
원본의 `local_config.php` 는 읽지 않고 **환경 변수**로 지정한다([코드]: 설정 값은 `common/settings.py` 의 `flag/text/number` 가 `os.environ` 에서 읽음). systemd 에서는 `Environment=`/`EnvironmentFile=` 을 쓴다. 저장소의 `systemd/namifax.service` 는 `EnvironmentFile=-/etc/namifax.env`(앞의 `-` 로 파일이 없어도 기동)를 읽고, cron 과 HylaFAX 훅(`deploy/cron.d/namifax`, `deploy/hylafax/bin/*`)도 같은 파일을 읽는다(`tests/unit/test_env_file_wiring.py` 가 지킴). 웹 서버는 `namifax serve --config <ini>`(또는 `NAMIFAX_INI`)로 ini 의 `[app:main]` 설정(`session.secret`, `session.secure`, `csrf.trusted_origins`, `secret.key`, `sqlalchemy.url`)도 읽는다. [코드] `systemd/*.service`, `src/namifax/main.py` `serve_main`. 자세한 것은 [[operations-and-deployment]].

| 원본 | NamiFAX | 근거 |
|---|---|---|
| `AFDB_*`(엔진·호스트·사용자·비밀번호·DB 이름) | `DATABASE_URL`(`AFDB_URL` 도 인정, ini `sqlalchemy.url` 이 우선) | [코드] `db/provider.py` |
| `$INSTALLDIR`, `$ARCHIVE`, `$ARCHIVE_SENT`, `$TMPDIR` | `AVANTFAX_INSTALLDIR`, `AVANTFAX_ARCHIVE`, `ARCHIVE_SENT`, `AVANTFAX_TMPDIR` (시스템 기능 화면의 보관함 내려받기는 `AVANTFAX_ARCHIVE_SENT` 를 먼저 본다) | [코드] `common/settings.py`, `services/sysfunc.py` |
| `SMTP_*` | 읽지 않음(코드에 `SMTP_` 환경 변수 참조 없음). 관리자 화면의 SMTP 설정(DB 저장, 비밀번호는 `NAMIFAX_SECRET_KEY` 또는 ini `secret.key` 로 암호화) | [코드] `services/smtp_settings.py`, `common/secretbox.py` |
| `ENABLE_DID_ROUTING`, `ARCHIVEFAX2EMAIL`, `PAPERSIZE`, `DPI`, `PREV_TN`, `PREV_SP`, `HYLASPOOL`, `BINARYDIR`, `WWWUSER`, `FAXMAILUSER` 등 | 같은 이름의 환경 변수(위 열 개 이름이 `src/namifax/` 에서 모두 `grep` 으로 확인됨) | [코드] 전체 목록은 [[operations-and-deployment]] 2.2 |
| 테마·플러그인(`ADMINTHEME_DIR`, `PLUGINS_DIR`), 변환 도구 경로(`CONVERT`, `TIFFCP`, `GSR`), PHP 환경 | 필요 없음. 세 이름 모두 `src/namifax/` 에 참조가 없다 [코드]. 대체 도구(Ghostscript·Pillow)는 [문서] |

- 켜고 끄는 값은 `1`/`true`/`True`/`yes`. PHP 의 `true`/`false` 를 그대로 쓰면 안 된다 [코드: `settings.TRUE`].
- [문서] 설정 기본값이 원본과 다른 것이 있었으나(삭제된 `PORTING_GAPS` 의 E6, E7: `git show 61c3663:docs/PORTING_GAPS.md`) 현재 코드 기본값은 이 세션에서 변수별로 모두 대조하지 않았다. 중요한 변수는 이전 전에 기본값을 코드에서 확인한다.

## 5. 옛 주소 리다이렉트
- [코드] `deploy/legacy-redirects/nginx.conf`(30줄), `apache.conf`(29줄)(`wc -l`, 2026-10-02). nginx 파일 머리글은 `deploy/nginx/namifax.conf` 의 `server` 블록 안에서 `include` 하라고 적지만, 현재 `deploy/nginx/namifax.conf` 에는 그 `include` 가 없다(직접 추가해야 함), 옛 `*.php` 주소를 쿼리 문자열을 보존하며 301 로 새 주소에 보낸다(`/index.php` → `/login`, `/inbox.php` → `/inbox`, `/pdf.php?fid=N` → `/faxes/download/N?format=pdf`, `/refax.php?fid=N` → `/sendfax?refax=N`, `/admin/conf_modems*.php` → `/admin/modems` 등). 숫자가 아닌 `fid` 는 nginx 규칙이 404 를 돌려주고, Apache 는 규칙이 적용되지 않는다(`RewriteCond` 가 숫자만 받음).
- [코드] `tests/unit/test_legacy_redirects.py`(수집된 시험 41개, `uv run pytest --collect-only -q`, 2026-10-02)가 규칙의 도착 주소가 앱에 있는지와 Apache·nginx 파일이 같은 옛 페이지를 다루는지, 쿼리 파라미터 변경 두 가지를 지킨다. 규칙 자체는 실제 Apache·nginx 로 바꿀 때 시험한다고 파일 머리글이 말한다. "17개 주소 시험 완료"는 [문서] 이며 이 세션에서 재현하지 않았다.

## 6. 사용자에게 알릴 것
- [문서] 이전 직후 모든 사용자가 한 번 다시 로그인해야 한다(PHP 세션·로그인 쿠키는 이어지지 않음).
- [문서] 화면 모양과 대화상자가 바뀐다. 기능과 권한 규칙은 같다고 문서는 말한다.
- [문서] 비밀번호 찾기, 2단계 인증(TOTP), 패스키, SAML 은 새 기능이다.
- [문서] 병행 운영 중 NamiFAX 에서 로그인한 계정은 원본에서 로그인되지 않을 수 있다(`NAMIFAX_PASSWORD_HASH=md5` 가 아닐 때). 이 경우 비밀번호 찾기로 새로 받는다.
- [문서] SMTP 는 관리자 화면에서 다시 입력해야 한다.
- [문서] 큰 `FaxArchive` 의 첫 기동은 인덱스 생성으로 오래 걸릴 수 있으니 점검 시간대에 한다.

## 7. 확인하지 못한 것
- 실제 HylaFAX 와의 병행 운영, 3.0~3.2.x 업그레이드 이력이 있는 실제 DB, 대용량 보관소 시간(문서도 미확인이라고 명시).
- 예행연습 결과 자체(Docker 실행 필요). 파일 존재와 의존 경로만 확인했다.
