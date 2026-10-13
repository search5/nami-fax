---
title: 실행·배포·운영 점검
type: topic
updated: 2026-10-13
sources: [src/namifax/main.py, src/namifax/__init__.py, src/namifax/db/provider.py, src/namifax/db/bootstrap.py, src/namifax/origin_guard.py, src/namifax/common/passwords.py, src/namifax/common/secretbox.py, src/namifax/common/settings.py, src/namifax/services/scheduler.py, src/namifax/services/scheduler_config.py, src/namifax/services/sysfunc.py, src/namifax/views/sendfax.py, src/namifax/services/upload_check.py, src/namifax/cli/cron.py, src/namifax/cli/user.py, src/namifax/cli/phb.py, src/namifax/cli/encrypt_secrets.py, src/namifax/cli/faxrcvd.py, src/namifax/db/seed.py, src/namifax/services/login_throttle.py, src/namifax/services/cloud_storage.py, src/namifax/services/storage_lifecycle.py, src/namifax/services/printer.py, src/namifax/services/smtp_settings.py, src/namifax/services/mailer.py, src/namifax/services/hylafax_info.py, tests/unit/test_env_file_wiring.py, tests/unit/test_serve_main_db.py, tests/unit/test_session_secure_flag.py, tests/unit/test_login_throttle.py, tests/unit/test_business_logic_phase3.py, docs/ko/install/hylafax.md, docs/ko/install/operations-checklist.md, development.ini, production.ini, pyproject.toml, systemd/namifax.service, deploy/nginx/namifax.conf, deploy/apache/namifax.conf, deploy/cron.d/namifax, deploy/sudoers.d/namifax, deploy/postfix/setup-email2fax.md, deploy/hylafax/, "[[install-hylafax]]", "[[operations-checklist]]", "[[setup-email2fax]]"]
verified: true
---

실행 방법, 환경 변수, 배포 파일, 설치 후 점검 순서를 코드와 배포 파일을 직접 열어 대조해 정리한 페이지.
근거 문서는 [[install-hylafax]] 와 [[operations-checklist]]. 관련: [[overview]] [[scheduler-and-storage]] [[hylafax-integration]] [[authentication-and-security]] [[migration-from-avantfax]] [[known-gaps-and-decisions]].
이 저장소에서는 실제 HylaFAX 서버에 붙여 시험하지 못했다(아래 "확인하지 못한 것").

## 1. 실행 방법

### 1.1 `namifax serve` (systemd 단위가 쓰는 방식)
- [코드] `pyproject.toml` 의 `[project.scripts]` 가 `namifax`(`namifax.main:main`)와 `namifax-server`, `namifax-createuser`, `namifax-dynconf`, `namifax-faxrcvd`, `namifax-notify`, `namifax-faxcover`, `namifax-cron`, `namifax-phb` 를 만든다.
- [코드] `namifax serve`(`src/namifax/main.py` 의 `serve_main`)는 순서대로 (0) 옵션 `--config`/`-c <ini>`(기본값은 환경 변수 `NAMIFAX_INI`, 없으면 ini 를 읽지 않음)가 있으면 그 파일의 `[app:main]` 설정을 `pyramid.paster.get_appsettings` 로 읽는다(`_load_ini_settings`; 파일이 없거나 읽기 실패면 stderr 에 "Cannot read the configuration file" 를 내고 종료 코드 1), (1) `resolve_database_url(settings, os.environ)` 로 DB 주소를 정해 `ensure_schema` 실행(ini 의 `sqlalchemy.url` 이 환경 변수보다 먼저), (2) `NAMIFAX_ENABLE_SCHEDULER` 가 `1`/`true`/`True`(기본 `1`)면 프로세스 안에서 APScheduler 시작, (3) `create_app(**settings)` 로 Pyramid 앱 생성(실패하면 메시지를 stderr 에 내고 종료 코드 1, 다른 앱으로 대체하지 않음), (4) 표준 라이브러리 `wsgiref` 의 `ThreadingWSGIServer`(스레드 서버)로 `--host`/`--port`(기본 환경 변수 `NAMIFAX_HOST` 0.0.0.0, `NAMIFAX_PORT` 8000)에 바인딩한다. 시험: `tests/unit/test_serve_main_db.py`(옵션 없음 → `create_app()` 에 설정 없음, `--config` 와 `NAMIFAX_INI` → ini 값 전달, ini 의 `sqlalchemy.url` 이 스키마 준비에 쓰임, 없는 ini 는 종료 코드 1; 읽기만 했고 실행하지 않았다).
- [코드, 측정 2026-10-03] **같은 DB 에 웹 서비스를 둘 이상 띄울 수 없다.** 임시 SQLite DB 에 `namifax serve` 두 개(포트 18801, 18802)를 시험했다. (1) 마이그레이션이 필요한 DB 에서 두 서비스를 거의 동시에 시작하면 두 번째가 시작 중에 죽는다: `RuntimeError: Database initialisation failed: (sqlite3.IntegrityError) UNIQUE constraint failed: alembic_version.version_num`(`db/bootstrap.py::ensure_schema` 가 둘 다 같은 마이그레이션을 적용하다가 `UPDATE alembic_version SET version_num='0026'` 에서 충돌). 이미 최신으로 마이그레이션된 DB 에서는 둘 다 시작했다. (2) 시작한 뒤에도 A 에서 로그인해 얻은 쿠키로 B 의 `/inbox` 를 열면 A 는 200, B 는 401 이다. 로그인 상태가 프로세스 메모리(`sessions.py`)에 있기 때문이다([[known-gaps-and-decisions]] §5). 실제 PostgreSQL·MySQL·MariaDB 에서 같은 시작 충돌이 나는지는 시험하지 않았다.
- [코드] 이 서버는 `waitress` 가 아니라 `wsgiref` 다. 프로세스는 하나이고 워커 개수 설정이 없다.
- [코드, 측정 2026-10-03] 이 서버는 `ThreadingMixIn` 을 섞어 연결마다 스레드를 만든다(`main.py` 의 `ThreadingWSGIServer`). 같은 앱을 `wsgiref` 와 `waitress`(스레드 8)로 띄워 `GET /login` 400번을 동시 16개로 보냈다(한 대의 PC에서 시험 클라이언트가 같은 프로세스로 돌아 절대값은 의미가 작고 상대 비교용이다). `wsgiref`: 186 req/s, 중앙값 42ms, 99백분위 1010ms. `waitress`: 345 req/s, 중앙값 43ms, 99백분위 105ms. 아무것도 보내지 않는 연결 300개를 열어 두면 `wsgiref` 는 스레드가 302개가 되고 일반 요청은 4ms 로 응답했으며, `waitress` 는 기본 연결 한도 100 때문에 그 상태에서 새 요청이 3초 안에 응답하지 못했다. 유휴 연결 제한시간은 `wsgiref` 요청 처리기가 `None`(제한 없음), `waitress` 는 `channel_timeout` 120초가 기본이다. 35초 관찰에서는 두 서버 모두 유휴 연결을 닫지 않았다. 실제 부하 아래의 운영 영향은 측정하지 않았다.

> 모순: 해결됨(커밋 `91dbc4a`). 이전에는 `namifax serve` 가 `create_app()` 을 설정 없이 불러 ini 의 `session.secure`, `session.secret`, `secret.key`, `csrf.trusted_origins`, `demo.data`, `sqlalchemy.url` 이 읽히지 않았다. 지금은 `--config`/`NAMIFAX_INI` 로 ini 를 주면 읽힌다. 단 **옵션을 주지 않으면 여전히 ini 를 읽지 않으므로** 저장소의 `systemd/namifax.service` 기본 `ExecStart=.../namifax serve` 는 ini 없이 뜬다. HTTPS 에서 ini 의 `session.secure = true` 를 쓰려면 단위 파일의 `ExecStart` 에 `--config /etc/namifax/production.ini` 를 붙이거나 `/etc/namifax.env` 에 `NAMIFAX_INI=...` 를 적어야 한다(`docs/ko/install/hylafax.md` 가 같은 안내). ini 없이 쓰려면 환경 변수 `NAMIFAX_SESSION_SECURE`(2.1)가 있다.

### 1.2 `pserve` + ini 파일
- [코드] `development.ini`, `production.ini` 는 `use = egg:namifax`(`pyproject.toml` 의 `paste.app_factory` 진입점)와 `waitress` 서버를 쓴다. `development.ini` 는 `0.0.0.0:6543`, `pyramid.reload_templates = true`, 루트 로그 INFO·`namifax` 로거 DEBUG. `production.ini` 는 `*:6543`, `reload_templates = false`, 로그 WARN.
- [코드] 두 ini 모두 `session.secret`, `session.secure`, `csrf.trusted_origins`, `secret.key`, `sqlalchemy.url` 줄이 없거나(`sqlalchemy.url` 은 주석 처리) 비어 있다. 이 값들을 쓰려면 `[app:main]` 에 직접 추가해야 한다.
- [코드] `namifax serve --config production.ini` 도 같은 `[app:main]` 설정을 읽지만 서버는 `[server:main]` 의 waitress 가 아니라 위 1.1 의 `wsgiref` 이다(`[server:main]` 은 무시됨). 이 경로로 `pserve production.ini` 를 실행하면 `ensure_schema` 는 `create_app` 안에서 돈다. 내장 스케줄러는 시작하지 않는다(스케줄러 시작은 `serve_main` 에만 있음). 별도 스케줄러 명령은 제거했으므로(2026-10-03) 이 경로에서는 정기 작업이 관리자 화면의 "지금 실행"이나 OS cron(`namifax cron`)으로만 돈다. 스케줄러를 쓰려면 `namifax serve` 로 띄운다.
- [코드] `pserve` 가 `waitress`, `plaster_pastedeploy` 를 쓰는 점은 `pyproject.toml` 의 의존성 목록으로 확인했다. 저장소의 systemd 단위와 nginx/apache 파일은 이 경로를 쓰지 않는다(8000 포트, `namifax serve`).

### 1.3 스케줄러
- [코드] 스케줄러는 웹 프로세스 안에서만 돈다. `namifax.service` 가 `NAMIFAX_ENABLE_SCHEDULER=1` 로 `namifax serve` 안에서 APScheduler 를 시작한다. 별도 `namifax scheduler` 명령, `systemd/namifax-scheduler.service`, 스크립트 `namifax-scheduler` 는 2026-10-03 에 제거했다(같은 DB 의 스케줄러가 둘이면 같은 작업을 같은 순간 시작하는 경쟁이 있어서). 작업 단위 중복 방지는 두 겹이다. (1) 프로세스 안 잠금(`scheduler.claim`). (2) 커밋 `ad5dc09` 이후, 실행 직전에 DB(`SystemConfig` 의 `sched_running_<작업>`)의 실행 표식이 6시간(`STALE_RUNNING_SECONDS`) 미만이면 다른 프로세스가 돌리는 중으로 보고 요약 "already running" 으로 건너뛴다(`scheduler._run_claimed`, `scheduler_config.running_marker`). 표식 확인과 기록 사이는 원자적이지 않아서(확인 후 `mark_running`) 같은 DB 를 쓰는 스케줄러 프로세스가 둘이고 같은 순간 시작하면 막지 못한다(웹 서비스를 하나만 운영하면 생기지 않는다). [코드, 측정 2026-10-03] `_run_claimed` 의 첫 단계(`running_marker` 확인, `mark_running`, 커밋)를 별도 세션 2개로 장벽 동기화해 40번 반복했더니 SQLite, PostgreSQL 16, MySQL 8.4, MariaDB 10.11 모두 39/40번에서 둘 다 통과했다(오류 0). 그래서 한 DB 에는 웹 서비스를 하나만 두는 것이 안전하다. [코드: `src/namifax/services/scheduler.py`, `scheduler_config.py`]
- [코드] 스케줄러 작업은 4개다(`scheduler_config.JOBS`): `tmp`(임시 폴더 정리, 기본 켬 00:00 1일), `inbox`(받은 팩스함 → 보관함 이동, **기본 꺼짐** 01:00 30일), `lifecycle`(Admin > Storage 에 저장한 보존 정책, 정책이 저장돼 있을 때만 실제로 지움), `phonebook`(주소록을 HylaFAX 로 내보내기, 60분; 요약에 `cli/phb.py::export_phonebook_count` 가 센 실제 항목 수를 적는다).

> 모순: 해결됨(커밋 `91dbc4a`). `docs/ko/install/hylafax.md` 와 `docs/ko/install/operations-checklist.md` 는 이제 내장 스케줄러가 `tmp`, `inbox`(기본 꺼짐), `lifecycle`, `phonebook` 4종을 돌린다고 적는다(2026-10-02 확인). 위키 `sources/` 요약은 옛 서술("임시 파일 정리만")이 남아 있을 수 있다. 코드 기준으로 보관함 안의 오래된 팩스를 날짜로 **삭제**하는 `namifax cron -d` 에 해당하는 스케줄러 작업은 없고(`lifecycle` 의 저장 정책이 있을 때만 삭제), 이 점은 `OPERATIONS_CHECKLIST.md` 도 같게 적는다. `namifax cron` 옵션은 `-t`(필수) `-i` `-d` `-p` `-s` [코드: `src/namifax/cli/cron.py` `getopt "i:t:d:p:s"`].

## 2. 환경 변수

### 2.1 `NAMIFAX_*` 전체 (코드·배포 파일 grep 결과, 2026-10-02)
방법: `src/`, `deploy/`, `systemd/`, `*.ini`, `pyproject.toml` 에서 `grep -rhoE "NAMIFAX_[A-Z0-9_]+"` 로 이름을 모은 25개를 하나씩 읽었다(이름을 문자열로 조립하는 코드는 `src/` 검색에서 보이지 않았다). 번역 파일(`locale/`)과 Alembic 설명문에 나오는 이름은 변수의 사용처가 아니다.

| 변수 | 기본값 | 용도 | 근거 |
|---|---|---|---|
| `NAMIFAX_HOST` / `NAMIFAX_PORT` | `0.0.0.0` / `8000` | `namifax serve` 바인딩(`--host`/`--port` 옵션이 이김) | `src/namifax/main.py` |
| `NAMIFAX_INI` | 없음 | `namifax serve` 가 읽을 ini 경로(`--config` 의 기본값). 없으면 ini 를 읽지 않음 | `src/namifax/main.py` |
| `NAMIFAX_ENABLE_SCHEDULER` | `1` | 웹 프로세스 안 스케줄러(`1`/`true`/`True`) | `src/namifax/main.py` |
| `NAMIFAX_SESSION_SECRET` | 없음(프로세스마다 임의 키 + 경고 로그) | 흐름 상태 쿠키(`namifax_flow`: 2FA 단계, 패스키 챌린지)의 서명 키. ini 의 `session.secret` 이 있으면 그것이 먼저 | `src/namifax/__init__.py` |
| `NAMIFAX_SESSION_SECURE` | `false` | 그 쿠키의 `Secure` 표시(`1`/`true`/`yes`). ini 에 `session.secure` 가 있으면 ini 가 이김(커밋 `403b549`) | `src/namifax/__init__.py`, `tests/unit/test_session_secure_flag.py` |
| `NAMIFAX_LOGIN_MAX_FAILURES` | `5` | 비밀번호 로그인 연속 실패 허용 횟수(양의 정수만 인정, 아니면 기본값). 넘으면 계정이 잠기고 관리자가 풀 때까지 유지된다. 같은 클라이언트 주소는 10배까지(기본 50회)이고 주소 잠금만 시간이 지나면 풀린다 | `src/namifax/services/login_throttle.py` |
| `NAMIFAX_LOGIN_LOCK_MINUTES` | `15` | 위 횟수에 이르면 잠그는 시간(분). 실패를 세는 구간도 같은 길이 | `src/namifax/services/login_throttle.py` |
| `NAMIFAX_SECRET_KEY` | 없음 | SMTP 비밀번호·클라우드 키·2FA 시드 암호화. Fernet 키 또는 16자 이상 문장. 쉼표로 여러 개면 첫 키로 암호화·모두로 복호화(회전). 환경 변수가 ini `secret.key` 보다 먼저 | `src/namifax/common/secretbox.py` |
| `NAMIFAX_PASSWORD_HASH` | `argon2` | `md5`(대소문자 무시)면 새 비밀번호를 원본 형식으로 저장 | `src/namifax/common/passwords.py` |
| `NAMIFAX_ARGON2_TIME_COST` / `_MEMORY_COST` / `_PARALLELISM` | 라이브러리 기본 | Argon2id 비용 조정(양의 정수만 인정) | `src/namifax/common/passwords.py` |
| `NAMIFAX_DB_PATH` | 현재 폴더의 `namifax.db` | SQLite 파일(ini `sqlalchemy.url`, `DATABASE_URL`, `AFDB_URL` 이 모두 없을 때) | `src/namifax/db/provider.py` |
| `NAMIFAX_DEMO_DATA` | 꺼짐 | 데모 데이터(`1`/`true`/`yes`/`on`). SQLite 에서만, 사용자가 없는 새 DB 일 때. 다른 DB 에서는 경고 후 무시 | `src/namifax/db/bootstrap.py`, `db/seed.py` |
| `NAMIFAX_NEW_USER_PASSWORD` | 없음 | `namifax createuser` 의 비밀번호(`-p` 가 없을 때) | `src/namifax/cli/user.py` |
| `NAMIFAX_DEFAULT_LANGUAGE` | `en` | `import-users` 로 만든 계정의 언어 | `src/namifax/cli/import_users.py` |
| `NAMIFAX_ARCHIVE_DIR` | `/var/spool/hylafax/archive` | 로컬 저장소 제공자와 보존 정책(`storage_lifecycle`)이 보는 보관 폴더. 만들 수 없고 이 변수도 없으면 `~/.namifax/archive` 로 대체(로컬 제공자) | `src/namifax/services/cloud_storage.py`, `storage_lifecycle.py` |
| `NAMIFAX_TMPDIR` | 시스템 임시 폴더 | 가상 프린터 작업 파일의 폴더(`namifax_spool/`, `namifax_drafts/`) | `src/namifax/services/printer.py` |
| `NAMIFAX_MAX_UPLOAD_BYTES` | 10 MiB | 팩스 업로드 크기 한도(양의 정수만 인정) | `src/namifax/services/upload_check.py` |
| `NAMIFAX_FAXCOVER` | `python -m namifax.cli.faxcover` | 표지 생성 실행 파일 | `src/namifax/views/sendfax.py` |
| `NAMIFAX_QUEUE_SIMULATION` | 미지정(꺼짐) | `1`/`true`/`yes` 일 때만 `sendfax` 가 없을 때 전송 성공을 흉내냄. 그 밖은 모두 오류(아래 참고) | `src/namifax/views/sendfax.py`, `tests/unit/test_business_logic_phase3.py` |
| `NAMIFAX_REBOOT_CMD` / `NAMIFAX_SHUTDOWN_CMD` | `sudo /sbin/reboot` / `sudo /sbin/halt` | 관리자 > 시스템 기능의 재부팅·종료 명령(`shlex.split`, 쉘 없음) | `src/namifax/services/sysfunc.py` |
| `NAMIFAX_HOME` | `/opt/namifax` | 훅 스크립트가 가상환경 위치를 찾을 때만 씀 | `deploy/hylafax/bin/*` |

- [코드] `NAMIFAX_QUEUE_SIMULATION` 은 **커밋 `c59af5e` 에서 의미가 바뀌었다**. 이전에는 미지정이어도 pytest 실행 중이거나 `/var/spool/hylafax` 가 없으면 가짜 성공(무작위 작업 번호)을 돌려줬다. 지금은 `sendfax` 실행 파일이 없을 때 이 변수가 `1`/`true`/`yes` 가 아니면(미지정·`0`·빈 값·`false`·`no`) `success: False` 와 "HylaFAX (the sendfax program) is not installed or not reachable" 오류를 돌려주고 가짜 작업 번호는 만들지 않는다(`views/sendfax.py` 의 `_simulation_wanted`, `dispatch_sendfax`). 시험 `test_dispatch_sendfax_never_fakes_success_unless_simulation_is_explicit` 가 이를 파라미터화해 확인한다(읽기만 함). 개발 장비에서 모의 성공이 필요하면 `NAMIFAX_QUEUE_SIMULATION=1` 을 직접 줘야 한다. 운영에서는 이 변수를 쓰지 말고 `sendfax` 가 `PATH`(또는 `BINARYDIR`/`SENDFAX`)에 있는지 점검 순서(4절)에서 확인한다.
- [코드] 새 `NAMIFAX_*` 이름은 이번에 `NAMIFAX_INI`, `NAMIFAX_SESSION_SECURE`, `NAMIFAX_LOGIN_MAX_FAILURES`, `NAMIFAX_LOGIN_LOCK_MINUTES` 4개가 더해졌다(이전 판 표는 21개 이름이었다).

### 2.2 원본 이름을 그대로 쓰는 설정(NAMIFAX_ 접두사 없음)
- [코드] `DATABASE_URL`(없으면 `AFDB_URL`, 그다음 `NAMIFAX_DB_PATH`, 그것도 없으면 현재 폴더의 `namifax.db`) 순서로 DB 를 정한다(`src/namifax/db/provider.py::resolve_database_url`). ini 의 `sqlalchemy.url` 이 있으면 그것이 먼저다(`namifax serve` 는 `--config`/`NAMIFAX_INI` 를 줄 때만 ini 를 본다).
- [코드] `src/namifax/common/settings.py` 의 `flag/text/number` 와 `os.environ` 로 읽는 원본 이름은 다음과 같다: `AVANTFAX_INSTALLDIR`, `AVANTFAX_ARCHIVE`, `AVANTFAX_ARCHIVE_SENT`(시스템 기능의 아카이브 묶음에서만 `ARCHIVE_SENT` 보다 먼저 봄), `ARCHIVE_SENT`, `AVANTFAX_TMPDIR`, `AVANTFAX_AUDIO_DIR`, `AVANTFAX_SERVERNAME`, `AVANTFAX_RESERVED_FAX_NUM`, `HYLASPOOL`, `HYLAFAX_PREFIX`, `BINARYDIR`, `HYLAFAX_USER_SYNC`, `FAXMAILUSER`, `WWWUSER`, `DEFAULT_TSI_ID`, `ENABLE_DID_ROUTING`, `ENABLE_BARDECODE_SUPPORT`, `ENABLE_OCR_SUPPORT`, `ENABLE_DL_TIFF`, `ENABLE_FAX_ANNOTATION`, `ARCHIVEFAX2EMAIL`, `FAXRCVD_INCLUDE_PDF`, `FAXRCVD_INCLUDE_THUMBNAIL`, `FAXRCVD_PRINT_PDF`, `PRINTFAXRCVD`, `PRINTERNAME`, `PRINTCMD`, `PDFPRINTCMD`, `NOTIFY_INCLUDE_PDF`, `NOTIFY_ON_SUCCESS`, `COVERPAGE_FILE`, `COVERPAGE_MATCH`, `FROM_COMPANY`, `FROM_LOCATION`, `FROM_FAXNUMBER`, `FROM_VOICENUMBER`, `PAPERSIZE`, `DPI`, `PREV_TN`, `PREV_SP`, `PHONEBOOK`, `WHITEPAGES`, `ALTERNATE_AUTH_ENABLE`, `ALTERNATE_AUTH_CLASS`, `ALTERNATE_AUTH_FALLBACK`, `WEBSERVER_AUTH`, `PWAUTHPATH`, `MIN_PASSWD_SIZE`, `MAX_PASSWD_SIZE`, `MAX_USERNAME_SIZE`, `MAX_EMAIL_SIZE`, `DEFAULT_FAXES_PER_PAGE_INBOX`, `DEFAULT_FAXES_PER_PAGE_ARCHIVE`, `INBOX_LIST_MODEM`, `RESTRICTED_USER_MODE`, `SHOW_ALL_CONTACTS`, `SHOWSERVER_DETAILS`, `FOCUS_ON_NEW_FAX`, `FOCUS_ON_NEW_FAX_POPUP`, `SENDFAX_USE_COVERPAGE`, `SENDFAX_REQUEUE_EMAIL`, 날짜·메일 형식(`EMAIL_DATE_FORMAT`, `FAXCOVER_DATE_FORMAT`, `EMAIL_ENCODING_CHARSET`), OCR·바코드(`OCR_BINARY`, `OCR_COMMAND`, `OCR_LANGUAGE`, `BARDECODE_BINARY`, `BARDECODE_COMMAND`), 그 밖(`ADMIN_EMAIL`, `AUTOCONFDID`, `ANN_GRAVITY`, `CPAGE_LINELEN`, `NUM_PAGES_FOLLOW`, `USE_HTML_COVERPAGE`, `TIFF_TO_G4`, `PRINTFAX2PS`, `SUDO`). 켜고 끄는 값은 `1`/`true`/`True`/`yes`(`settings.TRUE`). 일부는 `1/true/True` 만 인정한다(`fax_access._did_routing_enabled`). 변수별 기본값은 `common/settings.py` 와 사용하는 파일에 흩어져 있어 이 페이지에서 일일이 옮기지 않았다. 2026-10-02 에 이 목록의 이름 약 90개가 모두 `src/` 의 `.py` 에 철자 그대로 나오는지 `grep -w` 로 확인했고, `settings.flag/text/number`/`os.environ.get` 첫 인자 약 97개가 모두 이 페이지에 있는지도 대조했다(빠졌던 `ARCHIVE_SENT` 만 추가). `NAMIFAX_ARCHIVE_DIR`(2.1)와 `AVANTFAX_ARCHIVE`/`HYLASPOOL` 은 서로 다른 변수이므로, 수신 보관 폴더(`faxrcvd` 는 `AVANTFAX_ARCHIVE`)를 바꾸면 보존 정책의 대상 폴더(`NAMIFAX_ARCHIVE_DIR`)도 같이 맞춰야 한다 [코드: `cli/faxrcvd.py`, `services/storage_lifecycle.py`].
- [코드] `REMOTE_USER` 는 웹 서버가 넘기는 값이고 설정이 아니다(`WEBSERVER_AUTH` 와 함께 쓰는 로그인).

### 2.3 ini 로 주는 설정(`--config`/`NAMIFAX_INI` 또는 `pserve`)
- [코드] ini 의 `[app:main]` 키: `session.secret`, `session.secure`, `csrf.trusted_origins`(쉼표로 구분한 `https://호스트`), `secret.key`, `demo.data`, `sqlalchemy.url`. 환경 변수 대응: `session.secret` ↔ `NAMIFAX_SESSION_SECRET`, `session.secure` ↔ `NAMIFAX_SESSION_SECURE`, `secret.key` ↔ `NAMIFAX_SECRET_KEY`, `demo.data` ↔ `NAMIFAX_DEMO_DATA`, `sqlalchemy.url` ↔ `DATABASE_URL`. 우선순위는 키마다 다르다: `session.secret`/`session.secure`/`sqlalchemy.url` 은 ini 가 먼저, `NAMIFAX_SECRET_KEY`/`NAMIFAX_DEMO_DATA` 는 환경 변수가 먼저. **`csrf.trusted_origins` 만 환경 변수가 없다**(`origin_guard.py` 는 `settings` 만 읽음). `namifax serve` 는 옵션 없이는 ini 를 읽지 않는다(1.1).
- [코드] 프록시 뒤에서는 `X-Forwarded-Host` 를 읽어 `Origin`/`Referer` 와 비교하므로(`origin_guard.py`) `csrf.trusted_origins` 없이도 nginx 설정의 `proxy_set_header X-Forwarded-Host $host` 만으로 동작한다. 단, SAML 콜백(`/auth/saml/acs`, `/auth/saml/sls`)은 검사에서 제외된다.

## 3. 배포 파일(저장소 `deploy/`, `systemd/`)

| 파일 | 내용 | 비고 |
|---|---|---|
| `systemd/namifax.service` | `User=uucp`, `/opt/namifax`, `namifax serve`, `NAMIFAX_HOST=0.0.0.0`, `NAMIFAX_PORT=8000`, `NAMIFAX_ENABLE_SCHEDULER=1`, `EnvironmentFile=-/etc/namifax.env`(단위 파일 주석: 파일 값이 앞의 `Environment=` 줄을 덮어씀), `ProtectSystem=full`, `ProtectHome=true`, `NoNewPrivileges=true`, `LimitNOFILE=65536` | 최상위 `systemd/` 에 있다(`deploy/systemd/` 아님; 문서는 정정됨) |
| `deploy/nginx/namifax.conf` | 443 SSL, `client_max_body_size 25m`, `127.0.0.1:8000` 프록시, `Host`/`X-Forwarded-Host`/`-Proto`/`-For` 전달, `/forgot` 속도 제한 예시는 주석 | 포트가 systemd 단위와 일치 |
| `deploy/apache/namifax.conf` | 443 SSL, `LimitRequestBody 26214400`, `ProxyPass` 8000, `X-Forwarded-Proto https` | `X-Forwarded-Host` 줄은 없다. `ProxyPreserveHost On` 으로 Host 가 그대로 가므로 출처 검사는 통과한다 [코드]. 웹 서버 로그인(`WEBSERVER_AUTH`)은 프록시 방식에서 `REMOTE_USER` 가 안 넘어간다고 파일 주석이 명시 |
| `deploy/legacy-redirects/{nginx,apache}.conf` | 옛 주소 301 | [[migration-from-avantfax]] 참고 |
| `deploy/cron.d/namifax` | `0 0 * * * uucp sh -c 'set -a; [ -r /etc/namifax.env ] && . /etc/namifax.env; set +a; exec /opt/namifax/.venv/bin/namifax cron -t 2'` 만 켜짐. `-i 30 -d 365`, `-p 90`, `-s` 줄은 주석(같은 `sh -c` 꼴) | cron 에는 `EnvironmentFile` 이 없어 줄마다 환경 파일을 읽는다 |
| `deploy/sudoers.d/namifax` | `uucp` 가 `/sbin/reboot`, `/sbin/halt`, `/usr/sbin/faxdeluser *`, `/usr/sbin/faxadduser -u * -p * *` 만 비밀번호 없이 | 사용자 이름은 서비스 사용자에 맞춰 바꿀 것 |
| `deploy/hylafax/bin/{faxrcvd,dynconf,notify,faxcover}` | `set -a; [ -r /etc/namifax.env ] && . /etc/namifax.env; set +a` 뒤에 `${NAMIFAX_HOME:-/opt/namifax}/.venv/bin/namifax-*` 를 `exec` | `set -a` 로 변수가 자식 프로세스에 전달됨 |
| `deploy/hylafax/config.namifax` | `FaxRcvdCmd: bin/faxrcvd`, `DynamicConfig: bin/dynconf`, `UseJobTSI: true` (모뎀별 설정에 추가) | |
| `deploy/hylafax/etc-faxq.snippet` | `NotifyCmd: bin/notify`, `CoverCmd: bin/faxcover` | |
| `deploy/hylafax/hfaxd.conf.snippet` | 파일 안 주석은 `$SPOOL/etc/config` 에 넣으라고 안내. `JobFmt: "%-3j %3i %1a %15o %40M %-12.12e %5P %5D %7z %.25s"` (큐 목록 열 10개) | 파일 이름(`hfaxd.conf`)과 주석의 설치 위치가 다름. 어느 쪽이 맞는지는 실제 HylaFAX 로 확인하지 못함 |
| `deploy/postfix/setup-email2fax.md` | 메일 → `faxmail` 파이프 설정 단계 | 시스템 파일을 직접 고치지 않는 설명서. 상세는 [[setup-email2fax]] |

- [코드] 위 단위·설정 파일의 내용은 직접 열어 확인했다. 실제 서버에 적용해 시험한 적은 없다.

### 3.1 환경 파일 배선과 문서 차이(코드를 따름)
> 모순: 해결됨(커밋 `91dbc4a`). 이전에는 `systemd/*.service` 에 `EnvironmentFile=` 이 없었고 cron 줄도 환경 파일을 읽지 않아 `DATABASE_URL`, `NAMIFAX_SESSION_SECRET`, `NAMIFAX_SECRET_KEY` 가 웹 서비스·스케줄러·cron 에 전달되지 않았다(그러면 `DATABASE_URL` 이 없어 `namifax.db` SQLite 로 조용히 떨어짐, `db/provider.py`). 지금은 세 곳 모두 같은 `/etc/namifax.env` 를 읽는다: systemd 두 단위 `EnvironmentFile=-/etc/namifax.env`, cron 줄 `sh -c 'set -a; ... . /etc/namifax.env; set +a; exec ...'`, 훅 4개 `set -a; ... . /etc/namifax.env; set +a`. `tests/unit/test_env_file_wiring.py` 가 서비스 파일의 `EnvironmentFile=-/etc/namifax.env` 줄, cron 항목 4개의 읽기 순서(`set -a` → `.` → `set +a` → `namifax cron`), 훅과 cron 이 가짜 설치에서 `DATABASE_URL`/`NAMIFAX_SECRET_KEY` 를 프로그램에 전달하는지를 본다(읽기만 했고 실행은 하지 않았다).

> 모순: 해결됨(커밋 `91dbc4a`). 이전 우려(`export` 없는 `KEY=value` 를 `.` 로 읽으면 자식에 전달되지 않는다)는 훅 스크립트와 cron 줄에 `set -a` 가 들어가 해소됐다(`deploy/hylafax/bin/*`, `deploy/cron.d/namifax`). 남은 주의점이었던 쉘·systemd 해석 차이는 이제 문서화되고 시험됐다(커밋 `26fcf82`). 원래 문제 [코드: 이 세션에서 `sh` 로 직접 시험]: 환경 파일을 **쉘이 읽는** 훅·cron 과 systemd 는 해석이 다르다. systemd 는 `KEY=value` 를 값 그대로 쓰지만 쉘은 `&`(뒤를 별도 명령으로 실행), 공백, `;`, `$`, `#` 를 문법으로 처리한다. 예를 들어 `DATABASE_URL=mysql+pymysql://u:pw@h/db?charset=utf8mb4&x=1` 을 `sh -c 'set -a; . 파일; set +a; echo "[$DATABASE_URL]"'` 로 읽으면 `[]` 가 나왔다. 값에 이런 문자가 있으면 같은 파일이 서비스에서는 되고 훅·cron 에서는 깨진다. 해결책: `docs/ko/install/hylafax.md` 는 이제 `export` 와 줄 끝 `#` 주석만 금지하고, 값에 `&` `;` `(` `)` `<` `>` `|` 공백이 있으면 **큰따옴표로 감싸라**고 안내한다(큰따옴표는 systemd 와 셸이 똑같이 벗기며, 안에는 `$`·백슬래시·역따옴표·`"` 를 넣지 않는다). 시험 `tests/unit/test_env_file_wiring.py::test_a_quoted_value_with_special_characters_survives_the_shell_and_the_cron_line`(훅 스크립트를 `sh` 로 돌려 `&x=1 y;z` 가 든 따옴표 값이 살아남는지 봄)와 `test_install_guide_sample_uses_the_plain_key_value_format`(예제가 `KEY=값` 또는 `KEY="값"` 형식인지)가 있다(실행하지 않음). `OPERATIONS_CHECKLIST.md` 쪽 서술은 이번에 다시 읽지 않았다. 실제 HylaFAX 훅 실행 환경에서는 확인하지 못했다.

- [코드] 사용자 동기화(`HYLAFAX_USER_SYNC=1`)와 시스템 기능의 재부팅·종료는 `sudo` 를 쓴다. `systemd/namifax.service` 의 `NoNewPrivileges=true` 는 문서가 사용자 동기화를 켤 때 `false` 로 바꾸라고만 안내한다([[install-hylafax]] 3단계). 관리자 > 시스템 기능의 재부팅·종료(`sysfunc.reboot_command` = `NAMIFAX_REBOOT_CMD` 또는 `sudo /sbin/reboot`)도 같은 sudo 를 쓰므로, 단위를 그대로 두면 동작하지 않는다 [코드, 측정 2026-10-03: `setpriv --no-new-privs sudo -n true` 가 "The \"no new privileges\" flag is set, which prevents sudo from running as root." 로 거부했다. `NoNewPrivileges=true` 가 거는 것과 같은 플래그이며, 실제 systemd 단위로 `sudo` 를 돌려 본 것은 아니다]. 재부팅 버튼을 쓸 계획이면 점검 항목에 넣을 것. 같은 화면의 데몬 상태는 이제 `pgrep -x faxq`/`pgrep -x hfaxd` 가 돌려준 실제 프로세스 번호(실행 중 아님 `None`, `pgrep` 을 못 쓰면 `"unknown"`)와 웹 워커 자신의 PID 이다(`services/sysfunc.py` `daemon_status`, `views/admin.py` 가 호출; 이 세션 시작 시점에 해당 파일들은 당시 커밋되지 않은 변경 상태였고 이후 커밋됨(740e12e)).
- [문서] [[install-hylafax]] 는 경로 가정을 `/opt/namifax`(가상환경 `.venv`), `/var/spool/hylafax`, 서비스 사용자 `uucp` 로 둔다. 단위 파일과 `deploy/cron.d` 가 같은 가정이다 [코드].
- [코드] `ProtectSystem=full` 은 `/etc`, `/usr` 를 읽기 전용으로 만든다. 서비스가 쓰는 `/var/spool/hylafax` 는 영향 밖이다 [코드, 측정 2026-10-03: systemd 259 임시 서비스 대조 실험, [[hylafax-integration]] 참조].

## 4. 설치 후 점검 순서(권장)
[문서] [[install-hylafax]] 7단계를 기준으로, 위 코드 대조에서 나온 점검을 앞에 붙인 순서다.

1. `/etc/namifax.env`(`KEY=value`, `&`·공백·`;` 가 든 값은 큰따옴표로 감쌈: 3.1)를 만들고 서비스 사용자가 읽을 수 있게(`root:uucp`, 0640) 한 뒤, `DATABASE_URL`/`NAMIFAX_SESSION_SECRET`/`NAMIFAX_SECRET_KEY` 가 웹 서비스·스케줄러(저장소 단위 파일은 이미 `EnvironmentFile=-` 가 있다)·cron·훅 모두에 전달되는지 확인한다(3.1). 파일이 없으면 서비스는 그대로 뜨고 SQLite 로 떨어지므로 로그의 DB 를 확인한다. 로그에 `No session.secret / NAMIFAX_SESSION_SECRET configured` 경고가 없어야 한다 [코드].
2. DB: 어떤 DB 든 시작할 때(그리고 훅이 불릴 때마다) `ensure_schema` 가 Alembic `upgrade head` 로 테이블을 만든다. 새 DB 에는 기본 표지 3개만 넣고, 데모 계정(admin/operator)은 `NAMIFAX_DEMO_DATA`/`demo.data` 를 켠 **새 SQLite DB** 에서만 만든다 [코드: `db/bootstrap.py`, `db/seed.py`]. 첫 관리자는 `namifax createuser -u <이름> -e <메일>` 로 만든다(비밀번호는 `-p`, `NAMIFAX_NEW_USER_PASSWORD`, 터미널 프롬프트 순. 기본 비밀번호 없음) [코드: `cli/user.py`].
3. 암호화 키: `NAMIFAX_SECRET_KEY` 를 정한 뒤 `namifax encrypt-secrets` 를 한 번 실행한다. 키를 잃으면 암호화된 값은 복구할 수 없다 [코드: `common/secretbox.py` 가 키 없으면 `SecretKeyError`; 복구 불가는 [문서] [[operations-checklist]]].
4. 웹 서버(nginx 또는 apache) 설정 후 HTTPS 로 접속한다. 쿠키 `Secure` 표시는 환경 변수 `NAMIFAX_SESSION_SECURE=1`, 또는 ini `session.secure = true` + `namifax serve --config`/`NAMIFAX_INI`(1.1)로 켠다 [코드].
5. 로그인 → 설정 → 시스템 로그에서 오류를 확인한다 [문서].
6. HylaFAX: `sendfax`, `faxstat` 이 `PATH` 에 있는지 확인한다. 없으면 팩스 보내기가 "HylaFAX 가 설치되지 않았거나 접근할 수 없다"는 오류로 실패한다(2.1 `NAMIFAX_QUEUE_SIMULATION` 을 `1` 로 주지 않은 한 가짜 성공은 없음) [코드]. `sudo -u uucp /var/spool/hylafax/bin/dynconf ttyS0 5551234` 가 아무것도 출력하지 않고 끝나야 한다 [문서].
7. 관리자 > 모뎀에서 모뎀을 만들고 상태가 `Running and idle` 인지, 대시보드에 HylaFAX 버전이 보이는지 확인한다(`faxstat -i`, 못 읽으면 `None` 이라 표시를 지어내지 않음) [코드: `services/hylafax_info.py`].
8. 시험 팩스를 보내 출력함에 나타나는지, `notify` 가 보낸 팩스를 보관함에 올리는지 확인한다. 시험 팩스를 받아 `faxrcvd` 가 받은 팩스함에 올리는지(썸네일, PDF, 메일 알림) 확인한다 [문서].
9. 주기 작업: 관리자 > 예약 작업을 확인하고, 보관함 날짜 삭제(`-d`)가 필요하면 `deploy/cron.d/namifax` 의 주석 줄을 풀어 `/etc/cron.d/namifax` 로 둔다 [코드].
10. SMTP 게이트웨이를 관리자 화면에서 설정한다. 비밀번호 찾기, 수신 팩스 메일 전달, 알림이 이 설정을 쓴다. 기본 호스트는 `localhost` 이고 DB 를 읽지 못하면 로컬 MTA(localhost:25)로 보낸다 [코드: `services/smtp_settings.py`, `services/mailer.py`].

## 5. 운영 전에 사람이 판단할 것
| 항목 | 이유 | 근거 |
|---|---|---|
| `namifax serve`(wsgiref 스레드 서버) 그대로 운영할지, `pserve`+waitress 로 갈지 | 단위 파일은 전자를 쓴다. 쿠키 `Secure` 는 이제 어느 쪽에서도 켤 수 있어 이 이유는 사라졌고, 남는 차이는 서버 구현(wsgiref 는 참고 구현)이다 | [코드] `main.py`, `__init__.py` |
| 쿠키 `Secure` 표시 | HTTPS 에서는 켠다: `NAMIFAX_SESSION_SECURE=1` 또는 ini + `--config`. 기본은 꺼짐 | [코드] `__init__.py` |
| 로그인 시도 제한 값 | 기본은 사용자 이름당 5회 실패 시 계정 잠금(관리자 해제 전까지 유지), 주소당은 10배(50회)에서 15분 잠금. 잠긴 계정은 관리자 사용자 목록의 "Unlock" 버튼이나 `namifax unlock-user <이름>` 으로 푼다. 사무실 하나가 한 공인 주소를 쓰면 주소 한도(`NAMIFAX_LOGIN_MAX_FAILURES` 의 10배)를 올릴지 판단 | [코드] `services/login_throttle.py`, `views/auth.py` |
| SAML IdP Entity ID 설정 | 설정하지 않으면 응답의 `Issuer` 를 검사하지 않고 경고만 남김(`saml_idp_entity_id`) | [코드] `services/saml.py`, `views/admin.py` |
| `/forgot` 요청 횟수 제한(앞단) | 이메일만 알면 남의 기존 비밀번호를 무효화할 수 있음. 새 비밀번호는 본인 메일로만 간다 | [문서] [[operations-checklist]] |
| 사용자 동기화(`HYLAFAX_USER_SYNC`) 켤지 | `faxadduser` 가 비밀번호를 명령줄 인자로 받아 `ps` 로 노출됨. 전용 장비에서만 | [문서] [[install-hylafax]], sudoers 의 `faxadduser -u * -p * *` [코드] |
| SAML 로그인이 앱의 2FA 를 거치지 않음 | 확정된 정책: IdP 가 책임진다 | [문서] [[operations-checklist]] |
| 설정에서 지운 모뎀의 팩스는 받은 팩스함에서 안 보임(슈퍼유저 포함) | 모뎀 삭제 전에 비우거나 보관 | [문서]; 관련 코드 주석: 슈퍼유저 목록은 "설정된 모뎀·DID" 로 제한 [코드: `services/fax_access.py`] |
| 첫 기동 시간 | 큰 `FaxArchive` 에 인덱스를 만들 때 오래 걸릴 수 있음. 측정 안 함 | [문서] [[migrating-from-avantfax3]] |
| 키 회전 | 새 `NAMIFAX_SECRET_KEY` 로 바꾸기 전에 옛 키로 읽을 수 있는 상태에서 작업 | [문서] |
| 번역 | 한국어만 새 문구까지 채워짐. 나머지 언어는 새 화면 문구가 영어로 보일 수 있음 | [문서] [[i18n-and-ui]] |

## 6. 확인하지 못한 것
- 실제 HylaFAX 서버와의 연동(`JobFmt` 열 순서, `faxrm`/`faxalter` 의 소유자 권한, 배포판별 서비스 이름 `faxq`/`hfaxd`/`faxgetty`, 훅 환경 변수 전달). 문서와 파일 내용만 읽었고 연동은 이 세션에서 시험하지 않았다. 출력함은 가짜 `faxstat` 출력으로만 시험됐다고 문서는 말한다 [문서].
- Okta, Entra ID 등 Keycloak 이 아닌 IdP. Keycloak 26 컨테이너로는 2026-10-02 에 직접 시험했다(로그인, 위조·재사용 거부, 역할 부여·회수, 회선 속성 반영).
- 단위 파일·nginx·apache 설정을 실제 서버에 적용해 시작해 보는 것. 이 세션에서는 서버를 띄우지 않았다.
- 이메일 → 팩스(Postfix `faxmail`)는 설명서만 있고 시험하지 않았다 [문서: [[setup-email2fax]]].

## 사용자 매뉴얼(MkDocs)

- [코드] `docs/` 는 MkDocs(Material 테마, `mkdocs-static-i18n` 폴더 방식) 소스다. `docs/ko/`(기본)와 `docs/en/` 에 같은 구조로 `index.md`, `guide/`(개요), `install/`(설치 시작·HylaFAX 연동·AvantFAX 3.x 이전·운영 점검), `manual/`(사용자 매뉴얼)과 `manual/admin/`(관리자 매뉴얼), `dev/`(표지 업로드 계획·GCS 보류 메모)를 둔다. 설정은 저장소 루트 `mkdocs.yml`, 의존성은 `requirements-docs.txt`, 빌드 결과 `site/` 는 `.gitignore` 에 있다.
- [코드] 2026-10-13 에 임시 환경에서 `mkdocs build --strict` 로 한국어·영어 46페이지가 경고 없이 만들어짐을 확인했다. 사용·관리자 매뉴얼은 템플릿·뷰·한국어 번역 파일을 읽고 썼으며 실제 화면을 눌러 보며 확인하지는 않았다.
- [코드] 시험 `tests/unit/test_env_file_wiring.py` 는 `docs/ko/install/hylafax.md` 의 환경 파일 예시 블록을 읽는다. 이 파일 경로를 바꾸면 시험도 고쳐야 한다.
