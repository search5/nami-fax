---
title: AvantFAX 3.x에서 NamiFAX로 옮기기
type: source
updated: 2026-10-13
sources: [docs/ko/install/migration.md, docs/en/install/migration.md]
verified: false
---

> 원본은 `docs/ko/install/migration.md`(2026-10-13 에 MkDocs 구조로 이동. 이전 경로 `docs/MIGRATING_FROM_AVANTFAX3.md`)다. 영문판 `docs/en/install/migration.md` 가 있으나 이 요약은 한국어 원문 기준이다.

## 요약

AvantFAX 3.x(3.0~3.3.5, MySQL/MariaDB)를 NamiFAX로 옮기는 방법과 옮긴 뒤 달라 보이는 점. 3.x 이후 DB만 대상이고 2.x 는 지원하지 않는다. 기존 DB와 팩스 보관 폴더에 그대로 붙고, 원본 PHP 앱과 한동안 병행할 수 있다(예행연습의 읽기·쓰기 범위에서만 확인). 비밀번호는 원본 MD5 로 로그인한 뒤 **성공하는 순간 그 계정만 Argon2id 로** 바뀐다. 원본이 실제로 만든 데이터로 호환을 확인했다고 주장한다.

## 핵심 내용

### 1장: 한눈에 보기

| 질문 | 문서의 답 |
|---|---|
| 기존 DB를 그대로 쓸 수 있나 | **예.** 사용자·모뎀·카테고리·라우팅·주소록·배포 목록·보관 팩스가 모두 남음 |
| 비밀번호는 | 원본 MD5 해시로 그대로 로그인, 성공하면 그 계정 해시를 Argon2id 로 저장(4.5) |
| 되돌릴 수 있나 | 조건부 예. 이식본은 DB에 추가만 하고 지우거나 바꾸지 않음(4장). 다만 이식본에서 로그인했거나 비밀번호를 바꾼 계정은 원본이 못 읽는 Argon2id 가 됨. 병행이 필요하면 `NAMIFAX_PASSWORD_HASH=md5`(4.5) |
| 달라 보이는 것 | 기존 팩스 미리보기 재생성(4.2), 옛 주소, 모든 사용자 재로그인. HTML 엔티티로 저장된 글자는 풀어서 보여 같게 보임(4.1) |
| 확인하지 못한 것 | 실제 HylaFAX 서버 연동, 수년치 대용량 보관소의 첫 기동 시간 |

### 2장: 예행연습으로 확인한 것

- "DB를 그대로 쓸 수 있다"는 합성 데이터가 아니라 **원본 PHP 앱이 실제로 만든 데이터**로 확인. `tools/migration_rehearsal/run.sh` 가 재현한다. 이 디렉터리는 남아 있지만 원본 PHP 소스(`legacy/`)가 필요하므로 **먼저 `git checkout 9408385 -- legacy`** 로 되살려야 한다(Docker·네트워크 필요, 이미지가 있으면 약 15초)
- 절차: 원본 3.3.5 를 PHP 5.6 + MDB2 2.4.1 + MariaDB 10.3(2013년 무렵 비엄격 SQL 모드)에서 실행 → 원본 웹 화면으로 사용자 3명·모뎀 2개·카테고리 3개·주소록·이메일 주소록을 만들고 `ArchiveIn::create()` 로 팩스 6건(2건 보관) 기록 → 같은 DB·팩스 폴더에 NamiFAX 연결해 비교
- 결과: 세 사용자와 관리자 로그인 성공(원본 관리자의 옛 비밀번호는 거부) / 사용자별 수신함 목록과 PDF 열람 가능 여부(보관 팩스 포함)가 원본과 **같음**(회선·카테고리 제한 포함) / 썸네일·쪽 이미지는 처음 볼 때 새로 생성(4.2) / 원본이 쓴 연락처를 NamiFAX가 읽음(엔티티는 풀림, 4.1) / NamiFAX가 쓴 연락처(한글·악센트 포함)를 원본이 정상으로 읽음 / NamiFAX 사용 뒤에도 원본 앱의 로그인·수신함·주소록·보관함·설정·출력함이 정상
- 테스트 환경은 3.3.5 한 가지. 3.0~3.2.x 에서 업그레이드를 거듭한 설치는 `tests/unit/test_legacy_database_compat.py` 가 3.2.0 스키마(MySQL 8.4, MariaDB)로 확인하지만 실제 업그레이드 이력이 있는 DB로 시험하지는 않음

### 3장: 이전 절차

1. **백업**: DB(`mysqldump`)와 팩스 보관 폴더(스키마 보정이 일어남)
2. **설정**: 5장 대응표로 `local_config.php` 값을 환경변수로 옮김. 최소 `DATABASE_URL`(`mysql+pymysql://사용자:비밀번호@호스트/avantfax`), `AVANTFAX_INSTALLDIR`(DB에 상대 경로로 저장된 팩스 경로의 기준), `AVANTFAX_ARCHIVE`(원본 `$ARCHIVE`, 기본 `<설치 디렉터리>/faxes/recvd`), `NAMIFAX_SESSION_SECRET`, `NAMIFAX_SECRET_KEY`(→ [[operations-checklist]] 1장)
3. **기동**: 첫 기동에서 새 테이블과 인덱스 생성. 큰 `FaxArchive` 는 인덱스 때문에 오래 걸릴 수 있음
4. **로그인**: 모든 사용자 재로그인(PHP 세션 불연속). `wasreset` 계정은 첫 로그인에서 비밀번호 변경
5. **HylaFAX와 cron**: 원본 PHP 훅·cron 을 NamiFAX 명령으로 교체 → [[install-hylafax]], `deploy/hylafax/`, `deploy/cron.d/namifax`
6. **웹 서버**: 옛 주소 → 새 주소 규칙(6장)
7. **SMTP**: 관리자 화면 SMTP 설정에서 다시 입력(원본 `SMTP_*` 변수는 읽지 않음)

### 4장: 달라 보이는 점과 한계

**4.1 HTML 엔티티로 저장된 글자**
- 원본은 모든 폼 값을 `htmlentities(ENT_QUOTES, "UTF-8")` 에 통과시켜 저장(예: `Müller & Söhne GmbH` → `M&uuml;ller &amp; S&ouml;hne GmbH`, `Soporte Línea` → `Soporte L&iacute;nea`, `O'Brien "Bob"` → `O&#039;Brien &quot;Bob&quot;`)
- NamiFAX는 **읽을 때 풀어서** 같은 글자를 보임(`models/types.py` 의 `LegacyHtmlString`, `LegacyHtmlText`). DB는 건드리지 않아 되돌리기에 영향 없음. 새로 쓰는 값은 순수 UTF-8 이며 원본 앱에서도 정상
- 풀리는 것은 사람이 입력하는 텍스트(이름, 업체명, 설명, 별칭, 서명, 팩스 메모 등). 경로·번호·로그는 그대로
- 검색은 입력한 단어와 원본 저장 형태를 모두 비교(`müller` 로 `M&uuml;ller` 검색, 대소문자 구분 안 함). 값을 바꾸지 않고 저장하면 DB 원래 값이 남고, 바꾼 값은 순수 UTF-8
- 안전: 푼 글자는 출력 시 다시 이스케이프하므로 `&lt;script&gt;` 가 저장돼 있어도 실행되지 않음
- 한계: 원본이 **이중 인코딩해 깨뜨린 값**(예: 한글이 `ÃªÂ¹â‚¬`)은 복원 안 함, 관리자 화면에서 재입력 / 사용자가 `&uuml;` 를 글자 그대로 입력했다면 `ü` 로 보임(드묾) / 이름 중복 검사는 저장값끼리 비교해서 `Vertrieb M&uuml;ller` 가 있을 때 `Vertrieb Müller` 를 새로 만들면 중복으로 안 잡힐 수 있음(추론, 미시험) / 예행연습은 PHP 5.6 동작만 봄(더 오래된 PHP는 ISO-8859-1 기준 이중 인코딩 등 다를 수 있음)
- `tools/migration_rehearsal/check_text.py --strict`(이것도 `legacy/` 복원 뒤)가 원본 데이터로 점검

**4.2 기존 팩스의 미리보기**
- 원본의 `thumb.gif`·`prev*.gif` 는 쓰지 않음. 처음 볼 때 Ghostscript 로 `thumb.png`·`page*.png` 를 **팩스 폴더 안에** 새로 만듦(원본 파일 유지). 웹 서버 사용자의 쓰기 권한과 Ghostscript 필요
- 보관함 첫 화면은 최대 한 쪽 분량(기본 30건)을 한꺼번에 변환. 미리 만들려면 `namifax create-thumbnails`

**4.3 NamiFAX가 DB에 추가하는 것(원본 PHP 앱에 영향 없음)**
- 새 테이블 **5개**: `SystemConfig`, `SystemSettings`, `NetworkPrinters`, `UserTOTP`, `UserWebAuthnCredentials`(과 `alembic_version`). OCR 텍스트는 원본처럼 `FaxArchive.faxcontent` 에만 저장한다. 리비전 `0019` 가 만들던 `FaxOCR` 는 `0027` 이 지운다
- 검색용 인덱스 12개, `AddressBook` 에 컬럼 10개, `UserAccount.last_ip` 15자 → 45자(IPv6)
- 기존 행은 지우거나 바꾸지 않음. 기본 카테고리와 표지는 기존 DB에 추가하지 않음

**4.4 그 밖의 차이**
- 비밀번호 길이는 원본과 같게 8~15자(`MIN_PASSWD_SIZE`, `MAX_PASSWD_SIZE`)
- 화면은 Tailwind CSS 로 새로 만듦. 원본 테마와 `custom.css` 미지원
- 대화상자는 별도 창이 아니라 페이지. 변경 요청(삭제, 보관 등)은 POST + CSRF 토큰이 필요해 외부 스크립트가 원본 `ajax/*.php?fid=…` 를 GET 으로 부르던 방식은 동작하지 않음
- 수신함·보관함 날짜는 고정 형식(원본 `ARCHIVE_DATE_FORMAT` 설정 없음)
- 한국어 외 번역은 부분적: 695개 문구 중 한국어 외 로케일에서 번역된 것은 292~333개(약 42~47%), 나머지는 영어. 원본과 같은 뜻의 문구는 원본의 영어 원문과 번역을 가져왔고 나머지는 NamiFAX 신규 문구라 원본 번역이 없음. 가져오는 데 쓴 `tools/i18n_import_legacy.py` 는 삭제됨

**4.5 비밀번호 해시(Argon2id)**
- Argon2id 로 저장(솔트 포함, `NAMIFAX_ARGON2_TIME_COST`·`_MEMORY_COST`·`_PARALLELISM`). 원본 MD5(32자리)는 계속 확인되고 **그 계정이 이식본에 로그인하는 순간** 바뀜. 로그인하지 않은 계정은 MD5 그대로
- `UserAccount.password`, `UserPasswords.pwdhash` 는 마이그레이션 `0026` 이 255자로 확장(원본 `VARCHAR(32)`)
- **원본 PHP 앱은 Argon2id 를 읽지 못함**: 이식본에서 로그인한 계정은 원본으로 돌아가면 로그인 불가, 비밀번호 찾기로 새로 받아야 함
- 병행·되돌림 가능성을 열어 두는 동안 `NAMIFAX_PASSWORD_HASH=md5`(새 비밀번호도 원본 형식, 업그레이드 안 함). 전환 확정 뒤 설정을 지우면 이후 로그인부터 Argon2id

### 5장: `local_config.php` 설정 대응표

원본 `local_config.php` 는 읽지 않고 같은 이름의 **환경변수**로 지정(systemd 의 `Environment=`/`EnvironmentFile=`). 켜고 끄는 값은 `1` 또는 `true` 가 켜짐(PHP `true`/`false` 직접 사용 금지). 미지정이면 기본값이고 대부분 원본과 같지만 일부는 다름(변수별 차이는 `git show 61c3663:docs/PORTING_GAPS.md` 의 E6, E7).

**5.1 같은 이름으로 지정**(괄호는 문서가 적은 기본값)
- 화면 동작: `SHOW_ALL_CONTACTS`(켜짐), `RESTRICTED_USER_MODE`, `INBOX_LIST_MODEM`, `FOCUS_ON_NEW_FAX`, `SENDFAX_USE_COVERPAGE`(켜짐), `SENDFAX_REQUEUE_EMAIL`(켜짐), `ENABLE_DL_TIFF`, `WHITEPAGES` 등
- 쪽 크기·길이: `DEFAULT_FAXES_PER_PAGE_INBOX`(25), `DEFAULT_FAXES_PER_PAGE_ARCHIVE`(30), `MAX_USERNAME_SIZE`(15), `MAX_PASSWD_SIZE`(15), `MIN_PASSWD_SIZE`(8), `MAX_EMAIL_SIZE`(99)
- 라우팅·인식: `ENABLE_DID_ROUTING`, `AUTOCONFDID`, `ENABLE_BARDECODE_SUPPORT`, `ENABLE_OCR_SUPPORT`, `OCR_*`, `CALLIDN_*`
- 수신·알림: `ARCHIVEFAX2EMAIL`, `FAXRCVD_*`, `NOTIFY_*`, `PRINTERNAME`, `PRINTCMD`, `TIFF_TO_G4`, `ENABLE_FAX_ANNOTATION` 등
- 표지·보내기: `COVERPAGE_FILE`, `COVERPAGE_MATCH`, `USE_HTML_COVERPAGE`, `FROM_*`, `DEFAULT_TSI_ID`, `EMAIL_*` 등
- 변환: `PAPERSIZE`(a4), `DPI`(200), `PREV_TN`(80), `PREV_SP`(750)
- 경로·실행 파일: `HYLASPOOL`, `HYLAFAX_PREFIX`, `BINARYDIR`(도구 이름으로도 지정), `PHONEBOOK`, `ARCHIVE_SENT`, `SUDO`, `WWWUSER`(원본 기본 `apache`, 이식본 기본은 Debian의 `www-data`)
- 인증: `ALTERNATE_AUTH_*`, `WEBSERVER_AUTH`, `PWAUTHPATH`
- 날짜 형식은 문법이 다름: 원본 `ARCHIVE_DATE_FORMAT` 은 MySQL 형식(`%i` 가 분), NamiFAX 의 `EMAIL_DATE_FORMAT`·`FAXCOVER_DATE_FORMAT` 은 파이썬 형식(`%M` 이 분). 값을 그대로 옮기지 말 것

**5.2 이름이 바뀌거나 다른 곳에서 설정**
- `AFDB_ENGINE/HOST/USER/PASS/NAME` → `DATABASE_URL`
- `$INSTALLDIR`, `$ARCHIVE`, `$TMPDIR` → `AVANTFAX_INSTALLDIR`, `AVANTFAX_ARCHIVE`, `AVANTFAX_TMPDIR`
- `$RESERVED_FAX_NUM` → `AVANTFAX_RESERVED_FAX_NUM`, `$AVANTFAX_SERVERNAME` → `AVANTFAX_SERVERNAME`
- `SF_MAXSIZE`, `SF_FILESIZE` → `NAMIFAX_MAX_UPLOAD_BYTES`(바이트)
- `USE_SMTPSERVER`, `SMTP_*`, `SYSTEM_EMAIL_SIG_*` → **관리자 화면 SMTP 설정**(DB 저장, 비밀번호는 `NAMIFAX_SECRET_KEY` 로 암호화)

**5.3 필요 없는 것**
- 테마·플러그인(`ADMINTHEME_DIR`, `USERTHEME_DIR`, `PLUGINS_DIR`, `ARCHIVE_WIDE`, `NOTHUMBIMG` 등)
- 변환 도구(`CONVERT`, `TIFFCP*`, `GS*`, `PNM*`, `HYLATIFF2PS` 등; Ghostscript·Pillow 로 대체, `git show 61c3663:docs/PORTING_GAPS.md` G절)
- PHP 환경(`HAS_MIME_FUNCTION`, `HAS_FILEINFO`, `HAS_NEGATIVE_TIFF`, `AVANTFAX_DEBUG`, `AVANTFAX_VERSION`, `USERSESSION`)
- 화면 문구용(`CONTACTFILETYPES`, `SENDFAXFILETYPES`, `SYSTEM_IP`; 새 사용자 메일의 주소는 요청 주소 사용)

### 6장: 웹 서버에서 옛 주소를 새 주소로 보내기

- 북마크·외부 링크 보존을 위해 **웹 서버에서** 301 설정(애플리케이션 코드에는 없음). 규칙은 `deploy/legacy-redirects/`, Apache·nginx 각각 실제 서버로 17개 주소 시험
- Apache: `apache.conf` 를 `deploy/apache/namifax.conf` 의 `<VirtualHost>` 안 `ProxyPass` 앞에 `Include`(`mod_rewrite` 필요). nginx: `nginx.conf` 를 `server` 블록 안 `location /` 앞에 `include`
- 예: `/inbox.php?pageindex=2` → `/inbox?pageindex=2`(쿼리 유지), `/index.php` → `/login`, `/addressbook_edit.php?abook_id=5` → `/addressbook/edit?abook_id=5`, `/pdf.php?fid=12` → `/faxes/download/12?format=pdf`, `/refax.php?fid=12` → `/sendfax?refax=12`, `/admin/conf_modems_edit.php?devid=1` → `/admin/modems?devid=1`, `/admin/users.php?uid=4` → `/admin/users?uid=4`
- 사람이 여는 화면만 다룸(원본 `ajax/*.php`, `file.php` 는 제외). `tests/unit/test_legacy_redirects.py` 가 도착 주소가 앱에 실제로 있는지 감시

### 7장: 사용자에게 알릴 것
- 처음 한 번 재로그인 / 화면 모양·대화상자 변경(기능과 권한 규칙은 같음) / 비밀번호 찾기·2단계 인증(TOTP)·패스키는 새 기능

## 문서가 주장하는 수치·상태

- 예행연습 대상은 3.3.5 한 가지, 재현 약 15초(Docker 이미지 있을 때). 로그인·수신함·PDF 열람·주소록·보관함이 원본과 일치.
- 새 테이블 5개, 인덱스 12개, `AddressBook` 컬럼 10개 추가. 마이그레이션 `0026`(해시 컬럼 255자), `0027`(`FaxOCR` 삭제).
- 번역: 695개 문구 중 한국어 외 292~333개(약 42~47%).
- 리다이렉트 17개 주소를 Apache·nginx 에서 시험.

## 낡았을 가능성이 큰 부분

- 번역 수치(695, 292~333)는 측정 시점 값이라 문구가 늘면 달라진다.
- 3.0~3.2.x 업그레이드 이력 DB, 대용량 `FaxArchive` 의 첫 기동 시간, 실제 HylaFAX 연동은 문서 스스로 미확인이라고 밝힌다.
- 이름 중복 검사 경계 사례는 추론이며 미시험이다.
- 예행연습 도구는 `legacy/` 복원 전에는 실행되지 않는다.

## 관련 주제 페이지

[[database-and-migrations]] [[operations-and-deployment]] [[migration-from-avantfax]] [[authentication-and-security]] [[i18n-and-ui]]
