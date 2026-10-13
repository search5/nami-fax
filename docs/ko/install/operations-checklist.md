# 운영 전·운영 중 점검 목록

NamiFAX를 운영 환경에 올리기 전에 한 번, 그리고 운영 중 주기적으로 확인할 사항입니다. 코드로 보장되는 동작은
`ARCHITECTURE.md` 17장(삭제됨, 커밋 01f2f64 에서 복원)에 있고, 이 문서는 **사람이 설정하거나 판단해야 하는 것**만 모았습니다.

## 1. 첫 기동 전 (한 번)

| 항목 | 방법 | 이유 |
|---|---|---|
| 환경 파일 배선 | `/etc/namifax.env`(`KEY=value` 한 줄씩, 따옴표·`export`·줄 끝 주석 없음)를 두면 systemd 서비스(`EnvironmentFile=-`), cron 줄(`sh -c 'set -a; . /etc/namifax.env; …'`), HylaFAX 훅 스크립트(`set -a; . …`)가 모두 같은 파일을 읽습니다. | 파일이 전달되지 않으면 `DATABASE_URL` 이 없어 현재 폴더의 SQLite(`namifax.db`)로 조용히 떨어집니다. |
| 세션 서명 키 고정 | `session.secret`(ini) 또는 환경변수 `NAMIFAX_SESSION_SECRET` | 없으면 프로세스마다 임의 키를 쓰고 경고만 남깁니다. 워커가 여러 개거나 재시작하면 2FA 중간 단계 상태와 로그인 흐름이 끊깁니다. |
| HTTPS면 보안 쿠키 | ini 의 `session.secure = true`. ini 는 `namifax serve --config <파일.ini>` 또는 환경변수 `NAMIFAX_INI` 로 읽힙니다(`pserve` 로 띄워도 됩니다). 옵션이 없으면 ini 를 읽지 않습니다. | 기본값은 false입니다. `csrf.trusted_origins`, `secret.key` 도 같은 방식입니다. |
| 자격증명 암호화 키 | 환경변수 `NAMIFAX_SECRET_KEY`(또는 ini `secret.key`)를 정하고 `namifax encrypt-secrets`를 한 번 실행 | 클라우드 키, SMTP 비밀번호, 2FA 시드를 암호화해 저장합니다. **키를 잃으면 암호화된 값을 복구할 수 없습니다.** 비밀 저장소에 따로 보관하십시오. |
| 첫 관리자 | `namifax createuser -u <이름> -e <메일>` (비밀번호는 `-p`, `NAMIFAX_NEW_USER_PASSWORD` 또는 프롬프트) | 서버 DB(MySQL, MariaDB, PostgreSQL)에는 데모 계정이 만들어지지 않습니다. 내장 기본 비밀번호도 없습니다. |
| SMTP 게이트웨이 | 관리자 화면에서 설정 | **비밀번호 찾기**, 수신 팩스 메일 전달, 알림 메일이 모두 이 설정을 씁니다. 메일을 보낼 수 없으면 비밀번호 찾기는 "Email failed to send"를 보여 주고 기존 비밀번호는 그대로 둡니다. |
| 데모 데이터 끄기 | `NAMIFAX_DEMO_DATA`를 켜지 않기 | SQLite에서만 동작하는 옵트인입니다. SQLite는 운영 DB가 아닙니다. |
| 주기 작업 | 내장 스케줄러(`/admin/scheduler`)가 임시 폴더 정리(`tmp`), 받은 팩스함 보관 이동(`inbox`, 기본 꺼짐), 저장 정책 실행(`lifecycle`), 전화번호부 내보내기(`phonebook`) 4종을 돌립니다. | 보관함의 오래된 팩스를 날짜로 지우는 `cron -d` 에 정확히 대응하는 작업은 없으므로 필요하면 `deploy/cron.d/namifax` 에 적습니다. |
| 비밀번호 해시 | 기본 Argon2id. 원본 PHP와 한 DB를 함께 쓰는 동안은 `NAMIFAX_PASSWORD_HASH=md5` | 원본은 Argon2id를 읽지 못합니다([migration.md](migration.md) 4.5). |

### SAML 로그인과 권한

- 관리자 > SAML에서 IdP 주소·인증서를 저장하고 사용을 켭니다. 설정하기 전에는 로그인 화면에 버튼이 나오지 않습니다. 응답은 IdP가 **서명**한 것만 받습니다(서명 알고리즘 SHA-256 이상).
- "권한을 IdP에서 가져오기"를 켜면, 로그인할 때마다 응답의 역할 속성(기본 `Role`)에 따라 관리자·슈퍼유저·삭제·아무 회선 권한이 정해집니다. 회선·카테고리·DID 경로는 속성 이름을 적은 항목만 관리하며, 목록에 있는 이름이 namifax에 없으면 무시합니다. 역할을 빼면 다음 로그인에 권한도 내려가고, 여기서 손으로 바꾼 값은 덮어써집니다.
- Keycloak에서는 클라이언트의 매퍼로 `Role`(역할 목록, 다중값)과 `modems` 같은 사용자 속성(다중값)을 응답에 싣습니다. 사용자 속성은 realm의 "unmanaged attributes"가 켜져 있어야 저장됩니다.
- 실제 Keycloak 26 컨테이너로 로그인, 위조·재사용 거부, 역할 부여·회수, 회선 속성 반영을 확인했습니다. Okta·Entra ID 등 다른 IdP와의 연동은 시험하지 못했습니다.

## 2. HylaFAX 연동 (실제 서버에서만 확인 가능)

원본 `submit_fax()`와 같은 명령줄을 만드는 것은 테스트로 확인했지만, **실제 HylaFAX와의 연결은 이 저장소에서 검증하지 못했습니다.**

- `sendfax`가 `PATH`에 있어야 합니다. 없으면 `NAMIFAX_QUEUE_SIMULATION`이 꺼진 환경에서 전송이 실패로 표시됩니다(켜져 있거나 `/var/spool/hylafax`가 없으면 시뮬레이션).
- 커버페이지: `AVANTFAX_INSTALLDIR/images/<커버 파일>` 경로에 커버 파일이 있어야 하고, 실행 파일은 `NAMIFAX_FAXCOVER`(기본 `python -m namifax.cli.faxcover`)입니다.
- `DEFAULT_TSI_ID`, `ENABLE_DID_ROUTING`(수신 훅과 웹이 같은 값을 써야 합니다), `AVANTFAX_ARCHIVE`, `AVANTFAX_TMPDIR`.
- 첫 전송 후 확인: 출력함에 작업이 나타나는지, `sendfax` 출력의 `request id is N`을 작업 번호로 읽는지.
- 커버페이지만 보내는 경우 임시 `.ps` 파일이 전송 뒤 지워지는지(`AVANTFAX_TMPDIR` 또는 시스템 임시 폴더).

## 3. 기존 AvantFAX에서 옮길 때

절차 전체, 설정 대응표, 웹 서버의 옛 주소 리다이렉트, 예행연습 결과는 [migration.md](migration.md)에 있습니다. 아래는 요점만 남긴 것입니다.

- 원본 MySQL/MariaDB DB에 그대로 붙습니다(`ARCHITECTURE.md`(삭제됨, 커밋 01f2f64 에서 복원) 17.5a). 큰 `FaxArchive` 테이블은 **첫 기동에서 검색용 인덱스를 만드느라 오래 걸릴 수 있습니다.** 소요 시간은 측정하지 않았으니 점검 시간대에 첫 기동을 하십시오.
- **PHP 세션과 로그인 쿠키는 이어지지 않습니다.** 이전 직후 모든 사용자가 다시 로그인해야 합니다.
- 마이그레이션 예행연습 도구 `tools/migration_rehearsal/` 은 저장소에 남아 있지만 `legacy/` 를 `git checkout 9408385 -- legacy` 로 되살리기 전에는 실행되지 않습니다.
- 원본 DB는 첫 기동 전에 백업하십시오(스키마 보정이 일어납니다).
- 이전 버전의 포트가 만든 SQLite 파일은 시작 시 보정되지만, 아주 초기 버전의 것은 일부만 보정됩니다. 운영 데이터가 아니라면 지우고 새로 만드십시오.
- 기존 보관 팩스 파일은 `namifax import-archive`로 들여옵니다. 사용자는 `namifax import-users`.

## 4. 보안 판단이 필요한 것

### 비밀번호 찾기(원본 `forgot.php` 방식)
원본과 같게 **이메일 주소로 새 임시 비밀번호를 만들어 메일로 보내고, 그 비밀번호는 다음 로그인에서 바꿔야 합니다.** 원본의 성질을 그대로 가지므로 알고 계셔야 합니다.

- 누구든 다른 사람의 이메일 주소만 알면 그 계정의 **기존 비밀번호를 무효로 만들 수 있습니다**(임시 비밀번호가 본인 메일로 가므로 탈취는 아니지만 로그인을 방해할 수 있습니다). 막으려면 앞단(리버스 프록시)에서 `/forgot`에 요청 횟수 제한을 두십시오.
- 없는 주소를 넣으면 "해당 사용자가 없다"고 알려 줍니다(원본 동작). 계정 존재 여부가 노출됩니다.
- 원본과 다른 점: 새 비밀번호를 **시스템 로그에 남기지 않습니다**(원본은 평문으로 남겼습니다). 메일 발송이 실패하면 **기존 비밀번호를 되돌립니다**(원본은 잠긴 채로 남았습니다). 삭제된 계정은 찾지 않습니다.
- 2단계 인증을 켠 계정은 임시 비밀번호로 로그인해도 인증 코드를 요구합니다.

### 알려진 한계 (수정하지 않음)
- SAML 로그인은 앱의 2FA를 거치지 않습니다. 2단계 인증은 IdP가 책임진다는 **확정된 정책**입니다.
- 원본 보관함 검색과 받은 팩스함의 권한 규칙은 원본을 실제로 실행해 일치를 확인했습니다. 다만 대기열 작업 수정(`/ajax/faxalter`)은 원본처럼 로그인만 확인합니다.

## 5. 운영 중 주기 점검

- 시스템 로그에서 `Access denied to … fax` (권한 없는 접근 시도), `Attempt to reset password for email` (비밀번호 찾기 실패)를 가끔 확인하십시오.
- TOTP는 5회 실패하면 일정 시간 잠깁니다. 기기와 복구 코드를 모두 잃은 사용자는 `namifax reset-2fa <사용자>`로 풀어 줍니다.
- 설정에서 지운 모뎀의 팩스는 원본과 같게 **받은 팩스함에 보이지 않습니다**(슈퍼유저 포함). 모뎀을 지우기 전에 받은 팩스함을 비우거나 보관하십시오.
- 키 회전을 하려면 새 `NAMIFAX_SECRET_KEY`로 바꾸기 전에 기존 키로 값을 읽을 수 있는 상태에서 작업하십시오(키를 잃으면 복구 불가).

## 6. 아직 하지 않은 일

- 출력함은 원본과 같은 열·버튼으로 맞췄지만 **가짜 `faxstat` 출력으로만** 확인했습니다. 실제 HylaFAX의 작업 목록 형식(`JobFmt`에 `Mailaddr` 열이 있어야 합니다)과 `faxrm`·`faxalter`의 소유자 권한 동작은 HylaFAX가 있는 서버에서 확인해야 합니다. 웹 서버 사용자와 faxmail 사용자 이름은 환경변수 `WWWUSER`(기본 `www-data`; 원본 기본은 `apache`)와 `FAXMAILUSER`(기본 `faxmail`)로 지정합니다. HylaFAX 작업 소유자가 이 이름이면 메일 주소로 사용자를 찾습니다.
