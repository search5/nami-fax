# HylaFAX 연동 설치 가이드

NamiFAX와 HylaFAX를 연결하는 순서입니다. 파일은 `deploy/` 폴더에 있습니다. **이 저장소에서는 실제 HylaFAX에 붙여 시험하지
못했습니다.** 아래 순서는 원본 AvantFAX의 설치 스크립트(`debian-install.sh`, `setup-postfix.sh` 등; 원본 소스는 커밋 9408385 의 `legacy/` 에 있다)가 하던 일을 그대로
옮긴 것이고, 각 단계의 확인 방법을 함께 적었습니다. 운영 서버에 적용하기 전에 시험 서버에서 한 번 거치십시오.

경로 가정: NamiFAX는 `/opt/namifax`(가상환경 `.venv`), HylaFAX 스풀은 `/var/spool/hylafax`, 서비스 사용자는 `uucp`입니다.
다르면 `deploy/` 파일 안의 해당 부분을 바꾸십시오.

## 0. 환경 파일

`/etc/namifax.env`(모드 0640)에 DB 접속과 설정을 둡니다. 저장소의 파일들이 모두 이 한 파일을 읽습니다.

- systemd 서비스(`systemd/namifax.service`): `EnvironmentFile=-/etc/namifax.env`
  (`-` 때문에 파일이 없어도 시작은 합니다. 다만 그러면 `DATABASE_URL` 이 없어 현재 폴더의 SQLite 파일로 조용히 떨어지므로 꼭 만드십시오).
- cron(`deploy/cron.d/namifax`): cron 에는 `EnvironmentFile` 이 없어서 각 줄이 `sh -c 'set -a; . /etc/namifax.env; set +a; exec …'` 로 파일을 먼저 읽습니다.
- HylaFAX 훅 스크립트(`deploy/hylafax/bin/*`): `set -a; . /etc/namifax.env; set +a` 뒤에 `exec` 합니다.

**서식은 `KEY=value` 한 줄씩이며, `export` 와 값 뒤의 `#` 주석은 쓰지 마십시오.** systemd 와 셸이 같은 파일을 읽는데,
systemd 는 줄 끝 `#` 을 값의 일부로 읽습니다. 주석은 `#` 으로 시작하는 별도의 줄로 쓰십시오.
값에 `&` `;` `(` `)` `<` `>` `|` 공백이 들어 있으면(예: `?charset=utf8mb4&x=1` 이 붙은 DB 주소) **큰따옴표로 감싸십시오**: 큰따옴표는 systemd 와 셸이
똑같이 벗깁니다. 따옴표 없이 쓰면 셸은 `&` 에서 명령을 끊어 값이 비거나 잘립니다. 큰따옴표 안에는 `$` 백슬래시 역따옴표 `"` 를 넣지 마십시오.

```
DATABASE_URL=mysql+pymysql://avantfax:비밀번호@localhost/avantfax
NAMIFAX_SESSION_SECRET=<긴-무작위-문자열>
NAMIFAX_SECRET_KEY=<비밀저장소에-따로-보관>
# ENABLE_DID_ROUTING 은 훅과 웹이 같은 값을 써야 합니다
ENABLE_DID_ROUTING=0
FAXMAILUSER=faxmail
# WWWUSER 는 서비스를 실행하는 사용자
WWWUSER=uucp
```

HylaFAX가 기본 위치에 없으면 `HYLASPOOL`, `HYLAFAX_PREFIX`, `BINARYDIR`로 알려 줍니다(`sendfax`, `faxstat`, `faxinfo`,
`faxadduser`를 찾는 데 쓰입니다).

## 1. 훅 연결

1. `deploy/hylafax/bin/*`를 `/var/spool/hylafax/bin/`에 복사하고 실행 권한을 줍니다
   (`faxrcvd`, `dynconf`, `notify`, `faxcover`). 소유자는 HylaFAX가 훅을 실행하는 사용자(보통 `uucp`)입니다.
2. 각 모뎀 설정(`/etc/hylafax/config.ttyS0` 등)에 `deploy/hylafax/config.namifax`의 세 줄을 붙입니다.
   여러 모뎀이면 파일마다 붙입니다.
3. 서버 설정(`/var/spool/hylafax/etc/config`)에 `deploy/hylafax/hfaxd.conf.snippet`의 `JobFmt` 줄과
   `deploy/hylafax/etc-faxq.snippet`의 `NotifyCmd`, `CoverCmd` 줄을 붙입니다.
   **`JobFmt`는 NamiFAX가 읽는 열 순서와 같아야 합니다.** 다르면 출력함 목록이 어긋나거나 비어 보입니다.
4. HylaFAX 재시작: `systemctl restart hylafax`(배포판에 따라 `faxq`, `hfaxd`, `faxgetty`).

확인: `sudo -u uucp /var/spool/hylafax/bin/dynconf ttyS0 5551234` 가 아무것도 출력하지 않고 끝나야 합니다(차단 번호면
`RejectCall: true`). 시스템 로그 화면에 `dynconf> checking CallID1 …` 줄이 남습니다.

## 2. 웹 서비스

- 최상위 `systemd/namifax.service`(`deploy/` 아래가 아닙니다)를 `/etc/systemd/system/`에 두고 `systemctl daemon-reload && systemctl enable --now namifax`. 이 서비스는 `/etc/namifax.env` 를 읽습니다(0단계).
- 앞단 웹 서버: `deploy/nginx/namifax.conf` 또는 `deploy/apache/namifax.conf`. HTTPS를 쓰면 ini 의 `session.secure = true` 가 필요한데, `namifax serve` 는 ini 를 **옵션을 줄 때만** 읽습니다. 서비스 파일의 `ExecStart` 를 `namifax serve --config /etc/namifax/production.ini` 로 바꾸거나 환경 파일에 `NAMIFAX_INI=/etc/namifax/production.ini` 를 적으십시오(ini 의 `[app:main]` 에서 `session.secret`, `session.secure`, `csrf.trusted_origins`, `secret.key`, `sqlalchemy.url` 을 읽습니다. `pserve production.ini` 로 띄워도 같습니다).
  프록시 뒤에서는 `X-Forwarded-Host`를 넘겨야 변경 요청의 출처 검사가 통과합니다.
- 첫 관리자: `namifax createuser -u admin -e you@example.com`.

## 3. 사용자 동기화 (선택)

HylaFAX 서버(`hfaxd`)에 사용자 이름이 등록돼 있어야 `faxrm`, `faxalter`가 그 사용자의 작업을 다룰 수 있습니다. 원본은 계정을
만들거나 비밀번호를 바꿀 때마다 `faxadduser`/`faxdeluser`를 `sudo`로 실행했습니다. 같은 동작을 켜려면:

1. `deploy/sudoers.d/namifax`를 `/etc/sudoers.d/namifax`로 복사(모드 0440, `visudo -cf`로 확인). 서비스 사용자 이름을 맞추십시오.
2. `/etc/namifax.env`에 `HYLAFAX_USER_SYNC=1`.
3. `systemd/namifax.service`의 `NoNewPrivileges=true`를 `false`로 바꾸십시오. 켜져 있으면 `sudo`가 동작하지 않습니다.

`faxadduser`는 비밀번호를 명령줄 인자(`-p`)로만 받으므로, 실행되는 짧은 순간 같은 서버의 다른 사용자가 `ps`로 볼 수 있습니다
(원본과 같은 한계입니다). 서버에 다른 사용자가 없는 전용 장비에서 쓰십시오. 끄면(기본) 아무것도 실행하지 않습니다.

## 4. 주기 작업

**관리자 > 예약 작업**(`/admin/scheduler`; `/admin/maintenance` 는 없습니다)에서 설정합니다. 내장 스케줄러가 돌리는 작업은 4종(`tmp`, `inbox`, `lifecycle`, `phonebook`)입니다: 임시 폴더 정리(일수·시각), 받은 팩스함의 오래된 팩스를 보관함으로 이동(일수·시각, 기본 꺼짐), 보존 기간 정책 적용(정책 값은 Storage & Cloud 화면), 전화번호부 내보내기(주기). 각 작업은 "지금 실행"과 마지막 실행 결과를 보여 줍니다. 저장한 변경은 실행 중인 스케줄러가 1분 안에 반영하며(재시작 불필요), 화면 위쪽에 스케줄러 상태와 **정지/시작** 버튼이 있습니다. 정지하면 APScheduler 엔진 자체를 종료해 어떤 작업도 저절로 돌지 않고(프로세스는 남아 15초마다 시작 요청을 확인), 시작하면 엔진을 다시 띄웁니다. 정지 상태는 DB에 저장되어 재시작 뒤에도 유지됩니다. 스케줄러는 웹 서비스 프로세스 안에서만 돕니다(`NAMIFAX_ENABLE_SCHEDULER=1`, 기본값). 별도 스케줄러 서비스는 없습니다. 같은 DB에 웹 서비스를 둘 이상 띄우지 마십시오(스케줄러가 겹쳐 돕니다). 아래 cron 방식은 스케줄러를 쓰지 않을 때의 대안입니다.


`deploy/cron.d/namifax`를 `/etc/cron.d/namifax`로 복사하고 보존 기간을 정하십시오.
내장 스케줄러(`NAMIFAX_ENABLE_SCHEDULER=1`)는 위 4종을 돌립니다(받은 팩스함 보관 `inbox` 는 기본 꺼짐, `lifecycle` 은 저장 정책을
저장했을 때). 다만 **보관함의 오래된 팩스를 날짜로 지우는 `-d` 에 정확히 대응하는 스케줄러 작업은 없습니다**(비슷한 것은 저장 정책의
`full_retention_days`). `-d` 가 필요하면 cron에 적으십시오. 아무것도 켜지 않으면 팩스가 영원히 쌓입니다. cron 줄은 환경 파일을
읽도록 `sh -c` 로 감싸져 있으니 줄을 고칠 때 그 형태를 유지하십시오.

## 5. 이메일로 팩스 보내기 (선택)

`deploy/postfix/setup-email2fax.md`. 원본의 `setup-postfix.sh`가 하던 설정이며, 이 저장소의 스크립트는 시스템 파일을 직접
고치지 않으므로 적용 전에 내용을 읽고 직접 넣으십시오.

## 5-1. 가상 프린터로 팩스 보내기 (선택)
인쇄한 문서를 팩스로 보내는 CUPS 백엔드입니다. `deploy/cups/namifax-fax` 를 `/usr/lib/cups/backend/namifax-fax` 로 복사하고(소유자 root, 권한 0700),
CUPS 에서 장치 주소 `namifax-fax:/` 로 프린터를 추가하십시오. 인쇄 내용에 `[[FAX: 02-123-4567]]` 같은 태그가 있어야 하고, 작업은 CUPS 사용자 이름으로
`sendfax` 에 넘겨집니다(태그가 없으면 임시 폴더에 초안으로만 저장되고, `sendfax` 가 실패하면 CUPS 에 실패로 돌려줍니다). 확인: `echo "[[FAX: 123]]" | namifax print-in 1 사용자 제목 1 ""`.
**이 저장소에서는 실제 CUPS 와 HylaFAX 에 붙여 시험하지 못했습니다**(백엔드 스크립트의 인자 전달과 `namifax print-in` 의 동작만 시험됨).

## 6. 파일 권한

- 보관 폴더(`/var/spool/hylafax/archive`, `…/sent`)는 훅을 실행하는 사용자와 웹 서비스 사용자가 모두 쓸 수 있어야 합니다
  (같은 `uucp`로 돌리면 가장 단순합니다).
- 임시 폴더(`AVANTFAX_TMPDIR`)도 같습니다.
- `/etc/namifax.env`는 서비스 사용자만 읽게(0640, 소유 `root:uucp`) 하십시오. systemd 는 root 로 읽지만 cron·훅은 `uucp` 로 읽습니다. DB 비밀번호와 세션 키가 들어 있습니다.

## 7. 설치 뒤 점검 순서

1. 로그인 → 설정 → 시스템 로그에 오류가 없는지.
2. 관리자 > 모뎀에서 모뎀을 만들고 상태가 `Running and idle`로 나오는지(`faxstat`을 읽습니다).
3. 시험 팩스를 보내고 출력함에 작업이 나오는지, 완료 뒤 `notify`가 보관함에 보낸 팩스를 만드는지.
4. 시험 팩스를 받고 `faxrcvd`가 받은 팩스함에 올리는지(썸네일, PDF, 메일 알림).
5. 관리자 화면 대시보드의 HylaFAX 버전이 표시되는지(`faxstat -i`).
