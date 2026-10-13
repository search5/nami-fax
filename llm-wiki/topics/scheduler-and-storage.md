---
title: 스케줄러와 스토리지
type: topic
updated: 2026-10-03
sources: [src/namifax/services/scheduler.py, src/namifax/services/scheduler_config.py, src/namifax/services/job_control.py, src/namifax/views/admin_scheduler.py, src/namifax/cli/cron.py, src/namifax/cli/phb.py, src/namifax/cli/faxrcvd.py, src/namifax/services/archive_in.py, src/namifax/routes.py, src/namifax/templates/admin_scheduler_state.jinja2, src/namifax/main.py, src/namifax/services/storage_lifecycle.py, src/namifax/services/cloud_storage.py, src/namifax/views/admin.py, src/namifax/templates/admin_storage.jinja2, src/namifax/static/js/storage.js, src/namifax/static/js/scheduler.js, systemd/, deploy/cron.d/namifax, tests/unit/test_scheduler_admin.py, tests/unit/test_scheduler_job_control.py, tests/unit/test_storage_page_fields.py, tests/unit/test_cloud_storage.py, tests/unit/test_storage_lifecycle_orm.py, tests/unit/test_remote_upload.py, tests/unit/test_cli_phb.py, tests/unit/test_scheduler.py, [[hylafax-integration-architecture]], [[future-gcs-storage]], [[install-hylafax]], [[new-features-plan]]]
verified: true
---

# 스케줄러와 스토리지

정기 유지보수 작업(APScheduler)과 보관 저장소(로컬/S3 호환)를 다룬다. 다른 주제: [[architecture-and-modules]] [[database-and-migrations]] [[operations-and-deployment]] [[hylafax-integration]] [[testing]] [[known-gaps-and-decisions]].

## 1. 작업 4종

작업 이름은 `JOBS = ("tmp", "inbox", "lifecycle", "phonebook")` 이다. [코드] `src/namifax/services/scheduler_config.py`

| 작업 | 하는 일 | 기본 설정 | 실제 호출 |
|---|---|---|---|
| `tmp` | 임시 폴더(`AVANTFAX_TMPDIR`, 기본 `/tmp/avantfax/`)에서 N일 지난 항목 삭제 | 켜짐, 00:00, 1일 | `run_cron(["cron","-t",N])` |
| `inbox` | 받은 팩스함에서 N일 지난 팩스를 보관함으로 이동 | **꺼짐**, 01:00, 30일 | `ArchiveIn.prune_inbox(N)` |
| `lifecycle` | Storage 화면에 저장한 정책 실행(TIFF 정리, 보존 만료 삭제, 원격 삭제) | 켜짐, 00:00 | `StorageLifecycleService.run_saved_policy()` |
| `phonebook` | 주소록을 HylaFAX `PBOOK1.1` 파일로 내보냄 | 켜짐, 60분마다 | `export_phonebook_count()` (`cli/phb.py`) |

- [코드] `src/namifax/services/scheduler.py` `_run_claimed`: 위 호출 그대로. 첫 세 작업은 매일 `CronTrigger(hour, minute)`, `phonebook` 은 `IntervalTrigger(minutes)`(`apply_config`). 놓친 실행은 `misfire_grace_time=3600`, `coalesce=True`.
- [코드] 값 범위: 일수 1~3650, 전화번호부 주기 1~10080분. 시각이 `HH:MM` 이 아니면 기본값으로 대체. (`scheduler_config.load`, `clean_time`)
- [코드] `lifecycle` 은 정책이 저장되지 않았으면(`storage_purge_tiff_days`, `storage_retention_days` 둘 다 빈 값) 아무것도 지우지 않고 "no policy saved ..." 로 끝난다. Storage 화면에 보이는 기본값 7/365 는 **저장 전에는 실행되지 않는다**. [코드] `storage_lifecycle.run_saved_policy`
- [코드] 각 실행은 `sched_last_<작업>` 에 `{ok, summary, at, stopped}` JSON 으로 기록되고, 시스템 로그에 `scheduler> <작업>: <요약>` 도 남긴다. 작업이 예외를 내도 스케줄러는 죽지 않고 `failed: ...` 로 기록한다. [코드] `scheduler._run_claimed`

> 모순: 위키 요약 [[install-hylafax]] 는 "내장 스케줄러는 임시 파일 정리만 한다"는 옛 서술을 옮겨 두었다. 코드의 내장 스케줄러는 위 4종을 모두 돌린다(`inbox` 는 기본 꺼짐, `lifecycle` 은 정책 저장 시). 저장소의 `docs/ko/install/hylafax.md` 는 이번 변경에서 이미 4종으로 정정됐다(72~77행을 읽어 확인). 남은 차이: **`-d`(보관함의 오래된 팩스 삭제)에 정확히 대응하는 스케줄러 작업은 없다**. 비슷한 일은 `lifecycle` 의 `full_retention_days`(DB 행·파일·원격 삭제)이고, `cron -d` 는 `FaxPDFArchive.prune_archive` 를 부르며 `deploy/cron.d/namifax` 의 주석 줄에서만 쓴다. [코드] `deploy/cron.d/namifax`, `src/namifax/cli/cron.py`, `src/namifax/services/archive_base.py`

> 모순: 위키 요약 [[hylafax-integration-architecture]] 는 원문대로 화면 경로를 `/admin/maintenance` 라 하고 "이력 대시보드"를 말한다. 코드의 경로는 `/admin/scheduler` 이고(`src/namifax/routes.py` 58~60행), `/admin/maintenance` 라우트는 없다. 이력은 작업별 "마지막 실행 결과" 한 건(`sched_last_<작업>`)만 보관한다. 저장소 원문 `docs/hylafax_avantfax_integration_architecture.md`(삭제됨, `git show 614f7b0:docs/hylafax_avantfax_integration_architecture.md`) 머리말은 이 점을 이미 정정했다. [코드]

## 2. 설정 저장소: SystemConfig 의 `sched_*` 키

모든 상태는 `SystemConfig` 키-값 표에 있다(별도 테이블 없음). [코드] `scheduler_config.py`, `services/system_config.py` ([[database-and-migrations]])

| 키 | 의미 |
|---|---|
| `sched_<작업>_enabled`, `_time`, `_days`, `_minutes` | 작업별 설정(`tmp_*`, `inbox_*`, `lifecycle_*`, `phonebook_*`) |
| `sched_stopped` | `1` 이면 관리자가 스케줄러를 정지시킨 상태 |
| `sched_heartbeat` | 스케줄러(웹 프로세스 안)가 마지막으로 살아 있다고 알린 시각(ISO) |
| `sched_engine_state` | `running` / `stopped`: APScheduler 엔진이 실제로 도는지 |
| `sched_running_<작업>` | 실행 중 표지 `{by, started}` JSON. 6시간(`STALE_RUNNING_SECONDS`) 넘으면 죽은 프로세스가 남긴 것으로 보고 무시 |
| `sched_cancel_<작업>` | `1` 이면 중지 요청 |
| `sched_last_<작업>` | 마지막 실행 결과 JSON |

- [코드] `signature()` 는 설정값 전체와 `stopped` 를 JSON 으로 묶은 문자열이다. 돌고 있는 스케줄러가 이것을 기억해 두었다가 달라지면 다시 일정을 짠다.
- 키 이름이 `cloud_*`, `storage_*` 인 스토리지 설정도 같은 표를 쓴다(아래 4절).

## 3. 실행 구조

### 컨트롤러 스레드와 하트비트
- [코드] `NamiFaxScheduler.start()` 는 (a) 정지 상태가 아니면 APScheduler `BackgroundScheduler` 엔진을 올리고, (b) **컨트롤러 스레드**(`NamiFaxSchedulerControl`)를 시작한다. 이 스레드는 `control_interval = 15`초마다 `watch_config()` 를 부른다. (`services/scheduler.py`)
- [코드] `watch_config()` 한 번의 일: `sched_stopped` 가 꺼져 있고 엔진이 없으면 엔진 시작, 정지 요청이 있고 엔진이 돌면 엔진 종료, 둘 다 아니고 설정 서명이 바뀌었으면 일정을 다시 짬. 그리고 항상 `beat()` 로 `sched_heartbeat`, `sched_engine_state` 를 기록한다.
- [코드] 하트비트가 180초(`ALIVE_SECONDS`) 안이면 "살아 있음". 화면 상태는 이 값과 `sched_stopped`, `sched_engine_state` 로 계산한다.
- [코드] APScheduler 패키지가 없으면 컨트롤러 없이 단순 스레드 타이머가 전화번호부 내보내기만 `phonebook_sync_interval_mins`(기본 60)마다 돌린다. 이 경로는 정지/시작·설정 반영이 없다.
- [코드] DB 를 읽지 못하면 기본값으로 엔진을 그냥 시작한다(`start_engine_without_settings`; 이때는 등록된 작업이 없다).

### 정지/시작
- [코드] 화면의 정지/시작은 `sched_stopped` 만 바꾼다. 스케줄러가 **이 웹 프로세스에 내장**돼 있으면(`get_scheduler().is_running`) 바로 `watch_config()` 를 불러 즉시 반영하고, 다른 웹 프로세스의 스케줄러면 최대 15초 안에 그 프로세스의 컨트롤러가 반영한다. (`views/admin_scheduler.py`)
- [코드] 정지는 **엔진만 끈다**. 프로세스와 컨트롤러는 남아 시작 요청을 기다린다. 정지 상태는 DB 에 있으므로 재시작해도 유지된다. 정지 중에도 "지금 실행"은 동작한다. [코드·시험] `tests/unit/test_scheduler_admin.py` (`test_run_now_still_works_while_stopped`, `test_saving_the_settings_does_not_start_a_stopped_scheduler`)
- 화면 상태 단계(`_state`): `none`(하트비트 없음), `running`, `starting`, `stopped`, `stopping`. 버튼은 하트비트가 없어도 항상 보인다. [코드]

### 동시 실행 방지와 작업별 실행 중 표시
- [코드] `claim(name, by)` 가 프로세스 안 `_RUNNING` 딕셔너리(+ 락)에 작업을 예약한다. 이미 있으면 `None` → `run_job` 은 `{"ok": False, "summary": "already running", ...}` 으로 돌아온다. 같은 작업은 같은 프로세스에서 동시에 두 번 돌지 않는다.
- [코드] 프로세스 간: `_run_claimed` 는 시작할 때 `cfg.running_marker()` 로 `sched_running_<작업>` 표지를 먼저 확인한다. 6시간(`STALE_RUNNING_SECONDS`) 안의 표지가 있으면 다른 프로세스가 돌리는 중이라 보고 **실행하지 않고** `"already running"` 을 돌려준다(`ok=False`). 이 경로는 `record_run` 을 부르지 않으므로 `sched_last_<작업>` 은 바뀌지 않고, 이쪽 프로세스의 예약은 `release` 로 돌려준다. 표지가 없으면 `mark_running` 으로 직접 표지를 써서 **다른 프로세스(웹 ↔ 별도 스케줄러)도 실행 중임을 볼 수** 있게 한다. 정기 실행(`_scheduled` → `run_job`)과 "지금 실행"이 같은 `_run_claimed` 를 지나므로 둘 다 이 검사를 받는다. 화면의 "지금 실행"은 그 전에 `is_running(job, session)` 으로 표지까지 검사해 거절한다("This task is already running."). [코드·시험] `tests/unit/test_scheduler_job_control.py` (`test_a_scheduled_run_yields_to_a_fresh_marker_of_another_process`, `test_a_stale_marker_does_not_block_and_the_marker_is_cleared_at_the_end`)
- 한계: 죽은 프로세스가 남긴 표지는 6시간 동안 정기 실행과 "지금 실행"을 막는다(그 뒤에는 낡은 표지로 무시). [코드] `scheduler_config.running_marker`. 또 표지 확인(읽기)과 `mark_running`(쓰기)은 락이나 원자적 갱신 없이 이어서 하는 두 단계라, 같은 DB 를 쓰는 스케줄러가 둘이고 같은 순간에 시작하면 둘 다 통과한다(웹 서비스를 하나만 운영하면 생기지 않는다). [코드, 측정 2026-10-03] 4개 DB 모두 40번 중 39번 둘 다 통과했다([[operations-and-deployment]] §1.3 의 측정). 이 경쟁을 고정하는 시험은 저장소에 아직 없다.
- [코드] "지금 실행"은 기본으로 데몬 스레드(`namifax-job-<이름>`)에서 돈다(`THREADED = True`; 시험에서는 동기 실행). 화면은 즉시 "실행 중"으로 바뀌고 2초마다 `/admin/scheduler/jobs` 를 불러 갱신한다.

### 중지(협조적 취소 `should_stop`)
- [코드] 강제 종료가 아니라 **다음 안전 지점에서 멈추는 협조적 취소**다. 작업마다 `should_stop()` 콜백을 받아 반복 사이에 확인한다: `tmp` 는 파일 사이, `inbox` 는 팩스 사이, `lifecycle` 은 폴더/팩스 사이, `phonebook` 은 업체 사이.
- [코드] `should_stop()` 은 프로세스 안 `cancel` 이벤트를 먼저 보고, 아니면 약 1초에 한 번 `sched_cancel_<작업>` 키를 읽는다(다른 프로세스에서 누른 중지를 듣기 위함). `request_stop()` 이 둘 다 설정한다.
- [코드] 전화번호부는 파일을 반만 쓰지 않도록 `JobStopped` 예외를 던져 **아무것도 쓰지 않고** 끝낸다("stopped by an administrator before anything was written"). 나머지는 지금까지 한 만큼을 요약에 적고 `stopped=True` 로 기록한다. 화면은 중지된 결과를 실패가 아니라 호박색으로 보인다. [코드·시험] `tests/unit/test_scheduler_job_control.py`
- 중지 요청 뒤에도 작업이 멈추기 전까지 "중지 중" 표시가 유지된다(`stopping`). [코드] `views/admin_scheduler.py::_jobs_html`

> 모순(고쳐짐): 이전 위키는 `phonebook` 요약이 종료 코드 `0` 을 "entries" 개수로 써서 항상 "(0 entries)" 가 된다고 적었다. 현재 코드는 `export_phonebook_count()`(`cli/phb.py`)가 실제로 쓴 업체 수(`build_phonebook` 의 `count`)를 돌려주고, 요약은 "phonebook exported (N entries)" 이다. `export_phonebook()`/`run_phb()` 는 종료 코드 `0` 계약을 그대로 둔다. [코드·시험] `tests/unit/test_scheduler_job_control.py` (`test_the_phonebook_export_reports_how_many_entries_it_wrote`, `test_the_phonebook_job_summary_uses_the_real_entry_count`)
- [코드] 세는 단위는 항목이 아니라 **업체(`get_companies()` 한 건)** 이다. `generate_phonebook_content` 는 줄바꿈 없이 이어 붙인 문자열을 만든다(시험도 `PBOOK1.1Acme Corp|...` 형태를 기대: `tests/unit/test_cli_phb.py`). [코드, 측정 2026-10-03] 원본 `includes/phb.php`(`git show 9408385:legacy/avantfax/includes/phb.php`)의 제어 흐름을 같은 입력으로 옮겨 비교했다(PHP 를 실행한 것이 아니라 Python 으로 옮긴 것). 번호가 정상인 업체는 출력이 같다. 차이는 번호가 빈 경우다: 원본은 앞에 유효한 번호가 있으면 빈 번호 자리에도 `;` 를 써서 `111;`, `111;;222` 가 되고, 이 구현은 빈 번호를 건너뛰어 `111`, `111;222` 가 된다. 앞쪽의 빈 번호와 번호가 하나도 없는 업체는 같다. 실제 HylaFAX 가 이 파일을 읽는지는 시험된 적이 없다([[hylafax-integration]]).

## 4. 관리자 화면과 엔드포인트

| 경로 | 권한 | 역할 |
|---|---|---|
| `/admin/scheduler` (GET) | admin | 작업별 설정 폼, 상태 상자, 작업 블록 |
| `/admin/scheduler` (POST) | admin | `action` = `stop`, `start`, `run`(+`job`), `stop_job`(+`job`), 그 외는 설정 저장 |
| `/admin/scheduler/state` | admin | 상태 상자 조각(HTML). 화면이 3초마다 가져옴(`static/js/scheduler.js`) |
| `/admin/scheduler/jobs` | admin | 작업별 상태 블록 조각(마지막 결과, 지금 실행/중지 버튼). 2초마다 |

- [코드] `X-Requested-With: XMLHttpRequest` 로 POST 하면 전체 페이지 대신 상태 조각만 돌려준다(새로고침 없이 버튼 전환).
- [코드] 설정 저장은 체크박스 `*_enabled` 가 폼에 없으면 꺼짐으로 처리한다. 잘못된 시각은 기존 값을 유지하고 오류 문구를 보인다. 저장 문구는 "실행 중 스케줄러가 1분 안에 반영"이며, 실제 반영 지연은 컨트롤러 주기 15초 이하다. [코드] 이 화면은 정책 일수 요약(`policy`)도 보여 주는데 값은 Storage 화면에서 저장한 키에서 읽는다.
- 시험 [코드]: `tests/unit/test_scheduler_admin.py`, `tests/unit/test_scheduler_job_control.py`(설정 저장·정지/시작·중지·조각 엔드포인트), `tests/unit/test_scheduler.py`. 이 세션에서는 시험을 실행하지 않았다.

## 5. 웹 내장 실행

- [코드] 스케줄러는 웹 프로세스 안에서만 돈다. `namifax serve` 가 `NAMIFAX_ENABLE_SCHEDULER`(기본 `1`; `1`/`true`/`True` 만 켜짐)이면 `get_scheduler().start()` 로 시작한다. `systemd/namifax.service` 는 `Environment="NAMIFAX_ENABLE_SCHEDULER=1"` 을 주고 이어서 `EnvironmentFile=-/etc/namifax.env` 를 읽는다. 정지 버튼은 같은 프로세스라 즉시 반영되고, 화면의 "지금 실행"은 웹 프로세스 스레드에서 실행된다.
- [코드] 별도 프로세스로 스케줄러만 돌리던 `namifax scheduler`(`run_scheduler_standalone`), `systemd/namifax-scheduler.service`, 스크립트 `namifax-scheduler`, `start(blocking=True)` 는 2026-10-03 에 제거했다. 이유: 같은 DB 를 쓰는 스케줄러가 둘이면 같은 작업을 같은 순간 시작하는 경쟁이 있다(3절). 제거를 고정하는 시험은 `tests/unit/test_standalone_scheduler_removed.py`.
- [코드] 내장 스케줄러는 `namifax serve`(`main.py::serve_main`)에서만 시작된다. `create_app()`/`pserve` 같은 다른 방법으로 웹을 띄우면 스케줄러가 시작되지 않는다(`src/namifax/__init__.py` 에 시작 코드 없음). 이 경우 화면은 "No scheduler is running ..." 안내를 보인다. [코드] `templates/admin_scheduler_state.jinja2`
- [코드] 한 DB 에는 웹 서비스를 하나만 운영한다. 둘 이상 띄우면 각 프로세스가 자기 스케줄러를 돌려 둘 다 하트비트를 쓰고 둘 다 작업을 건다(같은 순간에 시작하면 3절의 경쟁으로 둘 다 돈다). 웹 서비스 자체도 둘을 함께 쓸 수 없다: [[operations-and-deployment]] §1.1 의 측정(시작 시 마이그레이션 충돌, 로그인 상태 비공유). 동시에 띄우지 못하게 막는 코드는 없다(2026-10-03 `grep`).
- [코드] `deploy/cron.d/namifax` 는 스케줄러 대신 OS cron 을 쓰는 대안이다. 각 줄은 `sh -c 'set -a; [ -r /etc/namifax.env ] && . /etc/namifax.env; set +a; exec .../namifax cron ...'` 로 감싸 `/etc/namifax.env` 를 읽고 실행한다(cron 에는 `EnvironmentFile` 이 없으므로). 파일에서 기본으로 켜진 줄은 `0 0 * * * ... namifax cron -t 2` 뿐이고 `-i 30 -d 365`, `-p 90`, `-s` 줄은 주석이다. 스케줄러의 `tmp` 작업과 이 cron 줄을 같이 켜면 중복이지만 파괴적이지 않다(오래된 파일 삭제). `cron -s` 는 `run_saved_policy()` 로 `lifecycle` 작업과 같은 일을 한다. [코드] `cli/cron.py`
- 레거시와의 차이: 레거시는 `avantfaxcron.php` 와 OS crontab 이 전부였다. 현재는 같은 옵션 `-t -i -d -p -s` 를 가진 `namifax cron` 명령이 남아 있고, 스케줄러가 그 위에 얹혔다. [코드] [문서] [[hylafax-integration-architecture]]

## 6. 스토리지

### 제공자
- [코드] `StorageConfig.storage_type` 은 `LOCAL` 또는 `S3` 만 의미가 있다. `CloudStorageManager.get_provider` 는 `S3` 이면 `S3CompatibleStorageProvider`(boto3), **그 밖의 모든 값은 `LocalStorageProvider`** 를 돌려준다. (`services/cloud_storage.py`)
- [코드] `LocalStorageProvider`: 기본 폴더는 `NAMIFAX_ARCHIVE_DIR`(기본 `/var/spool/hylafax/archive`). 만들 수 없고 환경변수도 없으면 `~/.namifax/archive` 로 물러선다.
- [코드] `S3CompatibleStorageProvider`: 엔드포인트(MinIO, Ceph, Cloudflare R2 등), 리전, 버킷, 접근 키·비밀 키, 접두사. 엔드포인트가 비면 boto3 기본(AWS)으로 간다. 메서드: `upload_file`, `download_file`, `delete_file`, `delete_fax`(정확히 `fax<ID>/` 접두사 아래 객체만 삭제; 예전에는 `fax1` 접두사라 `fax10` 도 지웠다), `test_connection`(`head_bucket`). 키 규칙은 `fax_object_key(fid, name)` = `fax<fid>/<name>`, 설정한 접두사는 `_resolve_key` 가 앞에 붙인다.
- [코드] `provider_from_config(cfg)`: 저장된 `cloud_storage_type` 이 (대소문자 무시) `S3` 가 아니면 `None`(원격 복사본 없음), `S3` 이면 `cloud_*` 키(`cloud_endpoint_url`, `cloud_region_name`, `cloud_bucket_name`, `cloud_access_key`, `cloud_prefix`)와 비밀 키(`get_secret("cloud_secret_key")`)로 `S3CompatibleStorageProvider` 를 만든다. 수신 업로드와 수명주기가 이것을 쓴다.
- [코드·시험] `tests/unit/test_cloud_storage.py` 와 `tests/unit/test_remote_upload.py` 는 boto3 를 mock 으로, 업로드 제공자는 `FakeProvider` 로 대체해 검사한다. [코드, 측정 2026-10-03] 그와 별도로 실제 HTTP S3 API 서버(`moto_server`, 에뮬레이터이며 AWS 나 MinIO 가 아님)를 띄워 `S3CompatibleStorageProvider` 로 연결 시험, 업로드, 내려받기(내용 일치), 파일 삭제, `delete_fax(1)`(`fax10/` 는 남음), 없는 버킷(연결 시험 실패, 업로드 False)을 확인했고 모두 기대대로였다. 이 시험은 저장소에 남기지 않았다. AWS S3 와 MinIO 로는 하지 못했다(MinIO 이미지는 Docker Hub 와 Quay 에서 내려받을 수 없었다).

> 모순(일부 고쳐짐): 이전 위키는 "코드에서 `upload_file` 을 부르는 곳이 없어 S3 는 연결 시험과 원격 삭제에만 쓰인다"고 적었다. 현재 코드는 **수신 팩스를 S3 로 올린다**: `cli/faxrcvd.py` 가 보관함 등록(`inbox.create`) 성공 뒤 `upload_received_fax(session, faxid, faxpath)` 를 부르고(206행), 이 함수는 `provider_from_config` 가 제공자를 돌려줄 때(S3)만 `faxpath` 의 `fax.tif`, `fax.pdf` 중 **있는 파일**을 키 `fax<fid>/fax.tif`, `fax<fid>/fax.pdf`(접두사가 있으면 그 아래)로 `upload_file` 한다. 예외를 삼키고 `avantfaxlog("cloud> upload of fax ...")` 만 남기므로 업로드 실패가 수신을 실패시키지 않으며, 재시도 코드는 없다. LOCAL 이면 아무것도 하지 않는다. [코드·시험] `tests/unit/test_remote_upload.py` (`test_s3_receive_uploads_tiff_and_pdf_under_the_fid_key`, `test_an_upload_failure_does_not_fail_the_receive_and_is_logged`, `test_local_storage_uploads_nothing`, `test_provider_prefix_is_applied_to_the_key`)
> 여전히 원문(위키 요약 [[hylafax-integration-architecture]] §9, [[new-features-plan]])과 다른 점: **발신 팩스 업로드(`notify`)는 없다**(`upload_received_fax` 호출자는 `faxrcvd` 하나), `thumb.png` 는 올리지 않는다(TIFF·PDF 만), `download_file` 을 부르는 곳이 없어 로컬에 파일이 없을 때 원격에서 내려받아 보여 주는 기능과 미리 서명된 URL 은 없다. 또 웹·AJAX 삭제(`views/modals.py`, `views/ajax.py`)와 `cron -d`(`prune_archive`)는 로컬 삭제만 하고 원격은 건드리지 않는다. 원격을 지우는 곳은 수명주기(`purge_expired_faxes`)뿐이다. 원문 `docs/NEW_FEATURES_PLAN.md`(삭제됨, `git show 61c3663:docs/NEW_FEATURES_PLAN.md`)(머리말·§8 요약)와 `docs/hylafax_avantfax_integration_architecture.md`(삭제됨, `git show 614f7b0:docs/hylafax_avantfax_integration_architecture.md`) 머리말은 아직 "업로드 코드 없음"으로 적혀 있어 이번 변경과 어긋난다(문서 쪽이 낡음). [코드]

### 수명주기 정책 `StorageLifecyclePolicy`
- [코드] 필드와 기본값: `purge_tiff_after_days=7`(PDF 가 있을 때만 로컬 TIFF 삭제, 0=즉시), `full_retention_days=365`(0=영구 보관), `remote_sync_delete=True`, `delete_remote_tiff_only=False`. (`services/storage_lifecycle.py`)
- [코드] `delete_remote_tiff_only`(원격 TIFF 선별 삭제)는 이제 동작한다. `run_lifecycle` 이 `tiff_only=policy.delete_remote_tiff_only` 로 `purge_expired_faxes` 에 넘기고, 보존 만료 팩스마다 `tiff_only` 이면 `provider.delete_file("fax<fid>/fax.tif")` 만(원격 PDF 는 남음), 아니면 `provider.delete_fax(fid)`(그 팩스의 원격 객체 전부)를 부른다. [코드·시험] `tests/unit/test_remote_upload.py::test_remote_tiff_only_policy`, `test_saved_policy_reads_the_remote_tiff_only_setting`
- [코드] 저장된 정책에서는 설정 키 `storage_remote_tiff_only`(`"1"` 이면 켜짐, 기본 `"0"`)에서 읽는다(`run_saved_policy`). 그러나 **Storage 화면에는 이 값을 바꾸는 입력이 없고** `admin_storage_view` 도 저장하지 않는다(저장하는 키는 `storage_purge_tiff_days`, `storage_retention_days`, `storage_remote_sync_delete` 셋). 즉 현재는 DB 의 `SystemConfig` 를 직접 고쳐야 켜진다. 이 동작은 보존 만료 팩스 삭제 안에서만 일어나며, 원격 TIFF 만 지운 팩스도 로컬에서는 DB 행과 파일이 지워진다.
- [코드] [[hylafax-integration-architecture]] 의 `REMOTE_KEEP_FOREVER` / `REMOTE_SYNC_LIFECYCLE` / `REMOTE_PURGE_TIFF_ONLY` 이름은 설정이나 코드 식별자로 쓰이지 않는다(`src/` 검색: `REMOTE_PURGE_TIFF_ONLY` 는 `storage_lifecycle.py` 95행 주석에만 있음). 원문은 세 이름만 나열하고 뜻을 정의하지 않으므로 이름 사이의 대응은 적지 않는다. 현재 두 설정이 하는 일은 시험이 고정한다: `remote_sync_delete` 가 꺼지면 원격 삭제 호출이 일어나지 않고(`test_storage_lifecycle_orm.py::test_run_lifecycle_purges_tiffs_then_faxes_and_honours_remote_sync`), `delete_remote_tiff_only` 가 켜지면 원격에서 TIFF 만 지운다(`test_remote_upload.py::test_remote_tiff_only_policy`). [코드]
- [코드] `purge_local_tiffs`: 아카이브 폴더를 걸어 `fax.tif` 가 있고 같은 폴더에 **0바이트가 아닌 `fax.pdf`** 가 있으며 TIFF 수정 시각이 N일보다 오래되었을 때만 TIFF 를 지운다. PDF 가 없거나 비어 있으면 건너뛴다(안전장치 두 개). 원격 업로드가 성공했는지는 보지 않으며, 원격에는 손대지 않는다.
- [코드] `purge_expired_faxes(retention_days)`: 보관 시각(`archstamp`)이 기준보다 오래된 팩스의 DB 행과 파일을 지운다. `retention_days <= 0` 이면 아무것도 지우지 않는다. 파일 정리는 **보관 폴더 안**에 있는 경로만 지운다(`_remove_leftovers` 가 `realpath` 로 폴더 밖 경로를 거부). [코드·시험] `tests/unit/test_storage_lifecycle_orm.py::test_files_outside_the_archive_are_never_touched`
- [코드] 원격 삭제 동기화: `remote_sync_delete` 이고 제공자가 있으면 로컬 삭제 전에 `provider.delete_fax(fid)`(또는 위의 TIFF 만 삭제)를 부른다. 예외는 삼킨다("unreachable bucket must not keep local data forever"). 즉 원격 삭제가 실패해도 로컬은 지워지고 원격 객체는 남을 수 있다.
- [코드] `run_saved_policy()`: 호출자가 제공자를 주지 않았으면 `provider_from_config(cfg)` 로 만든다(`S3` 일 때만 제공자가 있고 `LOCAL` 이면 `None`: 원격 복사본 없음). `storage_remote_sync_delete` 기본 `1`. `storage_retention_days` 가 비어 있으면 `full_retention_days=0`(만료 삭제 없음), `storage_purge_tiff_days` 가 비어 있으면 7일로 실행한다.
- 정책 저장 키(화면이 쓰는 것): `storage_purge_tiff_days`, `storage_retention_days`, `storage_remote_sync_delete`. [코드] `views/admin.py::admin_storage_view`

### `/admin/storage` 화면
- [코드] 두 구역: **Storage Lifecycle Policies**(폼 `action=save_lifecycle`)와 **Cloud Storage Backend**(`save_cloud`, `test_cloud`). 라우트 권한은 `permission="admin"` 이고, 뷰가 다시 `identity` 의 `superuser` 또는 `is_superadmin` 이 참인지 보아 아니면 `HTTPForbidden`("Superadmin permission required")을 낸다. `is_admin` 만 있는 일반 관리자는 열 수 없다(2026-10-02 커밋 `26fcf82` 로 바뀜; 이전에는 `is_admin` 도 통과했다). 시험 `tests/unit/test_admin_secret_pages_superuser.py`(GET·POST 403 확인, 읽기만 함). (`views/admin.py::admin_storage_view`)
- [코드] 제공자 선택 드롭다운(`name="storage_type"`, `data-provider-switch="cloud-fields"`)은 **`LOCAL` 과 `S3` 두 개뿐**이다. `static/js/storage.js` 가 선택에 따라 보임/숨김을 바꾼다: `LOCAL` 이면 연결 필드 묶음 `#cloud-fields` 와 "Test Connection" 버튼을 숨기고 안내문 `#cloud-note-LOCAL`("서버의 보관 폴더에 둔다, 연결할 것 없음")을 보이며, `S3` 이면 반대. 새로고침 없이 반응한다.
- [코드] `S3` 필드: 엔드포인트 URL, 리전, 버킷, 접근 키 ID, 비밀 접근 키(`type=password`; 이미 저장돼 있으면 자리표시자만 표시, 빈칸으로 저장하면 기존 비밀 유지), 키 접두사.
- [코드] 비밀 키는 `SystemConfigService.set_secret` 으로 저장(암호화 키 `NAMIFAX_SECRET_KEY` 가 필요하면 `SecretKeyError` 를 화면 오류로 보임). 값은 문서에 쓰지 않는다. [[authentication-and-security]]
- [코드·시험] `tests/unit/test_storage_page_fields.py`: LOCAL/S3 에 따른 필드 보임/숨김, 드롭다운 옵션이 `["LOCAL","S3"]` 인지, 응답에 `GCS` 문자열이 없는지, 폼 필드 이름이 그대로 POST 되는지를 검사한다.
- 주의 [코드]: 저장 시 `storage_type` 값을 검증하지 않고 그대로 `cloud_storage_type` 에 쓴다. 직접 POST 로 `GCS` 같은 값을 넣어도 저장되고, 이후 `get_provider` 는 조용히 로컬로 처리한다. 수명주기의 원격 삭제와 수신 업로드는 `provider_from_config` 가 `S3` 만 제공자로 만들므로(대소문자 무시) 그 밖의 값에서는 원격 동작이 없다.

### GCS 제거와 보류
- [코드] 2026-10-02 에 Storage 화면과 코드에서 GCS 가 제거됐다. 지금 드롭다운에 없고 응답에 `GCS` 문자열이 없다(시험으로 고정됨). `get_provider` 의 `("S3","GCS")` 분기도 `S3` 만 남았다. (`services/cloud_storage.py`, `tests/unit/test_storage_page_fields.py`)
- 보류 사유(실제 GCS 계정으로 시험한 적 없음, 엔드포인트가 비면 AWS 로 접속하는 문제, S3 호환 vs 전용 클라이언트 선택 등)와 다시 넣을 때의 절차는 [[future-gcs-storage]] 에 있다. [문서]
- [코드] 그 문서가 말한 "`StorageLifecycleService` 의 원격 삭제 동기화 두 곳에 `cloud_storage_type in (...)` 가 있다"는 현재 코드에서 **`provider_from_config` 의 `!= "S3"` 검사 한 곳**(수명주기와 수신 업로드가 함께 씀)으로 바뀌었다. 다시 추가할 때는 이 함수와 `CloudStorageManager.get_provider` 를 고치면 된다.

## 7. 한눈에 보는 문서-코드 차이

1. 내장 스케줄러가 "임시 파일 정리만" 한다는 문서([[install-hylafax]])는 낡았다: 코드는 4종(§1).
2. `/admin/maintenance`, 이력 대시보드, `REMOTE_*` 이름의 정책 3종은 코드에 없다(§1, §6). 수신 팩스의 S3 업로드는 이제 있으나 발신·`thumb.png`·원격 다운로드·서명 URL 은 없다(§6).
3. 원격 TIFF 선별 삭제(`delete_remote_tiff_only`)는 동작하지만 Storage 화면에서 켤 방법이 없고 설정 키 `storage_remote_tiff_only` 를 직접 써야 한다(§6).
4. 전화번호부 작업 요약의 개수와 프로세스 간 중복 실행 방지는 이번에 코드가 고쳐졌다(§3).
