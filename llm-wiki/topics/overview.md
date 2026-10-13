---
title: NamiFAX 개요
type: topic
updated: 2026-10-03
sources: [pyproject.toml, src/namifax/__init__.py, src/namifax/main.py, src/namifax/routes.py, src/namifax/services/scheduler.py, src/namifax/services/scheduler_config.py, src/namifax/services/cloud_storage.py, src/namifax/services/login_throttle.py, src/namifax/services/saml.py, src/namifax/db/provider.py, src/namifax/models/__init__.py, development.ini, production.ini, deploy/hylafax/, deploy/cron.d/namifax, deploy/sudoers.d/namifax, systemd/, package.json, tailwind.config.js, src/namifax/locale/, "[[architecture-md-part1]]", "[[hylafax-integration-architecture]]", "[[migrating-from-avantfax3]]"]
verified: true
---

# NamiFAX 개요

## 무엇인가
- AvantFAX(PHP, HylaFAX 웹 프런트엔드)를 Python/Pyramid 로 이식한 팩스 웹 시스템이다. 패키지 이름은 `namifax`, 버전 `4.0.0`. [코드] `pyproject.toml`, `src/namifax/__init__.py`
- 원본 PHP 트리(`legacy/`)는 이미 삭제되었다. 필요하면 `git show 9408385:<경로>` 로 읽는다. [코드] `git log` 의 `083920e`, [[migration-from-avantfax]]
- 원본 AvantFAX 3.x 의 DB 를 그대로 이어서 쓸 수 있게 하는 것이 설계 목표다(MD5 해시 수용, `adopt` 모듈 등). [코드] `src/namifax/common/passwords.py`, `src/namifax/db/adopt.py` / [문서] [[migrating-from-avantfax3]]

## 기술 스택
| 영역 | 사용 | 근거 |
|---|---|---|
| 웹 | Pyramid 2 + pyramid_jinja2, `namifax serve` 는 `wsgiref`(스레드형), ini 로 돌릴 때는 waitress(`[server:main]`) | [코드] `pyproject.toml`, `src/namifax/main.py`, `development.ini`, `production.ini` |
| DB | SQLAlchemy 2 ORM, pyramid_tm + zope.sqlalchemy + pyramid_retry, 마이그레이션 Alembic | [코드] `pyproject.toml`, `src/namifax/models/__init__.py` |
| DB 종류 | SQLite(기본), PostgreSQL(`psycopg`), MySQL/MariaDB(`pymysql`) | [코드] `pyproject.toml` 선택 의존성, `src/namifax/db/provider.py` |
| 정기 작업 | APScheduler | [코드] `src/namifax/services/scheduler.py` |
| 인증 | Argon2id(`argon2-cffi`), TOTP(`pyotp`), WebAuthn, SAML(`signxml`), 비밀번호 로그인 시도 제한(`services/login_throttle.py`, 기본 5회 실패 시 계정 잠금(관리자만 해제), 주소는 15분 잠금, `NAMIFAX_LOGIN_MAX_FAILURES`/`NAMIFAX_LOGIN_LOCK_MINUTES`) | [코드] `pyproject.toml`, `src/namifax/services/{totp,webauthn,saml,login_throttle}.py` |
| 문서·이미지 | Pillow, pypdf, pytesseract(OCR), segno(QR) | [코드] `pyproject.toml` |
| 외부 저장소 | boto3 (S3 호환). 수신 팩스는 S3 설정 시 `upload_received_fax` 가 `faxrcvd` 훅에서 올린다(키 `fax<fid>/...`) | [코드] `pyproject.toml`, `src/namifax/services/cloud_storage.py`, `src/namifax/cli/faxrcvd.py` |
| 화면 | Jinja2 + Tailwind CSS 3(빌드 산출물 `main.css` 를 저장소에 포함) | [코드] `package.json`, `tailwind.config.js` |
| 번역 | Babel, 24개 로케일(`src/namifax/locale/<코드>/` 의 `.po` 24개, `git ls-files src/namifax/locale \| grep -c '\.po$'` 로 2026-10-02 측정). 협상기는 `i18n.py` 의 `custom_locale_negotiator` | [코드] `pyproject.toml`, `src/namifax/locale/`, `src/namifax/i18n.py` |

## 전체 데이터 흐름
```
브라우저 --HTTP--> (nginx/apache, deploy/) --> namifax serve (Pyramid, 스레드형 WSGI)
                                                 |  views -> services -> db(ORM 세션) -> RDB
                                                 +-- 같은 프로세스에서 APScheduler(기본 켜짐)

HylaFAX(faxgetty/faxq/hfaxd) --훅 스크립트--> namifax-faxrcvd / notify / dynconf / faxcover
        (deploy/hylafax/bin/* 이 /etc/namifax.env 를 읽고 .venv 의 CLI 를 exec)   --> 같은 RDB + 팩스 파일 저장소

cron(/etc/cron.d/namifax) --> namifax cron (임시폴더 정리 -t, 보관함 이동 -i/-d, TIFF 정리 -p, 저장소 정책 -s)
APScheduler(웹 프로세스 안) --> 작업 4개(tmp 만 run_cron 을 부르고 나머지는 서비스를 직접 호출)
systemd: namifax.service(웹+스케줄러)
```
- 웹: `namifax serve` 가 먼저 `ensure_schema` 를 돌려 스키마를 맞추고, 환경변수 `NAMIFAX_ENABLE_SCHEDULER`(기본 `1`)가 켜져 있으면 APScheduler 를 같은 프로세스에서 시작한 뒤 `create_app()` 을 `wsgiref` 스레드 서버로 띄운다. 기본 포트 `8000`(`NAMIFAX_PORT`), 호스트 `0.0.0.0`(`NAMIFAX_HOST`). `--config`(`NAMIFAX_INI`)로 ini 의 `[app:main]` 설정을 읽어 앱 설정과 DB URL 에 쓴다(읽지 못하면 종료 코드 `1`). [코드] `src/namifax/main.py` `serve_main`, `tests/unit/test_serve_main_db.py`
- HylaFAX 훅: `FaxRcvdCmd: bin/faxrcvd`, `DynamicConfig: bin/dynconf`(`config.namifax`), `NotifyCmd: bin/notify`, `CoverCmd: bin/faxcover`(`etc-faxq.snippet`). 각 쉘 스크립트는 `/etc/namifax.env` 를 읽고(`set -a`) `${NAMIFAX_HOME:-/opt/namifax}/.venv/bin/namifax-faxrcvd` 등을 `exec` 한다. systemd 단위 2개(`EnvironmentFile=-/etc/namifax.env`)와 cron 줄도 같은 파일을 읽는다. [코드] `deploy/hylafax/config.namifax`, `deploy/hylafax/etc-faxq.snippet`, `deploy/hylafax/bin/{faxrcvd,notify,dynconf,faxcover}`, `systemd/*.service`, `deploy/cron.d/namifax`, `tests/unit/test_env_file_wiring.py`. 자세한 내용은 [[hylafax-integration]].
- 정기 작업: 작업 이름은 `tmp`, `inbox`, `lifecycle`, `phonebook` 4개. 설정은 DB(`SystemConfig` 의 `sched_*` 키)에 저장되고 관리자 화면(`/admin/scheduler`)에서 바꾼다. 다른 프로세스가 신선한 실행 표식을 남겼으면 실행은 "already running" 으로 건너뛴다. 스케줄러는 웹 프로세스 안에서만 돈다(별도 `namifax scheduler` 는 2026-10-03 에 제거). [코드] `src/namifax/services/scheduler_config.py`(`JOBS`, `load`, `running_marker`), `src/namifax/services/scheduler.py`(`_run_claimed`), `src/namifax/main.py`. 자세한 내용은 [[scheduler-and-storage]].
- 외부 데몬: HylaFAX(`hfaxd`, `faxq`, `faxgetty`), 메일 서버(Postfix email2fax, `deploy/postfix/setup-email2fax.md`), 선택적으로 PAM·외부 pwauth 인증, SAML IdP. [코드] `src/namifax/auth/pam.py`, `src/namifax/services/saml.py`, `deploy/` / [문서] [[setup-email2fax]]
- `uucp` 사용자가 서비스를 돌리며, `sudoers.d/namifax` 는 `faxadduser`/`faxdeluser`/`reboot`/`halt` 만 허용한다. [코드] `deploy/sudoers.d/namifax`, `systemd/namifax.service`

## 코드 트리 한눈에
```
src/namifax/
  __init__.py   create_app (Pyramid 설정)        main.py   `namifax` CLI 진입점
  routes.py     URL 라우트 선언                   security.py / sessions.py / origin_guard.py
  i18n.py       로케일 협상                       views/ services/ models/ db/ common/ auth/ cli/
  alembic/      마이그레이션(0001~0026)           locale/   .pot/.po/.mo (24개)
  templates/    Jinja2                            static/   css, js, images, theme.css
tests/          unit/ web/ fixtures/ conftest.py  deploy/    hylafax·cron.d·nginx·apache·sudoers.d·postfix·legacy-redirects
systemd/        서비스 유닛                       tools/migration_rehearsal  원본 AvantFAX 이관 리허설 도구
docs/           운영 문서 + llm-wiki/
```
[코드] `git ls-files` 결과(2026-10-02). 계층별 책임은 [[architecture-and-modules]].

## 위키 안내
| 알고 싶은 것 | 페이지 |
|---|---|
| 계층, 라우트, 진입점 | [[architecture-and-modules]] |
| 스키마, Alembic, DB 종류별 동작 | [[database-and-migrations]] |
| 로그인, 2FA, 권한, CSRF | [[authentication-and-security]] |
| 정기 작업, 보관·저장소 정책 | [[scheduler-and-storage]] |
| HylaFAX 훅과 연동 | [[hylafax-integration]] |
| 설치, 배포, 운영 점검 | [[operations-and-deployment]] |
| 시험 | [[testing]] |
| 다국어와 화면 | [[i18n-and-ui]] |
| AvantFAX 에서의 이식 이력 | [[migration-from-avantfax]] |
| 알려진 한계와 결정 | [[known-gaps-and-decisions]] |

원문 요약은 `sources/` 에 있다(문서가 주장하는 바이며 `verified: false`).

## 모순 기록
> 모순: [[architecture-md-part1]] 등 요약이 전제하는 `ARCHITECTURE.md`, `AGENTS.md`, 골든 마스터, `dev/`, `legacy/` 는 현재 작업 트리에 없다. [코드] `git ls-files` 에 없음(삭제 커밋 `01f2f64`, `72a7324`, `4368da8`, `083920e`). 이식 상태 표 같은 "진행 중" 표현은 낡았다고 보고 코드를 따른다.
