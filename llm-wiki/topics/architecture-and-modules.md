---
title: 아키텍처와 모듈
type: topic
updated: 2026-10-03
sources: [src/namifax/__init__.py, src/namifax/main.py, src/namifax/routes.py, src/namifax/security.py, src/namifax/sessions.py, src/namifax/origin_guard.py, src/namifax/models/__init__.py, src/namifax/db/provider.py, src/namifax/db/repository.py, src/namifax/db/bootstrap.py, src/namifax/views/inbox.py, src/namifax/views/auth.py, src/namifax/views/archive.py, src/namifax/views/fax_rights.py, src/namifax/services/login_throttle.py, src/namifax/services/scheduler.py, src/namifax/db/missing.py, src/namifax/db/orm_repository.py, src/namifax/models/meta.py, development.ini, deploy/, systemd/, tests/unit/test_origin_guard.py, tests/unit/test_serve_main_db.py, tests/unit/test_session_secure_flag.py, pyproject.toml, "[[architecture-md-part1]]", "[[architecture-md-part2]]", "[[db-layer-refactor-log]]"]
verified: true
---

# 아키텍처와 모듈

## 진입점
- `pyproject.toml` 의 스크립트: `namifax`(=`namifax.main:main`, 하위 명령 분기), `namifax-server`(`serve_main`), `namifax-createuser`, `namifax-dynconf`, `namifax-faxrcvd`, `namifax-notify`, `namifax-faxcover`, `namifax-cron`, `namifax-phb`. [코드] `pyproject.toml`
- paste 진입점 `paste.app_factory: main = namifax:main` 이고 `namifax.main = create_app` 이므로 ini 로도 띄울 수 있다(`development.ini` 는 waitress, `0.0.0.0:6543`). [코드] `pyproject.toml`, `src/namifax/__init__.py`, `development.ini`
- `namifax <명령>` 명령 목록: serve, scheduler, createuser, import-archive, reset-2fa, encrypt-secrets, dynconf, cron, notify, faxrcvd, faxcover, phb, ocr-import, create-thumbnails, import-users, import-blacklist, reroute, i18n. [코드] `src/namifax/main.py` `main()`
- `serve_main`: `--config`/`-c`(`NAMIFAX_INI`)가 있으면 ini 의 `[app:main]` 설정을 읽고(읽기 실패 시 종료 코드 `1`), 웹 앱과 같은 방식(`resolve_database_url`)으로 URL 을 풀어 `ensure_schema` 실행 → 스케줄러 시작(`NAMIFAX_ENABLE_SCHEDULER`, 기본 `1`) → `create_app(**settings)`. 앱 생성이 실패하면 스케줄러를 멈추고 대체 앱으로 숨기지 않고 stderr 에 쓴 뒤 종료 코드 `1`. [코드] `src/namifax/main.py`, `tests/unit/test_legacy_trees_removed.py`, `tests/unit/test_serve_main_db.py`
- `main.py` 의 `faxrcvd_main` 등은 PHP 시절 스크립트 이름(`faxrcvd.php`, `notify.php`, `avantfaxcron.php`)을 `argv[0]` 으로 넣어 호출한다. [코드] `src/namifax/main.py`

## create_app 이 하는 일 ([코드] `src/namifax/__init__.py`)
1. `Configurator(root_factory=RootContext)` 와 `NamiFaxSecurityPolicy` 를 설정한다(`registry.namifax_policy` 에 보관).
2. 서명 쿠키 세션 `namifax_flow`(2FA 단계, 패스키 챌린지용 짧은 흐름 상태). 로그인 자체는 보안 정책의 토큰 쿠키가 한다. 비밀은 `session.secret` 또는 `NAMIFAX_SESSION_SECRET`, 없으면 프로세스마다 무작위값을 쓰고 경고를 남긴다. 쿠키 `Secure` 는 ini `session.secure` 가 우선이고 없으면 `NAMIFAX_SESSION_SECURE`(기본 꺼짐). 쿠키 `HttpOnly`, `SameSite=Lax`, 제한 시간 1800초. [코드] `tests/unit/test_session_secure_flag.py`
3. `secret.key` 설정을 `secretbox` 기본 키로 등록.
4. 번역 디렉터리 `namifax:locale`, 로케일 협상기 `custom_locale_negotiator`.
5. `pyramid_jinja2` 와 `.models` include. `.models` 가 `pyramid_tm`, `pyramid_retry`, 엔진 1개, `request.dbsession`(reify) 을 만든다.
6. `BeforeRender` 구독자가 모든 템플릿에 스위치(`did_routing_enabled`, `barcode_enabled`, `dl_tiff_enabled` 등)와 헤더용 수치(안 읽은 수 `num_inbox`, `user_full_name`, `modem_devices`)를 넣는다.
7. `ensure_schema(engine, settings)` → `.routes` include → 트윈 `namifax.origin_guard.origin_guard_factory` → `config.scan(".views")`.

## 계층과 의존 방향
```
views  ->  services  ->  db(Repository/ORM)  ->  models
  \          \-> common, auth
   \-> templates(Jinja2)         cli -> services/db/common   (웹과 독립된 진입점)
```
의존은 대체로 위에서 아래로 흐르지만 엄격하지 않다. [코드] `ast` 로 `src/namifax` 의 import 를 패키지별로 모아 확인했다(2026-10-03). 규칙에 어긋나는 import: `services/scheduler.py` 가 모듈 맨 위에서 `namifax.cli.cron`·`namifax.cli.phb` 를 가져온다(services → cli). 함수 안에서 늦게 가져오는 것: `services/printer.py:146` → `views.sendfax`, `services/user_account.py:344` → `auth`, `common/helpers.py` → `services`·`db`(여러 곳), `db/adopt.py`·`db/textsearch.py`·`db/orm_repository.py` → `models`, `models/__init__.py:35` → `db.provider`. `db/seed.py` 와 `db/orm_repository.py` 는 모듈 맨 위에서 `models` 를 가져오고 `models` 는 함수 안에서 `db` 를 가져와, 순환은 늦은 import 로 피한다. 계층 규칙을 강제하는 도구나 시험은 없다(`importlinter`/`import-linter` 를 쓰는 파일이 `pyproject.toml`, `tests`, `src` 에 없음).

| 패키지 | 책임 | 근거 |
|---|---|---|
| `views/` | Pyramid 뷰(`@view_config`). 폼 처리, 권한 지정, 서비스 호출, 템플릿 렌더링. `admin.py`(1138줄, `wc -l` 2026-10-02)가 관리자 화면 대부분을 가진다 | [코드] `src/namifax/views/*.py` |
| `services/` | 업무 로직(주소록, 보관함 `archive_in/out/base/orm`, 큐, 커버 페이지, DID/바코드 라우팅, 모뎀, 메일, OCR, TOTP, WebAuthn, SAML, 로그인 시도 제한(`login_throttle`), 스케줄러, 저장소 수명 주기, 시스템 설정 등). 세션을 인자 `db=` 로 받는다 | [코드] `src/namifax/services/` |
| `models/` | SQLAlchemy 모델(테이블 이름은 원본처럼 `UserAccount`, `FaxArchive` 등 혼합 대소문자), `meta.Base`, `types.py` | [코드] `src/namifax/models/` |
| `db/` | `provider`(URL 해석, 엔진, `cli_session`), `bootstrap`(`ensure_schema`), `repository`/`orm_repository`(PHP `MDBOData` 호환 API), `adopt`/`sqlite_upgrade`(기존 테이블 수용), `seed`, `missing`, `textsearch` | [코드] `src/namifax/db/` |
| `common/` | `settings`(원본 `local_config.php` 이름의 환경변수), `secretbox`(자격증명 암호화), `passwords`(Argon2id + MD5 수용), `helpers`, `upload`, `validators` | [코드] `src/namifax/common/` |
| `auth/` | `password`(해시, 외부 pwauth), `pam`, `alternate`(대체 인증 설정) | [코드] `src/namifax/auth/` |
| `cli/` | HylaFAX 훅과 배치 도구, 사용자 관리, i18n 관리 | [코드] `src/namifax/cli/` |
| 최상위 모듈 | `security.py`(ACL, 보안 정책), `sessions.py`(메모리 로그인 세션), `origin_guard.py`(CSRF 성격 방어 트윈), `i18n.py`, `routes.py` | [코드] |
| `alembic/` | 리비전 `20261001_0001` ~ `20261002_0026` | [코드] `src/namifax/alembic/versions/` |

- DB 세션은 요청마다 `request.dbsession` 으로, CLI 는 `cli_session()` 으로 얻는다. 전역 엔진은 없다(엔진은 레지스트리 `dbengine`). [코드] `src/namifax/db/provider.py`, `src/namifax/models/__init__.py`, `tests/unit/test_global_engine_removed.py`
- `db=` 를 빠뜨리면 `db/missing.py` 의 자리표시자가 첫 사용 때 큰 소리로 실패한다. [코드] `src/namifax/db/repository.py` docstring
- DB URL 우선순위: `sqlalchemy.url` 설정 > `DATABASE_URL` > `AFDB_URL` > `NAMIFAX_DB_PATH` 또는 현재 폴더의 `namifax.db`. [코드] `src/namifax/db/provider.py`
- 세부는 [[database-and-migrations]], 인증은 [[authentication-and-security]].

## 보안 정책과 권한
- ACL: `public` 은 모두, `view`·`send_fax` 는 인증된 사용자, `admin` 은 `role:admin` 만(나머지 Deny). [코드] `src/namifax/security.py` `RootContext.__acl__`
- 신원은 `Authorization: Bearer`, 쿠키 `namifax_session`(옛 이름 `avantfax_session` 도 받음), 흐름 세션 순으로 토큰을 찾아 `SessionManager` 에서 조회한다. [코드] `src/namifax/security.py`
- 로그인 세션 저장소는 프로세스 메모리다: `SessionManager` 가 `self._sessions` 딕셔너리에 토큰을 두고 기본 유휴 제한 7200초. [코드] `src/namifax/sessions.py`. 따라서 다중 워커·재시작 사이에 로그인 세션은 공유되지 않는다(코드상 외부 저장소 없음에서 도출). 반면 비밀번호 로그인 실패 횟수는 `SystemConfig` 에 두어 워커끼리 공유한다. [코드] `src/namifax/services/login_throttle.py`
- `origin_guard`: `POST/PUT/PATCH/DELETE` 가 `Origin`(없으면 `Referer`)을 말하면 요청 호스트, `X-Forwarded-Host`, `csrf.trusted_origins` 중 하나여야 한다. `Origin: null` 은 거부. SAML ACS/SLS 경로(`/auth/saml/acs`, `/auth/saml/sls`)는 제외. [코드] `src/namifax/origin_guard.py`, `tests/unit/test_origin_guard.py`

## 라우트와 뷰 구조
- `routes.py` 의 `includeme` 가 `static` 뷰(`cache_max_age=3600`)와 라우트를 모두 선언한다. 뷰는 `config.scan(".views")` 로 `@view_config` 에서 모은다. [코드] `src/namifax/routes.py`
- 묶음별 라우트(이름 → 경로):
  - 공개: `home /`, `login`, `logout`, `forgot`, `pwdexpired`, `login_totp /login/totp`
  - 사용자: `inbox`, `viewfax`, `/faxes/download|image|thumbnail|rotate/...`, `sendfax`, `outbox`, `archive`, `/search`(OpenSearch), `addressbook(/edit)`, `emailbook(/edit)`, `distrolist(/edit)`, `settings`, `/settings/2fa/{setup,enable,disable,recovery}`
  - 관리자(`permission="admin"`): `/admin`, `/admin/users`, `modems`, `routing/did`, `barcodes`, `covers`, `categories`, `dynconf`, `fax2email`, `system_func`, `system_logs`, `smtp`, `printers`, `storage`, `scheduler(/state,/jobs)`, `saml`
  - 모달: `/email`, `/assign`, `/assignx`, `/note`, `/delete`, `/refax`, `/txreport`
  - AJAX: `/ajax/{modemstatus,inbox,book,emailbook,prefillto,dlist,archivefax,faxalter,deletefaxes,archivebook}`, `/audio/{name}`
  - 원본 호환 별도 경로: `/rotate`, `/setcompany`
  - 도우미 팝업 `/helper/*`, vCard 업로드 `/upload/contacts|faxcontacts`
  - WebAuthn `/api/webauthn/...`, SAML `/auth/saml/{metadata,login,acs,sls}`
- 일부 경로는 별칭이 둘이다(`admin_did`/`admin_routing_did`, `admin_sysfunc`/`admin_system_func`, `admin_syslog`/`admin_system_logs`). [코드] `src/namifax/routes.py`
- 뷰 파일: `inbox, outbox, archive, sendfax, addressbook, distrolist, modals, ajax, fax_files, fax_rights, helpers, auth, settings, settings_2fa, webauthn, saml, admin, admin_users, admin_scheduler, default, forbidden, notfound, no_database`. 렌더러는 `renderer="namifax:templates/<이름>.jinja2"`(상수 `TEMPLATE` 로 쓰는 뷰도 있음) 또는 `json`(`forbidden_view` 포함). 뷰 파일 23개(2026-10-02 `ls`). [코드] `src/namifax/views/`, `src/namifax/views/inbox.py`
- 팩스 접근 권한 계산은 `views/fax_rights.py` 의 `fax_access(request)`(반환 `FaxAccess`)와 `services/fax_access.py` 가 한다. `src/namifax/__init__.py` 의 `_add_page_counters` 가 이를 import 해 헤더 수치를 만든다. [코드] `src/namifax/views/fax_rights.py`, `src/namifax/__init__.py`
- 화면 규칙은 [[i18n-and-ui]].

## 모순 기록
> 모순: [[architecture-md-part1]] / [[architecture-md-part2]] 의 의존성 그래프와 "이식 상태 `[PENDING]`/`[IN_PROGRESS]`" 표, `[FFI_BRIDGED]` 개념은 현재 코드에 대응물이 없다(이식 완료, 브리지 없음). [코드] 위 구조를 따른다.
> 모순: 요약이 말하는 "JSON 대체 웹 앱" 이나 `avantfax` 복사본은 없다. [코드] `tests/unit/test_legacy_trees_removed.py` 가 `avantfax`, `namifax.web` 모듈 부재를 확인한다.
