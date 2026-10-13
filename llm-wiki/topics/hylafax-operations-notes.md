---
title: HylaFAX 운영 메모 (스풀 이동, 수신 파일, 첨부 형식, print-to-fax)
type: topic
updated: 2026-10-03
sources: [src/namifax/common/settings.py, src/namifax/cli/faxrcvd.py, src/namifax/services/fax_images.py, src/namifax/services/archive_base.py, src/namifax/services/cloud_storage.py, src/namifax/common/helpers.py, src/namifax/services/upload_check.py, src/namifax/services/sendfax_command.py, src/namifax/views/sendfax.py, src/namifax/templates/sendfax.jinja2, src/namifax/cli/print_in.py, src/namifax/services/printer.py, src/namifax/main.py, deploy/cups/namifax-fax, docs/ko/install/hylafax.md, "git show 로 읽을 수 있는 원본: docs/hylafax_avantfax_integration_architecture.md (삭제됨; git show 614f7b0:docs/hylafax_avantfax_integration_architecture.md)", [[hylafax-integration]], [[scheduler-and-storage]]]
verified: true
---

# HylaFAX 운영 메모

설계 문서(원문)에만 있고 위키에 없던 운영 지식을 모았다. 훅·`sendfax` 인자·스케줄러·S3 는 중복하지 않고 [[hylafax-integration]] 과 [[scheduler-and-storage]] 로 보낸다. 표기: `[코드]` 는 이 세션에서 `src/` 를 읽어 확인, `[문서]` 는 원문에만 있고 코드로 확인하지 못함(원문은 `git show` 로 읽는다). 시험은 실행하지 않았다.

## 1. 수신 스풀(`recvq`)을 큰 디스크로 옮기기 (원문 3장)

### 1.1 HylaFAX 쪽 (스풀 레벨)
- [문서] `/var/spool/hylafax/recvq` 는 HylaFAX 가 통화 중 수신 TIFF 를 쓰는 **임시 버퍼**다. 데몬 설정으로 하위 폴더 이름을 바꾸지 않고(권장되지 않는다고 함), **OS 수준에서 물리 저장소만 바꾼다**.
- [문서] 방법 1, 심볼릭 링크. 서비스를 멈춘 뒤 옮기고 링크를 건다.
  ```
  service hylafax stop
  mv /var/spool/hylafax/recvq /data/storage/fax_recvq
  ln -s /data/storage/fax_recvq /var/spool/hylafax/recvq
  chown -R uucp:uucp /data/storage/fax_recvq
  service hylafax start
  ```
- [문서] 방법 2, 바인드 마운트(원문은 "가장 안정적"이라 함). `/etc/fstab` 에 한 줄을 둔다.
  ```
  /data/storage/fax_recvq   /var/spool/hylafax/recvq   none   bind   0 0
  ```
  대용량 NVMe/SAN/NFS 마운트 지점을 쓸 수 있다.
- 주의(원문이 직접 말하는 것 + 위 절차에서 읽히는 것):
  - [문서] 이동 중에는 반드시 HylaFAX 를 멈춘다(수신 중 파일을 옮기지 않는다). 링크·마운트 뒤 소유자를 `uucp` 로 맞춘다.
  - [코드] NamiFAX 는 `recvq` 경로를 직접 읽지 않는다. 훅이 인자로 받은 TIFF 경로(`argv[1]`)를 쓸 뿐이다(`cli/faxrcvd.py`). 그래서 링크나 마운트로 옮겨도 NamiFAX 설정은 바꿀 필요가 없다. 스풀 루트는 `HYLASPOOL`(기본 `/var/spool/hylafax`)이고 훅 폴더·전화번호부·기본 보관 폴더가 여기서 파생된다(`common/settings.py::hylaspool`).

### 1.2 NamiFAX 쪽 (최종 보관 경로는 자유롭게)
- [코드] `faxrcvd` 는 수신 TIFF 를 **복사**해(`shutil.copy2`, `common/helpers.py::copy_tiff`) 보관 폴더에 둔다. 원본을 지우는 코드는 `cli/faxrcvd.py` 에 없다. 사용자가 보는 팩스는 모두 보관 폴더의 사본이다.
- [코드] 보관 폴더는 환경변수 **`AVANTFAX_ARCHIVE`** 로 정하고 기본값은 `<HYLASPOOL>/archive` 다(`common/settings.py::archive_dir`). 보낸 팩스 폴더는 `ARCHIVE_SENT`(기본 `<HYLASPOOL>/sent`)다. 값은 `/etc/namifax.env` 에 넣는다([[install-hylafax]]).
- [코드] 클라우드 보존 정책과 `LocalStorageProvider` 는 이와 별개로 **`NAMIFAX_ARCHIVE_DIR`**(기본 `/var/spool/hylafax/archive`)를 읽는다(`services/cloud_storage.py`). 수신 폴더를 옮기면 **두 변수를 같은 값으로** 맞춰야 한다. 자세한 영향은 [[operations-and-deployment]] 2.1.
- [코드] 폴더는 훅을 실행하는 사용자(`uucp`)와 웹 서비스 사용자가 모두 쓸 수 있어야 한다(`docs/ko/install/hylafax.md` 6절).

> 모순: 원문 3.2 는 `local_config.php` 의 `$ARCHIVE` 에 대응하는 NamiFAX 설정이 `production.ini` 의 `namifax.archive_dir` 라고 적는다. 코드에서 이 ini 키를 읽는 곳은 없다(`src/`, `deploy/` 검색 결과 없음). 설정 이름은 환경변수 `AVANTFAX_ARCHIVE` 다(위). 원문은 `faxes/` 라는 상위 폴더도 가정하지만 코드에는 없다(2절).

## 2. 팩스 한 통을 받을 때 생기는 파일 (원문 4.2, 5장)

### 2.1 HylaFAX 단계
- [문서] 한 통화로 온 팩스는 쪽수가 1이든 100이든 `recvq` 에 **멀티페이지 TIFF 한 개**(`fax<번호>.tif`, 예 `fax00000042.tif`)로 생긴다. T.30/G3·G4 압축이고 한 파일 안에 쪽마다 프레임(IFD)이 이어진다.
- [문서] 수신이 끝나면(회선을 끊고 파일을 닫은 뒤에만) `FaxRcvdCmd` 훅이 실행된다. 인자·래퍼는 [[hylafax-integration]] 1.1. 이 때문에 훅이 돌았다는 것이 곧 "수신 완료"의 증거다.
- [문서] **`faxqclean`**: HylaFAX 의 정리 프로그램. 설명서(manpages.debian.org `faxqclean(8)`, 2026-10-03 조회)는 `doneq` 의 끝난 작업을 처리하고(`-j`, 기본 15분) `docq` 에서 어떤 작업도 참조하지 않는 문서 파일을 지운다고(`-d`, 기본 1시간) 한다. `recvq` 와 `tmp` 는 `faxqclean` 이 아니라 `faxcron` 이 정리한다(`faxcron(8)`: 받은 팩스 `recvq` 7일, `tmp` 1일, 원격 장치 정보와 세션 로그 30일 이상을 삭제하고 옵션은 `-rcv`, `-tmp`, `-info`, `-log`). 원문의 "30일 단위" 는 `faxcron` 의 info·log 기본값과 같은 숫자이지만 원문이 어느 프로그램을 가리키는지는 원문만으로 알 수 없다. 설치된 HylaFAX 버전의 설명서와 다를 수 있다.
- [코드] NamiFAX 의 `src/`·`deploy/` 에는 `faxqclean`, `recvq` 라는 문자열이 없다. 즉 `recvq` 의 원본은 NamiFAX 가 지우지 않고, 지우는 일은 전적으로 HylaFAX 쪽 정리(`faxqclean` 등)에 맡겨져 있다. 보관 폴더의 정리는 별개로 NamiFAX 스케줄러가 한다([[scheduler-and-storage]]).

### 2.2 NamiFAX 아카이브 단계 (`faxrcvd`)
- [코드] 폴더: `<보관 폴더>/YYYY/MM/DD/<정리된 발신번호>/<HylaFAX ID>/`(`cli/faxrcvd.py::_process_faxrcvd`).
  - 날짜는 `faxinfo` 가 알려 준 **수신 시각**을 쓴다(`YYYY:MM:DD HH:MM:SS` 의 날짜 부분의 `:` 를 `/` 로 바꿈).
  - 발신번호는 `+` 와 숫자만 남기고(`clean_faxnum`) `+` 를 뺀 것이며, 비면 `unknown`.
  - HylaFAX ID 는 `os.path.basename(tiff)` 에서 `fax` 와 `.tif` 를 지운 것이다. 즉 `fax00000042.tif` 이면 `00000042` 이고 **앞의 0 이 그대로 남는다**.
- [코드] 파일을 만드는 순서(`faxrcvd.py`, `fax_images.py`):

| 순서 | 파일 | 만드는 곳 | 비고 |
|---|---|---|---|
| 1 | `fax.tif` | `copy_tiff` | 기본은 원본 그대로 복사. `TIFF_TO_G4` 가 켜지면 CCITT G4 로 다시 압축해 저장 |
| 2 | `fax.pdf` | `tiff2pdf` | LibTIFF `tiff2pdf` 를 먼저 시도, 실패하면 Pillow(상세는 [[hylafax-integration]] 3절) |
| 3 | `page0.png` ... `page<N-1>.png` | `static_preview` → `render_previews` | 쪽마다 한 장. 번호는 **0 부터**. 회색조, 폭 `PREV_SP`(기본 750) |
| 4 | `thumb.png` | 같은 함수 | 첫 쪽 하나만(`page0` 을 쓸 때 같이 만듦). 폭 `PREV_TN`(기본 80), 높이는 비율대로 |

  그 다음에야 DB 의 받은 팩스함 입력(`ArchiveIn.create`)이 이어진다. 선택 기능으로 `ENABLE_FAX_ANNOTATION` 이 켜지면 입력 직후 `fax.pdf` 를 다시 써서 팩스 ID 를 쪽마다 넣고, OCR 색인과 S3 업로드(`fax.tif`·`fax.pdf` 만)가 이어진다([[scheduler-and-storage]] 6절).
- [코드] 쪽 이미지 이름은 `fax_images.PREVIMG = "page"`, 접미사 `.png`, 썸네일 이름 `thumb.png`, `archive_base.py` 에 같은 상수가 있다. 삭제할 때도 같은 이름 규칙으로 지운다(`archive_base.py::delete_fax`).
- [코드] `faxinfo` 가 실패하거나(깨진 파일) TIFF 복사가 실패하면 폴더 안에 아무것도 입력하지 않고 종료 코드 0 으로 끝난다([[hylafax-integration]] 1.1).

### 2.3 쪽수에 따른 파일 수
- [코드] 파일 수는 **3 + N** 이다(`fax.tif`, `fax.pdf`, `thumb.png` 와 쪽 이미지 N 장). N 은 `fax.tif` 의 프레임 수(`n_frames`)다(`render_previews`). 예: 1쪽 4개, 5쪽 8개, 30쪽 33개, 100쪽 103개. 계산식은 원문 5.3 의 표와 같다.
- [문서] 원문 6.1 은 하루 수백 통이면 쪽 PNG 때문에 inode 와 메타데이터 검색이 느려지고, TIFF·PDF·PNG 가 중복 저장돼 용량이 늘어난다고 지적한다. 코드로 측정한 수치는 없다. 대응으로 로컬 TIFF 정리와 S3 보관이 있다(수신 업로드와 `PRUNE` 류 정책의 현재 상태는 [[scheduler-and-storage]] 6절).

> 모순: 원문 5.2 는 폴더가 `faxes/YYYY/MM/DD/<발신번호>/<FaxID>/`(예 `.../42/`)이고 썸네일이 160x220 이라 적는다. 코드에는 `faxes/` 라는 상위 폴더가 없고(보관 폴더 바로 아래 `YYYY`), ID 는 0 이 채워진 채 쓰이며(`00000042`), 썸네일은 폭 기본 80 의 회색조다. 쪽 이미지 이름이 `page<N>.png` 인 점은 원문도 같다.

## 3. 발송 첨부파일: 형식과 변환 (원문 10장)

### 3.1 실제로 받아 주는 형식
- [코드] 판정은 파일 이름이 아니라 **첫 4096바이트**로 한다(`services/upload_check.py::kind`). 받는 것은 PDF(`%PDF`), PostScript(`%!`), TIFF(리틀/빅 엔디언·BigTIFF 머리), 텍스트(NUL 바이트가 없고 UTF-8 로 읽힘) 넷이고, 나머지는 `File type is unauthorized` 로 거절한다. 크기 한도는 `NAMIFAX_MAX_UPLOAD_BYTES`(기본 10 MiB), 넘으면 `File size is over the limit`. 발송 화면의 파일 선택기도 `.pdf,.tif,.tiff,.ps,.txt` 만 보인다(`templates/sendfax.jinja2`).
- [코드] 업로드는 시스템 임시 폴더에 `sendfax_<난수>_<파일명>` 으로 저장했다가 발송 요청(`dispatch_sendfax`)이 끝나면 지운다(`views/sendfax.py`). 변환 없이 그 파일 그대로 `sendfax` 인자 목록에 들어간다(`services/sendfax_command.py`).
- [문서] 원문 10.1 표의 처리 설명은 HylaFAX 내부 동작이다. 코드로는 확인할 수 없다.

| 형식 | 확장자 | 원문의 처리 설명 [문서] | 현재 코드 |
|---|---|---|---|
| PDF | `.pdf` | 최고 권장. Ghostscript 로 팩스 해상도(204x98 표준, 204x196 고해상도)로 래스터화 | 받음, 그대로 `sendfax` 에 넘김 [코드] |
| PostScript | `.ps` | HylaFAX 네이티브, 가장 빠르고 정확 | 받음 [코드] |
| TIFF | `.tif`, `.tiff` | G3/G4 흑백, 추가 렌더링 없이 전송 | 받음 [코드] |
| 텍스트 | `.txt` | HylaFAX `textfmt` 가 PostScript 로 바꿈 | 받음, 그대로 넘김. `textfmt` 는 HylaFAX 쪽 일이라 NamiFAX 코드에 없음 [코드] |
| PNG/JPEG | `.png`, `.jpg` | Pillow 또는 `typerules` 로 PDF/PS 로 자동 래핑 | **거절** [코드] |
| Word/Excel/PPT/HWP | `.docx` 등 | 클라이언트에서 PDF 로 저장(권장), 또는 서버에 LibreOffice Headless 설치해 자동 변환 | **거절**, 변환 코드 없음 [코드] |

- [코드] 이미지·오피스 문서 거절의 근거: PNG 머리(`\x89PNG...`)와 오피스(`PK`/OLE) 머리에는 NUL 바이트나 UTF-8 이 아닌 바이트가 있어 `kind` 가 `None` 을 돌려준다. 이 판정은 코드를 읽어 낸 결론이며 이 세션에서 실제 파일로 실행해 보지는 않았다. `src/` 에서 `libreoffice`, `soffice`, `unoconv`, `typerules`, `textfmt` 검색 결과가 없다.

> 모순: 원문 10.2 는 이미지(`.png`, `.jpg`)가 Pillow 나 HylaFAX 룰셋으로 PDF/PostScript 에 "자동으로 래핑된 후 발송"된다고 한다. 업로드 검사가 이미지를 먼저 거절하므로 현재 동작이 아니다(같은 차이가 [[hylafax-integration]] 2절 끝에도 적혀 있다). 원문 10.3 의 LibreOffice 변환도 "구축할 수 있다"는 권장일 뿐 코드에 없다. 현재 올바른 운영은 **사용자가 PDF 로 저장한 뒤 올리는 것**이다.

### 3.2 팩스 품질 권장 사양 (원문 10.4)
- [문서] 용지는 A4(210x297 mm) 또는 US Letter. 색은 흑백 1비트나 그레이스케일(흰 바탕에 선명한 검정 글자). 이미지 해상도는 200~300 DPI 가 적당하다. 팩스 표준은 가로 204 DPI, 세로 98(표준)/196(고해상도) DPI 라 300 DPI 를 넘는 해상도는 전송 시간만 늘린다. 한 통은 10 MB 이하를 권장한다(아날로그 회선이 9,600~14,400 bps 라 큰 파일은 통화 시간을 길게 점유하고 단선 위험이 커진다).
- [문서] 컬러 사진이나 연한 배경은 T.30 이 흑백 1비트라서 디더링 때 글자가 뭉개지거나 배경이 검게 나올 수 있으니 고대비 흑백을 권한다.
- [코드] 코드와 맞는 곳은 크기뿐이다. 기본 한도 10 MiB 는 위 권장과 같은 값이지만 코드에서는 **강제 한도**이고 환경변수로 바꾼다. 그 밖의 사양(용지, DPI, 색 모드)은 코드가 검사하지 않는다. 수신 쪽 기본 해상도 가정은 `DPI`(기본 200)다(`settings.dpi`).

## 4. OS별 Print-to-Fax (원문 11장)

사용자가 문서에서 인쇄(`Ctrl+P`/`Cmd+P`)를 눌러 바로 팩스를 보내는 구조다. 일반 OS 인쇄 대화상자에는 "수신 팩스 번호" 칸이 없어서 번호를 전달하는 방법이 핵심 과제다(원문 11.1).

### 4.1 목표 설계 [문서]
두 방식을 함께 제공하는 것이 원문의 구상이다.
1. **클라이언트 팝업 방식**: 인쇄를 가로채 번호 입력 창을 띄우고 NamiFAX REST API 로 올린다.
   - Windows: PostScript 드라이버 + 가상 포트 모니터(RedMon 또는 WPHFX). 스풀된 PS/PDF 를 가로채 번호 팝업, 확인하면 REST API(`/api/sendfax`)로 업로드.
   - macOS: CUPS 커스텀 백엔드(`/usr/libexec/cups/backend/namifax`)가 AppleScript 대화상자(`osascript`)로 번호·주소록을 받고 `curl` 로 POST.
   - Linux: CUPS 백엔드(`fax4CUPS`) + `zenity`/`kdialog` 팝업, 이후 `namifax sendfax` CLI.
2. **가상 네트워크 프린터 + 문서 내 태그 방식**: 클라이언트에 아무것도 설치하지 않는다. 호스트 리눅스의 **CUPS 공유 큐**(`ipp://서버:631/printers/namifax`)를 사용하고, 클라이언트는 "Generic / PostScript" 로 네트워크 프린터를 추가한다. 원문은 RAW 9100, IPP 631 소켓 리스너를 직접 만드는 것은 지양(오버엔지니어링)한다고 명시한다. CUPS 백엔드가 인쇄 파일을 `namifax print-in` 에 넘기고, 본문의 `[[FAX: 번호]]` 태그를 찾는다.
   - 태그가 있으면 그 번호로 즉시 발송하고, 최종 팩스에서 태그 글자가 상대방에게 보이지 않도록 흰 사각형으로 가리거나 표지로 대체한다.
   - 태그가 없으면 폐기하지 않고 발송자 IP/계정 기준으로 웹 "임시 보관함(Outbox Drafts)"에 올리고, 웹에서 수신처를 고르게 한다(안내 배너).
   - 원문 11.4 의 태그 문법: `[[FAX: 02-123-4567]]`, `[[FAX: 010-9876-5432, TO: 홍길동 귀하, COVER: standard]]`, 대소문자 무관·공백 허용. 본문 추출은 PyMuPDF/pdfplumber 와 첫 쪽 빠른 OCR, `<<FAX: ...>>` 꼴도 인식한다고 한다.

### 4.2 현재 구현 [코드]
구현된 것은 **2번 방식의 서버 쪽 일부**뿐이다. 흐름: CUPS 백엔드 스크립트 → `namifax print-in` → `process_inbound_print_job` → `dispatch_sendfax`(발송 화면과 같은 경로) → `sendfax`. 개요와 커밋 이력은 [[hylafax-integration]] 8절에 있고, 여기서는 원문과의 차이를 위주로 쓴다.

- CUPS 백엔드 `deploy/cups/namifax-fax`(POSIX sh): 인자가 없으면 CUPS 가 요구하는 장치 목록 한 줄(`direct namifax-fax "NamiFAX Print-to-Fax" ...`)만 출력하고 끝낸다. 인자가 있으면 `/etc/namifax.env` 를 `set -a` 로 읽고 `${NAMIFAX_HOME:-/opt/namifax}/.venv/bin/namifax print-in "$@"` 를 `exec` 한다. 설치는 스크립트 머리 주석과 `docs/ko/install/hylafax.md` 5-1 에 있다: `/usr/lib/cups/backend/namifax-fax` 로 복사(소유자 root, 권한 0700), 장치 주소 `namifax-fax:/` 로 프린터 추가.
- 명령 연결: `namifax print-in`(`main.py`, 하이픈·밑줄 둘 다)이 `cli/print_in.py::main` 을 부른다. CUPS 인자는 `job-id user title copies options [파일]` 이며 `args[1]` 이 사용자, `args[5]` 가 파일이다. 파일이 없으면 표준 입력을 읽는다. 데이터가 비면 메시지만 내고 종료 코드 0. DB 는 `cli_session()` 으로 연다.
- 태그 인식(`services/printer.py::extract_fax_tags`): 정규식 `\[\[FAX:\s*([\d\-\+\(\)\s]+)\]\]`, 대소문자 무시. 번호 자리에는 **숫자, `-`, `+`, 괄호, 공백**만 온다. 여러 개 있으면 **첫 번째만** 쓴다. 인쇄 데이터는 `utf-8`(오류 무시)로 디코드해 그 텍스트에서 찾는다. 텍스트 레이어 추출이나 OCR 은 없다.
- 태그가 있을 때: 데이터를 `<NAMIFAX_TMPDIR 또는 시스템 임시 폴더>/namifax_spool/printjob_<토큰>_<사용자>.ps|.pdf|.prn` 으로 저장한다(확장자는 머리가 `%!PS`/`%PDF` 인지로 정함). 사용자가 DB 에 있으면(`NFUserAccount.load_username`) 그 이름·메일·회사·장소·전화·팩스를 발신자로 채우고, 없으면 사용자 이름만 쓴다. `dispatch_sendfax` 가 성공하면 `status: QUEUED` 와 sendfax 작업 번호를 돌려주고 스풀 파일을 지운다. 실패하면 `status: FAILED` 와 메시지를 돌려주고 파일은 남기며 CLI 종료 코드는 1 이다. 예외는 삼켜서 결과로 돌려준다.
- 태그가 없을 때: `<임시 폴더>/namifax_drafts/draft_<토큰>_<사용자>.<확장자>` 로 저장만 하고 `status: DRAFT`, 종료 코드 0.
- 같은 모듈의 `NetworkPrinterService` 는 **받은 팩스를 출력하는 쪽**의 물리 네트워크 프린터 목록과 RAW 9100 소켓 전송·시험 인쇄이며, 위 print-in 과는 방향이 반대다(`send_raw_print`, `test_print`). 두 가지를 혼동하지 않는다.
- 이 저장소에서는 실제 CUPS 와 HylaFAX 에 붙여 시험하지 못했다. 스크립트의 인자 전달과 `print-in` 동작만 시험으로 본다([[hylafax-integration]] 8절, `docs/ko/install/hylafax.md` 5-1).

### 4.3 설계만 있고 코드에 없는 것 [문서]
- Windows 가상 포트(RedMon/WPHFX)와 번호 입력 팝업, macOS `osascript` 백엔드, Linux `fax4CUPS`+`zenity`/`kdialog`: `src/`·`deploy/` 에서 `osascript`, `zenity`, `kdialog`, `RedMon`, `fax4CUPS` 검색 결과 없음.
- REST 엔드포인트 `/api/sendfax`(클라이언트 업로드용)와 `/api/hooks/faxrcvd`(원문 8.3 패턴 B 의 웹훅): `src/`, `deploy/` 검색 결과 없음.
- 태그 부가 문법(`TO:`, `COVER:`), `<<FAX: ...>>` 꼴, 태그 흰 사각형 마스킹이나 표지 대체, PyMuPDF/pdfplumber 텍스트 추출과 OCR.
- 웹 "임시 보관함(Outbox Drafts)", 발송자 IP/계정 기반 등록, "방금 인쇄된 문서가 대기 중" 안내 배너: 현재 초안은 서버 임시 폴더의 파일일 뿐이며 웹 화면에서 이를 읽는 코드가 없다(`namifax_drafts` 는 `cli/print_in.py` 와 `services/printer.py` 에서만 나온다).

> 모순: 원문 11.3 은 CUPS 백엔드가 `/usr/lib/cups/backend/namifax` 이고 `namifax print-in "$1" "$2" ...` 로 호출한다고 하지만, 실제 스크립트는 `deploy/cups/namifax-fax`(설치 이름 `namifax-fax`, 장치 주소 `namifax-fax:/`)이고 `"$@"` 로 모두 넘긴다. 또 원문은 태그를 PDF 텍스트 레이어/OCR 로 찾는다고 하지만 코드는 인쇄 바이트를 텍스트로 디코드해 찾는다. [코드, 측정 2026-10-03] 같은 문장 `[[FAX: 02-1234-5678]]` 을 PostScript(`%!PS`)로 만든 입력에서는 `extract_fax_tags` 가 태그를 찾았지만, Ghostscript 로 같은 내용을 PDF 로 만든 입력은 압축하지 않은 것(`-dCompressStreams=false`)과 압축한 것 모두에서 찾지 못했다(`pdftotext` 는 두 PDF 에서 태그를 읽는다). 즉 PostScript 로 들어올 때만 동작하고 PDF 로 들어오면 태그를 찾지 못한다. 원문이 PostScript 로 인쇄하는 "Generic / PostScript" 드라이버를 쓰게 하는 것은 이 제약과 맞는다.

## 5. 다시 읽을 곳
- 훅 이름·인자·래퍼, `sendfax` 인자 구성, 모뎀·대기열 파싱, 사용자 동기화: [[hylafax-integration]].
- 보관 폴더 정리, 수명주기 정책, 스케줄러 4종, S3: [[scheduler-and-storage]].
- 설치 순서와 HylaFAX 설정 줄: [[install-hylafax]], 환경 변수 전체: [[operations-and-deployment]].
