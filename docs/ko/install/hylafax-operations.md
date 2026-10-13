# HylaFAX 운영 메모

운영 중에 자주 부딪히는 일을 모았습니다: 수신 스풀 이동, 정리 작업, 팩스 한 통이 만드는 파일, 발송 첨부 형식, 인쇄로 팩스 보내기. 설치 순서는 [HylaFAX 연동 설치](hylafax.md)에 있습니다.

!!! warning "시험 범위"
    이 저장소는 실제 HylaFAX 와 CUPS 에 붙여 시험하지 못했습니다. 아래 NamiFAX 동작은 코드를 읽어 확인한 것이고, HylaFAX 자체의 동작(스풀 이동, `faxqclean`)은 일반적인 HylaFAX 운영 방식입니다. 운영 서버에 적용하기 전에 시험 서버에서 확인하십시오.

## 1. 수신 스풀(`recvq`)을 큰 디스크로 옮기기

### HylaFAX 쪽

`/var/spool/hylafax/recvq` 는 HylaFAX 가 수신 중에 TIFF 를 쓰는 임시 버퍼입니다. 데몬 설정으로 폴더 이름을 바꾸지 말고, 운영체제 수준에서 물리 저장소만 바꿉니다. 이동하는 동안에는 반드시 HylaFAX 를 멈추십시오.

방법 1, 심볼릭 링크:

```sh
service hylafax stop
mv /var/spool/hylafax/recvq /data/storage/fax_recvq
ln -s /data/storage/fax_recvq /var/spool/hylafax/recvq
chown -R uucp:uucp /data/storage/fax_recvq
service hylafax start
```

방법 2, 바인드 마운트(더 안정적입니다). `/etc/fstab` 에 한 줄을 둡니다.

```
/data/storage/fax_recvq   /var/spool/hylafax/recvq   none   bind   0 0
```

### NamiFAX 쪽

- NamiFAX 는 `recvq` 경로를 직접 읽지 않습니다. 수신 훅(`faxrcvd`)이 HylaFAX 에서 받은 TIFF 경로를 인자로 쓸 뿐이므로, 링크나 마운트로 옮겼다면 **NamiFAX 설정은 바꿀 필요가 없습니다.**
- 훅은 이 TIFF 를 **복사**해 보관 폴더에 둡니다. 원본(`recvq`)을 지우는 코드는 NamiFAX 에 없습니다. 사용자가 보는 팩스는 모두 보관 폴더의 사본입니다.
- 사본이 쌓이는 **보관 폴더**를 큰 디스크로 옮기려면 `/etc/namifax.env` 에 경로를 지정합니다. 받은 팩스는 `AVANTFAX_ARCHIVE`(기본 `<HYLASPOOL>/archive`), 보낸 팩스는 `ARCHIVE_SENT`(기본 `<HYLASPOOL>/sent`)입니다.
- 클라우드 보존 정책과 로컬 저장소 제공자는 이와 별도로 `NAMIFAX_ARCHIVE_DIR`(기본 `/var/spool/hylafax/archive`)를 읽습니다. 보관 폴더를 옮길 때는 **`AVANTFAX_ARCHIVE` 와 `NAMIFAX_ARCHIVE_DIR` 를 같은 값으로** 맞추십시오.
- 보관 폴더는 훅을 실행하는 사용자(`uucp`)와 웹 서비스 사용자가 모두 쓸 수 있어야 합니다.

## 2. 정리 작업

정리는 세 군데에서 이뤄지며 서로 대상이 다릅니다.

| 대상 | 누가 | 비고 |
|---|---|---|
| HylaFAX 스풀(`recvq`, `doneq`, `docq`, `tmp`) | HylaFAX 의 `faxqclean`, `faxcron` | NamiFAX 는 건드리지 않습니다 |
| NamiFAX 보관 폴더, 임시 폴더 | NamiFAX 내장 스케줄러 또는 `namifax cron` | 아래 참고 |
| 원격(S3) 사본 | 저장 정책 | [저장소·예약 작업](../manual/admin/storage-scheduler.md) |

### HylaFAX 쪽 (`faxqclean`)

HylaFAX 는 끝난 작업과 더 이상 참조되지 않는 문서 파일을 `faxqclean` 으로 정리하며, 보통 cron 으로 돌립니다. 보관 기간과 `recvq` 정리 방식은 설치된 HylaFAX 버전과 배포판 설정에 따르므로 `faxqclean(8)`, `faxcron(8)` 설명서를 확인하십시오. NamiFAX 의 `src/`·`deploy/` 에는 `recvq` 나 `faxqclean` 을 다루는 코드가 없습니다.

### NamiFAX 쪽 (`namifax cron`)

내장 스케줄러(웹 서비스 안에서 돎, `NAMIFAX_ENABLE_SCHEDULER=1` 기본값)는 `tmp`(임시 폴더 정리), `inbox`(받은 팩스함 보관 이동, 기본 꺼짐), `lifecycle`(저장 정책 실행), `phonebook`(전화번호부 내보내기) 네 가지를 돌립니다. **관리자 > 예약 작업**에서 설정합니다. 스케줄러를 쓰지 않으려면 `deploy/cron.d/namifax` 를 `/etc/cron.d/namifax` 로 복사해 `namifax cron` 을 cron 으로 돌릴 수 있습니다.

| 옵션 | 동작 |
|---|---|
| `-t 일수` | 임시 폴더(`AVANTFAX_TMPDIR`, 기본 `/tmp/avantfax/`)에서 지정한 일수보다 오래된 파일 삭제. **필수 옵션**입니다 |
| `-i 일수` | 받은 팩스함에서 오래된 팩스를 정리(보관함으로 이동) |
| `-d 일수` | 받은 팩스함/보관함에서 오래된 팩스 삭제 |
| `-p 일수` | PDF 가 있는 팩스의 원본 TIFF 삭제 |
| `-s` | 관리자 > 저장소 화면에 저장한 정책 실행(저장한 정책이 없으면 아무 일도 하지 않음) |

`-t` 가 없으면 사용법만 출력하고 아무것도 하지 않으므로, `-i`/`-d`/`-p`/`-s` 를 쓰는 줄에도 `-t 2` 같은 값을 함께 적으십시오. 예:

```
0 0 * * *   uucp  sh -c 'set -a; [ -r /etc/namifax.env ] && . /etc/namifax.env; set +a; exec /opt/namifax/.venv/bin/namifax cron -t 2'
```

`deploy/cron.d/namifax` 에서 기본으로 켜진 줄은 위의 `-t 2` 하나이고, 나머지(`-i 30 -d 365`, `-p 90`, `-s`)는 주석 처리돼 있습니다(그 주석 예시 줄에는 `-t` 가 빠져 있으니 주석을 풀 때 `-t 2` 를 추가하십시오). `-d` 와 정확히 대응하는 스케줄러 작업은 없으므로 날짜로 지우려면 cron 에 적어야 합니다. 아무것도 켜지 않으면 팩스가 영원히 쌓입니다. 자세한 화면 설명은 [저장소·예약 작업](../manual/admin/storage-scheduler.md)을 보십시오.

## 3. 팩스 한 통을 받을 때 생기는 파일

HylaFAX 는 쪽수와 관계없이 한 통화로 받은 팩스를 `recvq` 에 멀티페이지 TIFF 하나(`fax<번호>.tif`, 예 `fax00000042.tif`)로 만들고, 수신이 끝나면 `FaxRcvdCmd` 훅(`faxrcvd`)을 실행합니다.

훅은 보관 폴더에 다음 경로를 만듭니다.

```
<보관 폴더>/YYYY/MM/DD/<발신번호>/<HylaFAX ID>/
```

- 날짜는 `faxinfo` 가 알려 주는 수신 시각입니다.
- 발신번호는 `+` 와 숫자만 남긴 값이며(앞의 `+` 는 뺌), 비어 있으면 `unknown` 입니다.
- HylaFAX ID 는 파일 이름에서 `fax` 와 `.tif` 를 뗀 것으로 **앞의 0 이 그대로 남습니다**(`00000042`).

폴더 안에 만들어지는 파일(순서대로):

| 파일 | 설명 |
|---|---|
| `fax.tif` | 원본 TIFF 의 복사본. `TIFF_TO_G4` 를 켜면 CCITT G4 로 다시 압축 |
| `fax.pdf` | LibTIFF `tiff2pdf` 로 변환, 실패하면 Pillow 로 변환 |
| `page0.png` … `page<N-1>.png` | 쪽마다 한 장, 번호는 0 부터. 회색조, 폭 `PREV_SP`(기본 750) |
| `thumb.png` | 첫 쪽 썸네일. 폭 `PREV_TN`(기본 80) |

파일 수는 **3 + 쪽수**입니다(1쪽 4개, 5쪽 8개, 30쪽 33개, 100쪽 103개). 하루 수신량이 많으면 쪽 이미지 때문에 파일 수와 용량이 빠르게 늘므로 정리 설정(2절)을 켜 두십시오. 선택 기능(`ENABLE_FAX_ANNOTATION`, OCR 색인, S3 업로드)은 이 파일들을 만든 뒤에 이어서 동작합니다.

`faxinfo` 가 실패하거나 TIFF 복사가 실패하면 로그만 남기고 종료 코드 0 으로 끝납니다. HylaFAX 쪽에서는 성공처럼 보이니 보관 폴더에 팩스가 생겼는지 확인하십시오.

## 4. 발송 첨부 형식과 변환

업로드 형식은 파일 이름이 아니라 **파일 앞 4096바이트**로 판정합니다.

| 형식 | 확장자 | 처리 |
|---|---|---|
| PDF | `.pdf` | 받음, 그대로 `sendfax` 에 전달 |
| PostScript | `.ps` | 받음 |
| TIFF | `.tif`, `.tiff` | 받음 |
| 텍스트 | `.txt` | 받음(NUL 바이트가 없고 UTF-8 인 파일). 변환은 HylaFAX 가 합니다 |
| 그림(PNG, JPEG), Word/Excel/PowerPoint/HWP | | **거절**(`File type is unauthorized`) |

- 크기 한도는 `NAMIFAX_MAX_UPLOAD_BYTES`(기본 10 MiB)이며 넘으면 `File size is over the limit` 로 거절합니다.
- NamiFAX 는 업로드 파일을 변환하지 않습니다. 그림이나 오피스 문서는 **사용자가 PDF 로 저장한 뒤** 올리도록 안내하십시오.
- 발송 화면의 파일 선택기에는 `.pdf, .tif, .tiff, .ps, .txt` 만 보입니다.
- 용지·해상도·색 모드는 코드가 검사하지 않습니다. 일반적으로 흑백 또는 회색조의 A4/Letter, 200~300 DPI 이면 충분하고(팩스는 가로 204 DPI, 세로 98/196 DPI), 크거나 컬러인 문서는 전송 시간이 길어지고 글자가 뭉개질 수 있습니다.

## 5. 인쇄로 팩스 보내기 (CUPS)

구현된 것은 CUPS 백엔드에서 `namifax print-in` 을 거쳐 `sendfax` 로 가는 서버 쪽 경로입니다.

```
CUPS 프린터 -> deploy/cups/namifax-fax -> namifax print-in -> (발송 화면과 같은 경로) -> sendfax
```

설치는 [HylaFAX 연동 설치](hylafax.md)의 5-1 절을 따릅니다: `deploy/cups/namifax-fax` 를 `/usr/lib/cups/backend/namifax-fax` 로 복사(소유자 root, 권한 0700)하고, CUPS 에서 장치 주소 `namifax-fax:/` 로 프린터를 추가합니다. 백엔드는 `/etc/namifax.env` 를 읽고 `${NAMIFAX_HOME:-/opt/namifax}/.venv/bin/namifax print-in` 을 실행합니다.

동작:

- 인쇄 내용에 `[[FAX: 02-123-4567]]` 같은 태그가 있어야 합니다. 번호 자리에는 숫자, `-`, `+`, 괄호, 공백만 올 수 있고, 대소문자는 구분하지 않으며, 여러 개이면 **첫 번째만** 씁니다.
- 태그가 있으면 CUPS 사용자 이름으로 `sendfax` 에 넘겨 대기열에 넣습니다. NamiFAX 에 같은 이름의 사용자가 있으면 그 사용자의 이름·회사·전화·팩스 정보가 발신자로 채워집니다. 성공하면 `QUEUED`, 실패하면 `FAILED`(CLI 종료 코드 1, 스풀 파일 보존)입니다.
- 태그가 없으면 임시 폴더의 `namifax_drafts/` 에 파일로 저장만 하고 `DRAFT` 로 끝납니다(종료 코드 0). 웹 화면에서 이 초안을 읽는 기능은 아직 없습니다.
- 태그는 인쇄 데이터를 텍스트로 읽어 찾습니다. 측정 결과 **PostScript 로 들어오면 찾지만 PDF 로 들어오면 찾지 못했습니다.** 클라이언트 프린터는 "Generic / PostScript" 드라이버로 추가하십시오.
- 동작 확인: `echo "[[FAX: 123]]" | namifax print-in 1 사용자 제목 1 ""`

!!! note "구현되지 않은 것"
    예전 설계 문서에는 있었지만 이 저장소에는 없는 기능입니다. 운영 절차에 넣지 마십시오.

    - 보낸 팩스의 S3/GCS 업로드(받은 팩스의 S3 업로드와 저장 정책만 있습니다)
    - HTTP 웹훅 훅(`/api/hooks/faxrcvd`)과 클라이언트 업로드용 `/api/sendfax`
    - Windows 가상 포트(RedMon/WPHFX), macOS `osascript` 백엔드, Linux `fax4CUPS`/`zenity`/`kdialog` 번호 입력 팝업
    - 태그 부가 문법(`TO:`, `COVER:`), 태그 마스킹, PDF 텍스트 추출/OCR 로 태그 찾기
    - 웹의 임시 보관함(Outbox Drafts)과 안내 배너
    - 이미지와 오피스 문서의 자동 PDF 변환(LibreOffice 등)

관련: [이메일로 팩스 보내기](email-to-fax.md), [운영 점검 목록](operations-checklist.md)
