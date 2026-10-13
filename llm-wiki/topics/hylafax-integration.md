---
title: HylaFAX 연동
type: topic
updated: 2026-10-03
sources: [deploy/hylafax/, deploy/sudoers.d/namifax, deploy/cron.d/namifax, deploy/postfix/setup-email2fax.md, systemd/, pyproject.toml, src/namifax/main.py, src/namifax/cli/faxrcvd.py, src/namifax/cli/notify.py, src/namifax/cli/dynconf.py, src/namifax/cli/faxcover.py, src/namifax/cli/phb.py, src/namifax/services/sendfax_command.py, src/namifax/views/sendfax.py, src/namifax/services/modem.py, src/namifax/services/faxqueue.py, src/namifax/services/hylafax_users.py, src/namifax/services/hylafax_info.py, src/namifax/services/fax_images.py, src/namifax/services/upload_check.py, src/namifax/services/cloud_storage.py, src/namifax/services/printer.py, src/namifax/services/scheduler.py, src/namifax/cli/print_in.py, src/namifax/cli/cron.py, src/namifax/db/provider.py, src/namifax/common/helpers.py, src/namifax/common/settings.py, src/namifax/views/ajax.py, src/namifax/views/admin_users.py, src/namifax/services/user_account.py, tests/unit/test_business_logic_phase3.py, tests/unit/test_env_file_wiring.py, tests/unit/test_faxqueue.py, docs/ko/install/hylafax.md, docs/hylafax_avantfax_integration_architecture.md, tests/unit/test_sendfax_command.py, tests/unit/test_sendfax_view_commands.py, tests/unit/test_faxrcvd_flow.py, tests/unit/test_modem.py, tests/unit/test_hylafax_user_sync.py, tests/fixtures/legacy_sendfax_commands.json, [[hylafax-integration-architecture]], [[install-hylafax]], [[setup-email2fax]], [[porting-gaps]]]
verified: true
---

# HylaFAX 연동

NamiFAX 와 HylaFAX 의 접점을 코드 기준으로 정리한다. 스케줄러는 [[scheduler-and-storage]], 설치 절차는 [[operations-and-deployment]], 시험 체계는 [[testing]].

## 0. 가장 중요한 한계: 실제 HylaFAX 로 시험한 적이 없다

- [문서] `docs/ko/install/hylafax.md` 첫머리가 "이 저장소에서는 실제 HylaFAX 에 붙여 시험하지 않았다"고 밝힌다. [[install-hylafax]]
- [코드] 시험 모음에는 HylaFAX 데몬(`faxq`, `hfaxd`, `faxgetty`)이나 실제 모뎀을 쓰는 것이 없다. 이 세션에서 `tests/` 의 HylaFAX 관련 시험을 훑은 결과, 아래 방식들로 대신한다(시험을 실행하지는 않았다).

| 대체 검증 | 무엇을 보증하나 | 무엇을 보증하지 못하나 |
|---|---|---|
| **레거시 녹화 비교**: `tests/fixtures/legacy_sendfax_commands.json` 은 원본 PHP `submit_fax()` 를 가짜 `sendfax`/`faxcover` 로 돌려 인자를 녹화한 것. `tests/unit/test_sendfax_command.py` 가 `build_plan` 결과와 비교 | 웹 폼 → `sendfax`/`faxcover` **명령줄 인자**가 원본과 같다(빈 값 옵션과 빈 주소 자리표시자만 의도적으로 뺌) | 진짜 `sendfax` 가 그 인자를 받아들이는지, 큐에 들어가는지 |
| **가짜 실행 파일**: `tests/unit/test_sendfax_view_commands.py` 가 인자를 기록하는 쉘 스크립트를 `PATH` 에 두고 `request id is 80 ...` 를 출력하게 함 | 뷰가 계획대로 프로그램을 부르고 출력에서 작업 번호를 뽑는 흐름 | HylaFAX 의 실제 출력 형식, 권한, 스풀 |
| **mock 으로 외부 의존 대체**: `tests/unit/test_faxrcvd_flow.py` 는 `faxinfo`, `tiff2pdf`, `static_preview`, `send_mail`, `bardecode`, OCR 를 `patch` 하고 가짜 TIFF(`b"mock tiff"`)로 훅을 실행 | 훅 안의 DB 처리(주소록 등록·재사용, 받은 팩스함 입력). 시험 이름 6개 중 DID/모뎀/바코드 라우팅을 보는 것은 없다 | 실제 수신 TIFF 의 처리, `faxrcvd` 가 HylaFAX 에서 호출되는 방식 |
| **문자열 파서 시험**: `tests/unit/test_modem.py`, `tests/unit/test_faxqueue.py` 는 `faxstat` 출력 예시 문자열을 파서에 넣는다 | 예시 출력의 해석 | 실제 `faxstat` 출력과 `JobFmt` 일치 |
| **명령 mock**: `tests/unit/test_hylafax_user_sync.py` 는 `subprocess.run` 을 mock 으로 대체 | `sudo faxadduser/faxdeluser` 인자 구성, 쉘 미사용, 실패해도 계정 변경 유지 | sudoers 규칙이 실제로 통하는지 |

- [코드] 웹의 팩스 보내기(`views/sendfax.py::dispatch_sendfax`)에서 `sendfax` 실행 파일이 없으면(`settings.binary("sendfax")`), **환경변수 `NAMIFAX_QUEUE_SIMULATION` 이 `1`/`true`/`yes` 일 때만**(`_simulation_wanted`) 모의 접수로 성공을 돌려준다(작업 번호는 무작위 6자리, 응답에 `simulated: True`). 그 밖에는 모두(미지정, `0`, 빈 값 포함) `success: False` 와 "HylaFAX (the sendfax program) is not installed or not reachable" 오류를 돌려준다. 이전에는 pytest 실행 중이거나 `/var/spool/hylafax` 가 없으면 자동으로 모의 성공이었으나 커밋 `c59af5e` 에서 제거됐다(AUDIT-07). 시험: `tests/unit/test_business_logic_phase3.py` 의 `test_dispatch_sendfax_simulation_mode`(`=1` 이면 모의)와 `test_dispatch_sendfax_never_fakes_success_unless_simulation_is_explicit`(미지정·빈 값·`0`·`false`·`no` 는 오류). 개발 장비에서 모의가 필요하면 환경 변수를 명시해야 한다.
- 따라서 이 페이지의 "연동한다"는 모두 **명령줄 계약과 파일 형식을 원본에 맞춘 것**이지 실기 검증이 아니다. 실제 서버에서 확인할 점은 [[install-hylafax]] 7단계와 [[operations-checklist]] 에 있다. [문서]

## 1. 이벤트 훅

HylaFAX 가 부르는 실행 파일 4개와 NamiFAX 모듈의 연결. [코드] `deploy/hylafax/`, `pyproject.toml`, `src/namifax/main.py`

| HylaFAX 설정 | 위치 | 쉘 래퍼 | 콘솔 명령(`pyproject.toml`) | 모듈 |
|---|---|---|---|---|
| `FaxRcvdCmd: bin/faxrcvd` | 모뎀 설정(`config.namifax`) | `deploy/hylafax/bin/faxrcvd` | `namifax-faxrcvd` | `cli/faxrcvd.py` |
| `DynamicConfig: bin/dynconf` | 모뎀 설정 | `deploy/hylafax/bin/dynconf` | `namifax-dynconf` | `cli/dynconf.py` |
| `NotifyCmd: bin/notify` | 서버 설정(`etc-faxq.snippet`) | `deploy/hylafax/bin/notify` | `namifax-notify` | `cli/notify.py` |
| `CoverCmd: bin/faxcover` | 서버 설정 | `deploy/hylafax/bin/faxcover` | `namifax-faxcover` | `cli/faxcover.py` |

- [코드] 래퍼 4개는 같은 모양이다: `set -a; [ -r /etc/namifax.env ] && . /etc/namifax.env; set +a` 로 환경 파일을 읽어 **모든 변수를 내보낸 뒤**(커밋 `91dbc4a` 이전에는 `set -a` 가 없어 자식 프로세스에 변수가 전달되지 않았다) `${NAMIFAX_HOME:-/opt/namifax}/.venv/bin/namifax-<이름>` 을 `exec` 한다. 파일이 없어도 그대로 실행한다. `$SPOOL/bin/` 에 복사해 쓴다. 시험: `tests/unit/test_env_file_wiring.py`(가짜 설치로 `DATABASE_URL`/`NAMIFAX_SECRET_KEY` 가 프로그램에 닿는지 읽기만 했고 실행은 하지 않았다). 주의: 파일을 쉘이 `.` 로 읽으므로 값에 `&`, 공백, `;`, `$`, `#` 가 있으면 systemd `EnvironmentFile` 과 해석이 다르다. 이 세션에서 `sh` 로 `DATABASE_URL=...?charset=utf8mb4&x=1` 형태를 읽어 보니 `&` 이후가 별도 명령이 되어 변수가 비었다. 그런 값은 훅/cron 쪽에서 깨질 수 있다.
- [코드] 모뎀 설정에는 `FaxRcvdCmd`, `DynamicConfig`, `UseJobTSI: true` 세 줄이 있다. 서버 설정에는 `NotifyCmd`, `CoverCmd` 두 줄이 있다. `hfaxd.conf.snippet` 의 `JobFmt` 는 아래 4절의 열 순서 때문에 필요하다.
- [코드] 같은 기능이 `namifax faxrcvd|notify|dynconf|faxcover|cron|phb` 서브명령(`main.py`)으로도 있고, 이름은 원본 PHP 스크립트 이름(`faxrcvd.php` 등)을 `argv[0]` 로 맞춰 넘긴다.
- [코드] 모든 훅은 DB 세션을 직접 열고(`cli_session(ensure_schema=True)`) 끝나면 커밋하고 오류면 되돌린다. 훅이 웹 서비스와 **같은 DB** 를 봐야 한다(`/etc/namifax.env` 의 `DATABASE_URL`; 없으면 `db/provider.py::resolve_database_url` 이 현재 폴더의 SQLite `namifax.db` 로 조용히 떨어진다). [[database-and-migrations]]

### 1.1 `faxrcvd` (수신 완료)
- [코드] 인자: `file devID commID error-msg [CIDNumber] [CIDName] [DIDnum]`. 인자가 부족하면(`argv[0]` 포함 3개 미만, 즉 `file`/`devID` 가 없음) 사용법만 출력하고 종료 코드 0. 처리 순서: 모뎀 등록 확인(없으면 자동 생성) → 파일 있는지 → `faxinfo` → 보관 폴더 `<ARCHIVE>/YYYY/MM/DD/<번호>/<HylaFAX ID>/` 만들기 → `fax.tif` 복사 → PDF 변환 → 페이지 이미지·썸네일 → 주소록 조회/등록 → DID 라우팅(`ENABLE_DID_ROUTING`) → 받은 팩스함 입력 → (선택) OCR 색인 → S3 로 설정돼 있으면 `fax.tif`/`fax.pdf` 를 원격에 올림(`cloud_storage.upload_received_fax`, 키 `fax<fid>/fax.tif`·`fax<fid>/fax.pdf`, 실패는 로그만 남기고 수신을 막지 않음, LOCAL 이면 아무 것도 안 함) → 라우팅 우선순위(모뎀/DID → 주소록 Fax2Email → 바코드) → 메일 알림(PDF 첨부 또는 썸네일) → (선택) 프린터 출력. (`cli/faxrcvd.py`)
- [코드] 입력이 이상하면(파일 없음, `faxinfo` 실패, `fax.tif` 복사 실패) 로그만 남기고 종료 코드 0 으로 돌아온다: HylaFAX 쪽에서는 성공처럼 보인다.

### 1.2 `notify` (송신 결과)
- [코드] 인자: `qfile why jobtime [nextTry]`. `qfile` 은 HylaFAX 작업 파일이며 `totpages`, `status`, `external`, `jobid`, `mailaddr`, `groupid`, `owner`, `receiver`, `company`, `regarding` 등과 `postscript|pdf|tiff` 키의 파일 목록을 줄 단위로 읽는다. 작업 파일 형식에 대한 가정이므로 실제 `qfile` 과의 일치는 시험되지 않았다.
- [코드] `why` 에 따라 셋으로 나뉜다: `done`(보낸 팩스함에 `<SENT>/YYYY/MM/DD/<번호>/<HHMMSS>/<jobid>/` 로 PDF 생성·입력, 선택적으로 성공 메일), `blocked`/`requeued`(재시도 알림 메일), 그 밖(실패: PDF 를 만들어 실패 메일에 첨부). 보낸 사람은 `owner` 가 `FAXMAILUSER`/`WWWUSER` 이면 `mailaddr` 로 사용자를 찾고, 아니면 `owner` 이름으로 찾는다. 이것이 메일→팩스 사용자 식별의 기초다(§5).

### 1.3 `dynconf` (착신 거부)
- [코드] `dynconf device CallID1 ...` → SIP 접미사(`@host`)를 떼고 `DynamicConfig.lookup(device, callid)` 가 참이면 `RejectCall: true` 를 출력한다. 거부 대상이 아니면 아무것도 출력하지 않는다(설치 확인에 이 성질을 쓴다). `device` 만 있거나 CallID1 이 빈 문자열이면 `EMPTY CALLID` 로 조회한다. 조회에는 첫 CallID(`argv[2]`)만 쓰고 나머지 CallID 인자는 읽지 않는다. `device` 도 없으면 사용법만 출력한다.

### 1.4 `faxcover` (표지)
- [코드] 명령줄 옵션을 읽어 사용자 계정 정보를 풀고 PS 또는 HTML 표지 템플릿의 자리표시자를 치환해 표준 출력으로 내보낸다(`cli/faxcover.py`; 모듈 docstring 은 EPS 도 말하지만 코드는 `.ps`/`.html`/`.htm` 확장자만 구분한다. HTML 은 `USE_HTML_COVERPAGE` 가 켜졌을 때만이고 `html2ps` 로 PS 로 바꾼다). `-f`(보내는 사람)와 `-n`(받는 번호)가 없으면 사용법만 출력한다. HylaFAX 의 `CoverCmd` 가 이를 호출한다. 웹 폼 쪽은 표지만 보낼 때 `faxcover` 를 직접 불러 PS 를 만들고 그것을 `sendfax` 로 보낸다(§2).

## 2. 팩스 송신 계획 (`sendfax` 명령 구성)

- [코드] `services/sendfax_command.py::build_plan(request, sender, images_dir, tmp_dir, default_tsi)` 는 **무엇을 실행할지만 결정**한다(HylaFAX 불필요, 파일을 건드리지 않음). 결과 `Plan` = `steps`(실행할 `argv` 목록과 `stdout_to`), `files_to_write`, `cleanup`.
- [코드] 규칙 요약:
  - 파일도 표지도 없으면 `NothingToSend`.
  - 옵션 이름은 원본과 같다: `-o` 소유자, `-f` 보낸 메일, `-x` 받는 회사, `-c` 주석, `-r` 용건, `-y/-V` 받는 장소/전화, `-X/-Y/-U/-W` 보내는 회사/장소/전화/팩스, `-t` 재시도 횟수, `-k now + N <단위>`, `-S` TSI, `-P` 우선순위, `-a HH:MM` 예약. 값이 비면 옵션을 아예 뺀다.
  - 알림: 재큐 알림이면 `-R`, 아니면 `-D`. 표지: 있으면 `-C <images_dir>/<표지>`, 없으면 `-n`.
  - 모뎀: `-h <장치>@localhost`(`any` 이거나 비면 생략).
  - 수신처: 하나면 `-d [받는사람@]번호`; 세미콜론으로 여럿이면 문자 정화 후 임시 파일을 만들어 `-z <파일>`.
  - 표지 주소(주소·우편번호·도시)는 주석에 `{to-address:'..'}` 꼴로 실어 `faxcover` 가 다시 읽는다. `!` 는 `&#33;` 으로 바꾼다.
  - 파일 없이 표지만이면 `faxcover ... -p 0 -n <첫 번호>` 의 출력을 임시 `.ps` 로 저장하고 그것을 `sendfax -n` 으로 보낸다(`cleanup` 에 임시 파일).
- [코드] 인자는 **리스트**로 만들어 쉘을 거치지 않는다(폼 입력이 쉘 문법으로 해석되지 않음).
- [코드] 실행(`views/sendfax.py::dispatch_sendfax`): `sendfax` 는 `settings.binary("sendfax")` 로 찾고(`SENDFAX` 환경변수 → `BINARYDIR` → `PATH`), `faxcover` 는 `NAMIFAX_FAXCOVER` 가 있으면 그것, 없으면 `python -m namifax.cli.faxcover`. 하나라도 종료 코드가 0 이 아니면 출력 내용을 오류로 보여 주고, 성공이면 출력에서 `request id is <숫자>` 를 뽑아 작업 번호로 쓴다. 이 정규식은 HylaFAX 의 실제 출력에 대한 가정이다.
- [코드] 권한 규칙: 우선순위와 TSI 는 슈퍼유저만 바꿀 수 있다. 선(line) 선택은 사용자의 권한 목록과 `any_modem` 권한에 따른다. 업로드는 `upload_check` 로 크기·형식을 점검하고 임시 파일에 저장한 뒤 발송이 끝나면 지운다.
- [코드] 업로드 형식(`services/upload_check.py::kind`)은 파일 이름이 아니라 첫 4096바이트로 PDF(`%PDF`), PostScript(`%!`), TIFF, 텍스트(NUL 없고 UTF-8)만 받고 나머지는 "File type is unauthorized"로 거절한다. 크기 한도는 `NAMIFAX_MAX_UPLOAD_BYTES`(기본 10 MiB). 이미지(PNG/JPEG)나 오피스 문서를 PDF 로 바꾸는 코드는 `src/` 에 없다(`libreoffice`/`soffice` 검색 결과 없음).
- [문서] [[hylafax-integration-architecture]] §10.2 는 이미지가 Pillow 나 HylaFAX 룰셋으로 "자동 래핑"된다고, §10.3 은 오피스 문서를 클라이언트에서 PDF 로 바꾸거나 서버에 LibreOffice Headless 를 붙이는 것을 **권장 운영 정책**으로 적는다. 위 코드와 보면 이미지는 업로드 단계에서 거절되므로 §10.2 의 "자동 래핑"은 현재 동작이 아니다. 아직 해결되지 않은 문서-코드 차이.

## 3. 수신 처리: TIFF→PDF, 썸네일, Ghostscript

- [코드] **TIFF→PDF**(`common/helpers.py::tiff2pdf`): 먼저 LibTIFF 의 `tiff2pdf -o` 를 10초 제한으로 시도하고, 실패하거나 없으면 Pillow 로 모든 쪽을 PDF 한 개로 저장한다(모드 `1`/`L`/`RGB` 는 그대로, 그 밖은 RGB 로 바꿈). 해상도가 없으면 204x196dpi 로 가정하고, 가로세로 해상도가 10% 넘게 다르면 세로를 늘려 픽셀을 정사각형으로 만든다. 그래서 **수신 PDF 는 Ghostscript 없이도 만들어진다.**
- [코드] **썸네일/쪽 이미지**(`services/fax_images.py::render_previews`): `fax.tif` 가 있으면 Pillow 로 쪽마다 `page<N>.png`(폭 `PREV_SP`, 기본 750)와 첫 쪽의 `thumb.png`(폭 `PREV_TN`, 기본 80)를 만든다. 이것도 Ghostscript 가 필요 없다.
- [코드] **Ghostscript 가 필요한 곳**은 아래뿐이다. `settings.binary("gs")` 로 찾는다.
  1. 보낸 팩스처럼 **TIFF 가 없고 PDF 만 있는 폴더**의 쪽 이미지/썸네일(`render_pdf_previews`, `-sDEVICE=pnggray`). `gs` 가 없으면 0쪽을 돌려주고 미리보기가 없다.
  2. 송신 실패/완료 PDF 를 만들 때 **PostScript 입력**을 PDF 로 바꾸는 `convert2pdf`(`-sDEVICE=pdfwrite`). `gs` 가 없으면 `False` 를 돌려주고 notify 는 "PDF 만들기 실패" 메일로 갈음한다.
- [코드] 보관 폴더 구성: `fax.tif`, `fax.pdf`, `thumb.png`, `page0.png`...`page<N-1>.png`.

> 모순: 해결됨(커밋 `91dbc4a`): 저장소 문서는 이제 `page0.png ... page(N-1).png` 로 적는다. 위키 요약 [[hylafax-integration-architecture]] §5 만 `preview0.png ... preview(N-1).png` 로 남아 있다. 코드의 이름은 `page<N>.png` 다(`fax_images.PREVIMG = "page"`).

- [코드] 선택 기능: 바코드 해독(`bardecode`, 외부 도구 의존), OCR(`ocr_faxcontent` 와 `OcrService`, `settings.ocr_enabled()`), 팩스 번호 주석(`ENABLE_FAX_ANNOTATION`), G4 재압축(`TIFF_TO_G4`)은 설정으로 켠다. 이 세션에서 각 외부 도구의 설치 필요 조건은 `settings.binary()` 호출 지점만 확인했다.
- [코드·시험] `tests/unit/test_tiff2pdf_fallback.py`, `test_convert2pdf_*.py`, `test_archive_preview.py` 가 변환·미리보기를 검사한다. 시험에서는 `faxrcvd` 의 해당 단계가 `patch` 로 대체되므로 진짜 수신 TIFF 의 end-to-end 는 시험된 적이 없다.

## 4. 모뎀 상태와 대기열

- [코드] **모뎀 상태**(`services/modem.py`): `faxstat` 실행(5초 제한)의 출력을 `parse_faxstat_output` 이 장치별로 해석한다. 줄 첫 두 글자로 `Ru`(Running and idle → `modem-free`), `Se`(Sending job N → `modem-send`), `Re`(Receiving ... → `modem-recv`), 그 밖(`modem-wait`)을 나눈다. 명령이 실패하면 빈 결과가 되어 "Please wait" 로 표시한다. 화면 갱신은 `/ajax/modemstatus` 가 맡는다(`views/ajax.py`).
- [코드] **대기열**(`services/faxqueue.py`): 발송 대기 `faxstat -s`, 완료 `faxstat -d`(실패만 `s == "F"`), 취소는 `faxrm`, 변경은 `faxalter`. 출력 열은 발송 대기 `SENDQ_KEYS = jid pri s owner mailaddr number pages dials tts status`, 완료 `DONEQ_KEYS = jid pri s owner mailaddr number pages dials status`(`tts` 없음) 순서로 **공백 단위 토큰** 해석을 하며 마지막 열(status)은 남은 토큰을 이어 붙인다. `JobFmt` 는 두 큐에 같은 10열을 내므로 완료 큐에서는 시각 토큰이 `status` 앞에 붙어 들어올 수 있다[문서: `hfaxd(8)` 는 `JobFmt` 를 "sendq 와 doneq 의 작업 상태를 돌려줄 때 쓰는 형식 문자열"로 설명한다(manpages.debian.org, 2026-10-03 조회)]. 동봉한 `JobFmt` 의 `%z` 열이 완료 작업에서 값을 내는지는 실제 `hfaxd` 출력이 있어야 알 수 있어 확인하지 못했다(시험은 가짜 출력만 쓴다). 그래서 `deploy/hylafax/hfaxd.conf.snippet` 의 `JobFmt` 로 열 구성을 고정해야 한다. 다르면 목록이 어긋난다. [코드] 시험은 예시 문자열만 쓴다(§0).
- [코드] 관리자 대시보드의 HylaFAX 버전은 `faxstat -i` 출력에서 정규식으로 뽑는다(`services/hylafax_info.py`). 못 구하면 `None`(값을 지어내지 않는다).
- [코드] `FaxQueue.shell_exec` 은 이름과 달리 **쉘을 쓰지 않는다**. 명령 문자열을 `shlex.split` 해 인자 리스트로 `subprocess.run` 하고, 실행 불가·빈 명령·구문 오류는 빈 문자열을 돌려준다(커밋 `c59af5e` 이전에는 `shell=True` 였고 오류 문자열을 출력으로 돌려줬다). 명령은 생성자 기본값 `faxstat -s`/`faxstat -d`. `killjob` 은 `faxrm <jid>` 를 환경 변수 `FAXUSER` 와 함께, `faxalter` 는 인자 리스트로 실행한다.

> 모순: 저장소 문서는 해결됨(커밋 `91dbc4a`, 2026-10-02 확인: `docs/hylafax_avantfax_integration_architecture.md`(삭제됨, `git show 614f7b0:docs/hylafax_avantfax_integration_architecture.md`) 첫머리가 "TCP 4559 에 접속하지 않고 `faxstat` 을 실행"으로 바로잡음). 위키 요약 [[hylafax-integration-architecture]] 만 아직 "실시간 모뎀 상태 조회(`faxstat` + TCP 4559)"라고 적는다. 코드에서 TCP 4559(`hfaxd` 포트) 소켓 접속은 찾지 못했다(`src/` 에서 `4559` 검색 결과 없음). 모뎀 상태와 대기열 모두 **`faxstat` 외부 프로세스 실행**으로만 구한다.

## 5. 메일 → 팩스 (Postfix)

- [문서] `deploy/postfix/setup-email2fax.md` ([[setup-email2fax]]): `fax.example.com` 도메인 메일을 Postfix `pipe` 서비스(`user=faxmail argv=/usr/bin/faxmail -d -n -NT ${user}`)로 HylaFAX `faxmail` 에 넘기고, `transport_maps` 로 도메인을 연결하고, `faxmail.conf` 를 설정한다. 이 저장소는 시스템 파일을 직접 고치지 않는 **설명서**일 뿐이며 자동 적용 스크립트가 없다. [코드] `deploy/postfix/` 에는 이 문서만 있다.
- [코드] NamiFAX 가 맡는 부분은 **소유자 식별**이다. `faxmail` 로 접수된 작업의 소유자는 `FAXMAILUSER`(기본 `faxmail`)이며, 대기열 표시와 `notify` 는 소유자가 `FAXMAILUSER` 또는 `WWWUSER`(기본 `www-data`)일 때 작업의 `mailaddr` 로 사용자를 찾아 그 사람의 팩스로 보여 준다. (`services/faxqueue.py::get_queue/list_owner`, `cli/notify.py`) `FAXMAILUSER` 를 Postfix 의 `user=` 와 같게 맞춰야 한다. [문서]
- 한계: 메일 수신 쪽(Postfix → `faxmail` → `sendfax`)은 NamiFAX 코드가 아니라 HylaFAX 의 `faxmail` 이며 이 저장소에서 시험된 적이 없다. [코드] NamiFAX 시험은 소유자 매핑 로직만 본다.

## 6. HylaFAX 사용자 동기화

- [코드] `HYLAFAX_USER_SYNC=1` 일 때만 켜지는 선택 기능(기본 꺼짐). 계정을 만들면 `sudo <PREFIX>/sbin/faxadduser -u <uid> -p <비밀번호> <이름>`, 지우면 `faxdeluser <이름>`, 비밀번호 변경은 삭제 후 재생성이다(HylaFAX 가 제자리 변경을 못 하기 때문). 쉘 없이 인자 리스트로 실행하고(`SUDO` 환경 변수로 sudo 명령을 바꿀 수 있고 기본 `sudo`, 프로그램 위치는 `<HYLAFAX_PREFIX 기본 /usr>/sbin/`) 실패(프로그램 없음 포함)는 `False` 를 돌려줄 뿐 호출자가 무시하므로 계정 변경을 막지 않는다. 모듈 docstring 은 "실패를 기록한다"고 하지만 이 파일에 로그 호출은 없다. (`services/hylafax_users.py`, 호출: `services/user_account.py`, `views/admin_users.py`)
- [코드] `deploy/sudoers.d/namifax`: 서비스 사용자(`uucp`)가 비밀번호 없이 실행할 수 있는 것은 `/sbin/reboot`, `/sbin/halt`(관리자 > 시스템 기능), `faxdeluser *`, `faxadduser -u * -p * *` 뿐이다.
- [문서] [[install-hylafax]]: `faxadduser` 가 비밀번호를 **명령줄 인자**로 받아 같은 서버의 다른 사용자가 `ps` 로 볼 수 있으므로 다른 사용자가 없는 전용 장비에서만 켠다. `systemd/namifax.service` 의 `NoNewPrivileges=true` 는 `sudo` 를 막으므로 이 기능에는 `false` 로 바꿔야 한다. [코드] 현재 서비스 파일 둘 다 `NoNewPrivileges=true` 이다(`docs/ko/install/hylafax.md` 3단계도 같은 안내).

> 모순: 해결됨(커밋 `91dbc4a`). `docs/ko/install/hylafax.md` 는 이제 서비스 파일을 최상위 `systemd/`(`namifax.service`)로 안내하고 "`deploy/` 아래가 아닙니다"라고 적는다(2026-10-02 `grep` 확인). 다만 `llm-wiki/sources/install-hylafax.md` 요약은 옛 문서 기준이라 아직 `deploy/systemd/` 로 적혀 있다(요약 페이지는 이 페이지의 수정 범위 밖). `deploy/sudoers.d/namifax` 주석에도 "deploy/systemd" 라는 옛 표현이 남아 있다.

## 7. 주기 작업 배선

- [코드] 전화번호부 내보내기는 스케줄러의 `phonebook` 작업이 `cli/phb.py::export_phonebook_count()` 로 하며(실제 쓴 항목 수, 즉 회사 수를 요약 "phonebook exported (N entries)" 에 넣는다. 이전에는 종료 코드 0 을 항목 수처럼 썼다) 기본 경로는 `<HYLASPOOL>/etc/phonebook`(`PHONEBOOK` 설정으로 변경). HylaFAX 클라이언트 전화번호부 형식 `PBOOK1.1` 을 쓴다. 예약 실행은 다른 프로세스(같은 DB 를 쓰는 다른 웹 서비스의 스케줄러)의 6시간 미만 실행 표식이 있으면 "already running" 으로 건너뛴다(`scheduler_config.running_marker`, `scheduler._run_claimed`). 상세와 한계는 [[scheduler-and-storage]].
- [코드] 정리 작업(임시 폴더, 받은 팩스함 보관, 수명주기)의 배선은 두 갈래다. (1) 스케줄러: 웹 내장(`systemd/namifax.service` 의 `NAMIFAX_ENABLE_SCHEDULER=1`; 별도 스케줄러 서비스는 2026-10-03 에 제거). (2) OS cron: `deploy/cron.d/namifax`(`namifax cron -t/-i/-d/-p/-s`; 기본으로 켜진 줄은 `-t 2` 하나). cron 줄은 모두 `sh -c 'set -a; [ -r /etc/namifax.env ] && . /etc/namifax.env; set +a; exec /opt/namifax/.venv/bin/namifax cron ...'` 꼴이다.
- [코드] 두 서비스 모두 `User=uucp`, `ProtectSystem=full`, `ProtectHome=true`, `NoNewPrivileges=true`, `Restart=always`, `After=hylafax.service`(그리고 `mariadb.service`/`mysql.service`)이며 `EnvironmentFile=-/etc/namifax.env`(앞의 `-` 는 파일이 없어도 시작)를 가진다. 이전 판의 추정(서비스가 환경 파일을 받는지 모름)은 커밋 `91dbc4a` 로 해소됐고 `tests/unit/test_env_file_wiring.py` 가 두 서비스 파일의 해당 줄을 본다. 보관·임시 폴더는 훅을 실행하는 사용자와 웹 서비스 사용자가 모두 쓸 수 있어야 한다. `ProtectSystem=full` 은 `/usr`, `/boot`, `/etc` 를 읽기 전용으로 만들 뿐이므로 `/var/spool/hylafax` 쓰기는 막지 않는다 [코드, 측정 2026-10-03: systemd 259 의 임시 서비스에 루트로 `-p ProtectSystem=full` 을 주면 `/etc`, `/usr`, `/boot` 는 읽기 전용이 되고 `/var/spool`, `/var/lib` 는 쓰기 가능했다. 옵션이 없는 대조군에서는 다섯 곳 모두 쓰기 가능].

## 8. 그 밖의 접점

- [코드] 설정 위치 변수: `HYLASPOOL`(기본 `/var/spool/hylafax`), `HYLAFAX_PREFIX`(기본 `/usr`), `BINARYDIR`, 프로그램별 변수(`GS`, `FAXINFO`, `SENDFAX`...), `AVANTFAX_ARCHIVE`(기본 `<HYLASPOOL>/archive`), `ARCHIVE_SENT`(기본 `<HYLASPOOL>/sent`), `PHONEBOOK`(기본 `<HYLASPOOL>/etc/phonebook`), `AVANTFAX_TMPDIR`(`notify` 의 임시 폴더, 기본 `/tmp/avantfax/`). 클라우드 보존 정책과 로컬 저장소 제공자는 이와 별개로 `NAMIFAX_ARCHIVE_DIR` 를 본다. 두 값이 다르면 수신 보관 폴더와 보존 정책의 대상 폴더가 갈라진다([[operations-and-deployment]] 2.1). `common/settings.py`
- [코드] 가상 프린터(CUPS → 팩스)는 `cli/print_in.py`(표준 입력의 인쇄 데이터를 받음)와 `services/printer.py` 에 있다. `process_inbound_print_job` 은 `[[FAX: 번호]]` 태그가 있으면 `<NAMIFAX_TMPDIR 또는 시스템 임시 폴더>/namifax_spool/printjob_*.ps|pdf|prn` 으로 저장한 뒤 `_dispatch_print_job` 으로 `views/sendfax.py::dispatch_sendfax`(발송 화면과 같은 경로)에 넘긴다. 사용자 계정이 있으면(`db` 를 받았을 때 `NFUserAccount.load_username`) 그 이름·회사·팩스 번호로 발신자를 채운다. 성공하면 `dispatched: True, status: QUEUED`, `job_id` 는 sendfax 의 jobid 이고 스풀 파일은 지운다. 실패하면 `dispatched: False, status: FAILED` 와 `message`("The fax to ... could not be queued: ...")를 돌려주고 파일은 남는다(예외는 삼켜 결과로 돌려줌). 태그가 없으면 `namifax_drafts/` 에 저장만 한다. CLI `print_in` 은 `cli_session()` 으로 DB 를 열어 넘기고, 실패(`FAILED`)이면 종료 코드 1, 성공이나 초안 저장이면 0 이다(2026-10-02 커밋 `26fcf82` 로 바뀜; 이전에는 파일만 저장하고 `QUEUED` 를 돌려줬다). 시험 `tests/unit/test_network_printer.py`, `tests/unit/test_cli_print_in.py`(읽기만 함). 진입점은 `namifax print-in`(`src/namifax/main.py` 의 명령 분기, 커밋 `88bb5d8`)과 CUPS 백엔드 스크립트 `deploy/cups/namifax-fax`(환경 파일을 읽고 `namifax print-in "$@"` 로 `exec`, 인자 없이 부르면 CUPS 가 요구하는 장치 목록 한 줄을 출력)다. 근거 시험 `tests/unit/test_print_in_wiring.py`. **실제 CUPS 에 등록해 시험한 적은 없다**(스크립트의 인자 전달과 명령 분기만 시험됨). 설치 절차는 `docs/ko/install/hylafax.md` 5-1.
- 레거시와의 차이와 알려진 결함은 [[porting-gaps]], [[migration-from-avantfax]], [[known-gaps-and-decisions]] 를 본다.

## 9. 문서-코드 차이 요약

1. TCP 4559 로 모뎀 상태를 읽는다는 설명은 코드에 없다. `faxstat` 프로세스 실행뿐(§4). `docs/hylafax_avantfax_integration_architecture.md`(삭제됨, `git show 614f7b0:docs/hylafax_avantfax_integration_architecture.md`) 는 `91dbc4a` 이후 이 점을 바로잡았다(위키 `sources/` 요약은 옛 서술 그대로).
2. 쪽 이미지 이름은 `preview<N>.png` 가 아니라 `page<N>.png`(§3). 저장소 문서(`docs/hylafax_avantfax_integration_architecture.md`(삭제됨, `git show 614f7b0:docs/hylafax_avantfax_integration_architecture.md`))는 정정됐다.
3. 서비스 파일 위치는 `deploy/systemd/` 가 아니라 `systemd/`(§6). 해결됨(`91dbc4a`).
4. 이미지 업로드 "자동 래핑"(§2)은 코드에 없다. 가상 프린터의 `sendfax` 연결(§8)은 `26fcf82` 로, 진입점 `namifax print-in` 과 CUPS 백엔드 스크립트는 `88bb5d8` 로 생겼다(실제 CUPS 시험은 없음).
