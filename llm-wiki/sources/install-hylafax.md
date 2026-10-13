---
title: HylaFAX 연동 설치 가이드
type: source
updated: 2026-10-13
sources: [docs/ko/install/hylafax.md, docs/en/install/hylafax.md]
verified: false
---

> 원본은 `docs/ko/install/hylafax.md`(2026-10-13 에 MkDocs 사이트 구조로 이동. 이전 경로 `docs/INSTALL_HYLAFAX.md`)다. 영문판 `docs/en/install/hylafax.md` 가 있으나 이 요약은 한국어 원문 기준이다.

## 요약

NamiFAX와 HylaFAX를 연결하는 설치 절차(0~7단계, 5-1 포함). 원본 AvantFAX 설치 스크립트(`debian-install.sh`, `setup-postfix.sh` 등; 원본 소스는 커밋 `9408385` 의 `legacy/`)가 하던 일을 옮긴 것이고 단계마다 확인 방법을 적었다. **이 저장소에서는 실제 HylaFAX에 붙여 시험하지 못했다고 문서가 밝힌다.** 운영 서버 전에 시험 서버에서 한 번 거치라고 안내한다. 경로 가정: NamiFAX `/opt/namifax`(가상환경 `.venv`), HylaFAX 스풀 `/var/spool/hylafax`, 서비스 사용자 `uucp`.

## 핵심 내용

### 0단계: 환경 파일
- `/etc/namifax.env`(모드 0640)에 DB 접속과 설정을 둔다. 저장소의 파일이 모두 이 한 파일을 읽는다.
  - systemd 서비스(`systemd/namifax.service`): `EnvironmentFile=-/etc/namifax.env`. `-` 때문에 파일이 없어도 시작은 하지만 `DATABASE_URL` 이 없어 현재 폴더의 SQLite 로 조용히 떨어지므로 꼭 만들 것
  - cron(`deploy/cron.d/namifax`): `EnvironmentFile` 이 없어 각 줄이 `sh -c 'set -a; . /etc/namifax.env; set +a; exec …'` 로 파일을 먼저 읽음
  - 훅 스크립트(`deploy/hylafax/bin/*`): `set -a; . /etc/namifax.env; set +a` 뒤에 `exec`
- **서식**: `KEY=value` 한 줄씩. `export` 와 값 뒤 `#` 주석 금지(systemd 는 줄 끝 `#` 을 값으로 읽음. 주석은 `#` 으로 시작하는 별도 줄). 값에 `&` `;` `(` `)` `<` `>` `|` 공백이 있으면(예: `?charset=utf8mb4&x=1`) 큰따옴표로 감쌈(systemd 와 셸이 똑같이 벗김). 따옴표 안에는 `$` 백슬래시 역따옴표 `"` 금지
- 예시 변수: `DATABASE_URL`, `NAMIFAX_SESSION_SECRET`, `NAMIFAX_SECRET_KEY`, `ENABLE_DID_ROUTING`(훅과 웹이 같은 값), `FAXMAILUSER`, `WWWUSER`(서비스 실행 사용자)
- HylaFAX가 기본 위치에 없으면 `HYLASPOOL`, `HYLAFAX_PREFIX`, `BINARYDIR` 로 지정(`sendfax`, `faxstat`, `faxinfo`, `faxadduser` 탐색용)

### 1단계: 훅 연결
- `deploy/hylafax/bin/*`(`faxrcvd`, `dynconf`, `notify`, `faxcover`)를 `/var/spool/hylafax/bin/` 에 복사하고 실행 권한. 소유자는 훅을 실행하는 사용자(보통 `uucp`)
- 각 모뎀 설정(`/etc/hylafax/config.ttyS0` 등)에 `deploy/hylafax/config.namifax` 의 세 줄을 붙임(모뎀이 여럿이면 파일마다)
- 서버 설정(`/var/spool/hylafax/etc/config`)에 `deploy/hylafax/hfaxd.conf.snippet` 의 `JobFmt` 줄과 `deploy/hylafax/etc-faxq.snippet` 의 `NotifyCmd`, `CoverCmd` 줄을 붙임. **`JobFmt` 는 NamiFAX가 읽는 열 순서와 같아야 함**(다르면 출력함 목록이 어긋나거나 빔)
- 재시작: `systemctl restart hylafax`(배포판에 따라 `faxq`, `hfaxd`, `faxgetty`)
- 확인: `sudo -u uucp /var/spool/hylafax/bin/dynconf ttyS0 5551234` 가 아무것도 출력하지 않고 끝나야 함(차단 번호면 `RejectCall: true`). 시스템 로그에 `dynconf> checking CallID1 …` 줄이 남음

### 2단계: 웹 서비스
- **최상위** `systemd/namifax.service`(`deploy/` 아래가 아님)를 `/etc/systemd/system/` 에 두고 `systemctl daemon-reload && systemctl enable --now namifax`. 이 서비스는 `/etc/namifax.env` 를 읽음
- 앞단 웹 서버: `deploy/nginx/namifax.conf` 또는 `deploy/apache/namifax.conf`
- HTTPS면 ini 의 `session.secure = true` 가 필요한데 `namifax serve` 는 ini 를 **옵션을 줄 때만** 읽음. `ExecStart` 를 `namifax serve --config /etc/namifax/production.ini` 로 바꾸거나 환경 파일에 `NAMIFAX_INI=/etc/namifax/production.ini`. ini 의 `[app:main]` 에서 `session.secret`, `session.secure`, `csrf.trusted_origins`, `secret.key`, `sqlalchemy.url` 을 읽음(`pserve production.ini` 도 동일)
- 프록시 뒤에서는 `X-Forwarded-Host` 를 넘겨야 변경 요청의 출처 검사가 통과
- 첫 관리자: `namifax createuser -u admin -e you@example.com`

### 3단계: 사용자 동기화 (선택)
- `hfaxd` 에 사용자 이름이 등록돼 있어야 `faxrm`, `faxalter` 가 그 사용자의 작업을 다룸. 원본은 계정 생성·비밀번호 변경 때마다 `faxadduser`/`faxdeluser` 를 `sudo` 로 실행
- 켜는 법: (1) `deploy/sudoers.d/namifax` 를 `/etc/sudoers.d/namifax` 로 복사(0440, `visudo -cf`, 서비스 사용자 이름 맞춤) (2) `/etc/namifax.env` 에 `HYLAFAX_USER_SYNC=1` (3) `systemd/namifax.service` 의 `NoNewPrivileges=true` 를 `false` 로(켜져 있으면 `sudo` 불가)
- **주의**: `faxadduser` 는 비밀번호를 명령줄 인자(`-p`)로만 받아 실행 순간 같은 서버의 다른 사용자가 `ps` 로 볼 수 있음(원본과 같은 한계). 다른 사용자가 없는 전용 장비에서만 쓸 것. 끄면(기본) 아무것도 실행 안 함

### 4단계: 주기 작업
- **관리자 > 예약 작업**(`/admin/scheduler`; `/admin/maintenance` 는 없음)에서 설정. 내장 스케줄러가 돌리는 작업은 4종: `tmp`(임시 폴더 정리, 일수·시각), `inbox`(받은 팩스함의 오래된 팩스를 보관함으로 이동, 기본 꺼짐), `lifecycle`(보존 기간 정책 적용, 정책 값은 Storage & Cloud 화면), `phonebook`(전화번호부 내보내기, 주기)
- 각 작업에 "지금 실행"과 마지막 실행 결과. 저장한 변경은 실행 중인 스케줄러가 1분 안에 반영(재시작 불필요). 화면 위쪽에 스케줄러 상태와 **정지/시작** 버튼: 정지하면 APScheduler 엔진을 종료해 어떤 작업도 저절로 돌지 않고(프로세스는 남아 15초마다 시작 요청 확인), 시작하면 엔진을 다시 띄움. 정지 상태는 DB에 저장돼 재시작 뒤에도 유지
- 문서는 스케줄러가 웹 서비스에 내장(`NAMIFAX_ENABLE_SCHEDULER=1`, 기본값)되거나 `namifax scheduler` 를 별도 서비스(`systemd/namifax-scheduler.service`)로 돌린다고 쓴다. 아래 cron 방식은 스케줄러를 쓰지 않을 때의 대안
- `deploy/cron.d/namifax` 를 `/etc/cron.d/namifax` 로 복사해 보존 기간을 정함. **보관함의 오래된 팩스를 날짜로 지우는 `-d` 에 정확히 대응하는 스케줄러 작업은 없음**(비슷한 것은 저장 정책의 `full_retention_days`). `-d` 가 필요하면 cron 에 적을 것. 아무것도 켜지 않으면 팩스가 영원히 쌓임. cron 줄의 `sh -c` 래핑은 유지할 것

> 모순: 위 "별도 서비스" 서술은 현재 코드와 다르다. 2026-10-03 결정으로 `namifax scheduler`, `systemd/namifax-scheduler.service` 를 제거했고 스케줄러는 웹 프로세스(`namifax serve`) 안에서만 돈다(`log.md` 참고, [[scheduler-and-storage]]). 문서의 해당 문장이 아직 고쳐지지 않았다.

### 5단계: 이메일로 팩스 보내기 (선택)
- `deploy/postfix/setup-email2fax.md`. 원본 `setup-postfix.sh` 가 하던 설정이며, 이 저장소의 스크립트는 시스템 파일을 직접 고치지 않으므로 내용을 읽고 직접 넣을 것

### 5-1단계: 가상 프린터로 팩스 보내기 (선택)
- CUPS 백엔드: `deploy/cups/namifax-fax` 를 `/usr/lib/cups/backend/namifax-fax` 로 복사(소유자 root, 0700), CUPS 에서 장치 주소 `namifax-fax:/` 로 프린터 추가
- 인쇄 내용에 `[[FAX: 02-123-4567]]` 같은 태그가 있어야 하며 작업은 CUPS 사용자 이름으로 `sendfax` 에 넘어감. 태그가 없으면 임시 폴더에 초안으로만 저장, `sendfax` 가 실패하면 CUPS 에 실패로 돌려줌
- 확인: `echo "[[FAX: 123]]" | namifax print-in 1 사용자 제목 1 ""`
- 실제 CUPS·HylaFAX 와는 시험하지 못함(백엔드 스크립트의 인자 전달과 `namifax print-in` 동작만 시험)

### 6단계: 파일 권한
- 보관 폴더(`/var/spool/hylafax/archive`, `…/sent`)는 훅 실행 사용자와 웹 서비스 사용자 모두 쓸 수 있어야 함(같은 `uucp` 가 가장 단순). 임시 폴더(`AVANTFAX_TMPDIR`)도 같음
- `/etc/namifax.env` 는 0640, 소유 `root:uucp`. systemd 는 root 로 읽고 cron·훅은 `uucp` 로 읽음. DB 비밀번호와 세션 키가 들어 있음

### 7단계: 설치 뒤 점검 순서
1. 로그인 → 설정 → 시스템 로그에 오류 없는지
2. 관리자 > 모뎀에서 모뎀 생성 후 상태가 `Running and idle`(`faxstat` 을 읽음)
3. 시험 팩스 전송 후 출력함에 작업이 나오고, 완료 뒤 `notify` 가 보관함에 보낸 팩스를 만드는지
4. 시험 팩스 수신 후 `faxrcvd` 가 받은 팩스함에 올리는지(썸네일, PDF, 메일 알림)
5. 대시보드에 HylaFAX 버전이 표시되는지(`faxstat -i`)

## 문서가 주장하는 수치·상태

- 경로 가정과 `/etc/namifax.env` 모드 0640(소유 `root:uucp`)은 위와 같다.
- 실제 HylaFAX·CUPS 연결 시험은 하지 못했다고 문서가 밝힌다.
- 내장 스케줄러 작업은 4종이며 `-d` 에 해당하는 작업은 없다.

## 낡았을 가능성이 큰 부분

- 4단계의 "`namifax scheduler` 별도 서비스" 문장: 코드에서는 이미 제거됨(위 모순 블록).
- 배포판별 서비스 이름(`faxq`, `hfaxd`, `faxgetty`)과 `JobFmt` 열 순서의 일치는 실제 HylaFAX 서버에서만 확인할 수 있다.
- 마이그레이션 예행연습 도구(`tools/migration_rehearsal/`)는 이 문서가 아니라 [[migrating-from-avantfax3]] 가 다룬다.

## 관련 주제 페이지

[[hylafax-integration]] [[operations-and-deployment]] [[scheduler-and-storage]]
