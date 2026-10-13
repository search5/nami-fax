---
title: 운영 전·운영 중 점검 목록
type: source
updated: 2026-10-13
sources: [docs/ko/install/operations-checklist.md, docs/en/install/operations-checklist.md]
verified: false
---

> 원본은 `docs/ko/install/operations-checklist.md`(2026-10-13 에 MkDocs 구조로 이동. 이전 경로 `docs/OPERATIONS_CHECKLIST.md`)다. 영문판 `docs/en/install/operations-checklist.md` 가 있으나 이 요약은 한국어 원문 기준이다.

## 요약

NamiFAX를 운영에 올리기 전 한 번, 운영 중 주기적으로 확인할 사항. 코드로 보장되는 동작은 삭제된 `ARCHITECTURE.md` 17장(커밋 `01f2f64` 에서 복원)에 있고, 이 문서는 **사람이 설정하거나 판단해야 하는 것**만 모았다. 첫 기동 전 점검, SAML 로그인과 권한, HylaFAX 연동, AvantFAX 이전 요점, 보안 판단(비밀번호 찾기), 운영 중 점검, 아직 하지 않은 일로 구성된다.

## 핵심 내용

### 1장: 첫 기동 전 (한 번)

| 항목 | 방법 | 이유·주의 |
|---|---|---|
| 환경 파일 배선 | `/etc/namifax.env`(`KEY=value` 한 줄씩, 따옴표·`export`·줄 끝 주석 없음)를 두면 systemd(`EnvironmentFile=-`), cron 줄(`sh -c 'set -a; . /etc/namifax.env; …'`), 훅 스크립트(`set -a; . …`)가 같은 파일을 읽음 | 전달되지 않으면 `DATABASE_URL` 이 없어 현재 폴더 SQLite(`namifax.db`)로 조용히 떨어짐 |
| 세션 서명 키 고정 | ini `session.secret` 또는 `NAMIFAX_SESSION_SECRET` | 없으면 프로세스마다 임의 키 + 경고만. 워커가 여럿이거나 재시작하면 2FA 중간 단계와 로그인 흐름이 끊김 |
| HTTPS면 보안 쿠키 | ini `session.secure = true`. ini 는 `namifax serve --config <파일.ini>` 또는 `NAMIFAX_INI` 로 읽힘(`pserve` 도 가능), 옵션이 없으면 ini 를 읽지 않음 | 기본값 false. `csrf.trusted_origins`, `secret.key` 도 같은 방식 |
| 자격증명 암호화 키 | `NAMIFAX_SECRET_KEY`(또는 ini `secret.key`)를 정하고 `namifax encrypt-secrets` 한 번 | 클라우드 키, SMTP 비밀번호, 2FA 시드를 암호화 저장. **키를 잃으면 복구 불가**, 비밀 저장소에 따로 보관 |
| 첫 관리자 | `namifax createuser -u <이름> -e <메일>`(비밀번호는 `-p`, `NAMIFAX_NEW_USER_PASSWORD` 또는 프롬프트) | 서버 DB(MySQL, MariaDB, PostgreSQL)에는 데모 계정도 내장 기본 비밀번호도 없음 |
| SMTP 게이트웨이 | 관리자 화면에서 설정 | **비밀번호 찾기**, 수신 팩스 메일 전달, 알림 메일이 모두 사용. 메일을 못 보내면 비밀번호 찾기는 "Email failed to send" 를 보이고 기존 비밀번호 유지 |
| 데모 데이터 | `NAMIFAX_DEMO_DATA` 를 켜지 않음 | SQLite 에서만 동작하는 옵트인. SQLite 는 운영 DB 아님 |
| 주기 작업 | 내장 스케줄러(`/admin/scheduler`)가 4종을 돌림: `tmp`(임시 폴더 정리), `inbox`(받은 팩스함 보관 이동, 기본 꺼짐), `lifecycle`(저장 정책 실행), `phonebook`(전화번호부 내보내기) | 보관함의 오래된 팩스를 날짜로 지우는 `cron -d` 에 정확히 대응하는 작업은 없으므로 필요하면 `deploy/cron.d/namifax` 에 기입 |
| 비밀번호 해시 | 기본 Argon2id. 원본 PHP와 한 DB를 함께 쓰는 동안 `NAMIFAX_PASSWORD_HASH=md5` | 원본은 Argon2id 를 읽지 못함([[migrating-from-avantfax3]] 4.5) |

**SAML 로그인과 권한**
- 관리자 > SAML 에서 IdP 주소·인증서를 저장하고 사용을 켬. 설정 전에는 로그인 화면에 버튼이 없음. IdP 가 **서명**한 응답만 받음(SHA-256 이상)
- "권한을 IdP에서 가져오기"를 켜면 로그인할 때마다 응답의 역할 속성(기본 `Role`)에 따라 관리자·슈퍼유저·삭제·아무 회선 권한이 정해짐. 회선·카테고리·DID 경로는 속성 이름을 적은 항목만 관리하고 namifax 에 없는 이름은 무시. 역할을 빼면 다음 로그인에 권한도 내려가며 손으로 바꾼 값은 덮어써짐
- Keycloak: 클라이언트 매퍼로 `Role`(다중값)과 `modems` 같은 사용자 속성(다중값)을 응답에 실음. 사용자 속성은 realm 의 "unmanaged attributes" 가 켜져 있어야 저장됨
- 실제 Keycloak 26 컨테이너로 로그인, 위조·재사용 거부, 역할 부여·회수, 회선 속성 반영을 확인. Okta·Entra ID 등은 시험하지 못함

### 2장: HylaFAX 연동 (실제 서버에서만 확인 가능)
- 원본 `submit_fax()` 와 같은 명령줄을 만드는 것은 테스트로 확인했으나 **실제 HylaFAX 연결은 이 저장소에서 검증하지 못함**
- `sendfax` 가 `PATH` 에 있어야 함. 없으면 `NAMIFAX_QUEUE_SIMULATION` 이 꺼진 환경에서 전송이 실패로 표시(켜져 있거나 `/var/spool/hylafax` 가 없으면 시뮬레이션)
- 커버페이지: `AVANTFAX_INSTALLDIR/images/<커버 파일>` 에 파일이 있어야 하고 실행 파일은 `NAMIFAX_FAXCOVER`(기본 `python -m namifax.cli.faxcover`)
- 확인할 설정: `DEFAULT_TSI_ID`, `ENABLE_DID_ROUTING`(수신 훅과 웹이 같은 값), `AVANTFAX_ARCHIVE`, `AVANTFAX_TMPDIR`
- 첫 전송 후: 출력함에 작업이 나오는지, `sendfax` 출력의 `request id is N` 을 작업 번호로 읽는지. 커버페이지만 보낼 때 임시 `.ps` 가 전송 뒤 지워지는지

### 3장: 기존 AvantFAX에서 옮길 때
- 절차 전체·설정 대응표·리다이렉트·예행연습 결과는 [[migrating-from-avantfax3]]. 여기에는 요점만:
- 원본 MySQL/MariaDB DB에 그대로 붙음(`ARCHITECTURE.md` 17.5a, 삭제됨). 큰 `FaxArchive` 는 **첫 기동에서 검색용 인덱스를 만드느라 오래 걸릴 수 있음**, 소요 시간 미측정이므로 점검 시간대에 첫 기동
- **PHP 세션·로그인 쿠키는 이어지지 않음**: 이전 직후 모든 사용자 재로그인
- `tools/migration_rehearsal/` 은 남아 있으나 `git checkout 9408385 -- legacy` 로 `legacy/` 를 되살리기 전에는 실행되지 않음
- 원본 DB는 첫 기동 전에 백업(스키마 보정). 이전 버전 포트가 만든 SQLite 는 시작 시 보정되지만 아주 초기 버전은 일부만 보정되므로 운영 데이터가 아니면 새로 만듦
- 기존 보관 팩스는 `namifax import-archive`, 사용자는 `namifax import-users`

### 4장: 보안 판단이 필요한 것

**비밀번호 찾기(원본 `forgot.php` 방식)**: 이메일 주소로 새 임시 비밀번호를 만들어 메일로 보내고, 다음 로그인에서 바꿔야 함.
- 다른 사람의 이메일 주소만 알면 그 계정의 **기존 비밀번호를 무효로 만들 수 있음**(임시 비밀번호가 본인 메일로 가므로 탈취는 아니지만 로그인 방해 가능). 앞단 리버스 프록시에서 `/forgot` 요청 횟수 제한 권장
- 없는 주소는 "해당 사용자가 없다"고 알림(원본 동작) → 계정 존재 여부 노출
- 원본과 다른 점: 새 비밀번호를 **시스템 로그에 남기지 않음**(원본은 평문), 메일 발송 실패 시 **기존 비밀번호 복원**(원본은 잠긴 채), 삭제된 계정은 찾지 않음
- 2단계 인증을 켠 계정은 임시 비밀번호로 로그인해도 인증 코드를 요구

**알려진 한계(수정하지 않음)**
- SAML 로그인은 앱의 2FA 를 거치지 않음. 2단계 인증은 IdP 책임이라는 **확정된 정책**
- 원본 보관함 검색과 받은 팩스함 권한 규칙은 원본을 실제로 실행해 일치 확인. 다만 대기열 작업 수정(`/ajax/faxalter`)은 원본처럼 로그인만 확인

### 5장: 운영 중 주기 점검
- 시스템 로그의 `Access denied to … fax`(권한 없는 접근 시도), `Attempt to reset password for email`(비밀번호 찾기 실패) 가끔 확인
- TOTP 는 5회 실패하면 일정 시간 잠김. 기기와 복구 코드를 모두 잃으면 `namifax reset-2fa <사용자>`
- 설정에서 지운 모뎀의 팩스는 원본처럼 **받은 팩스함에 보이지 않음**(슈퍼유저 포함). 모뎀 삭제 전에 받은 팩스함을 비우거나 보관
- 키 회전은 새 `NAMIFAX_SECRET_KEY` 로 바꾸기 전에 기존 키로 값을 읽을 수 있는 상태에서 진행(키를 잃으면 복구 불가)

### 6장: 아직 하지 않은 일
- **번역**: 한국어만 새 문구까지 채움(빠진 번역 0개, 테스트 보장). 나머지 23개 언어에서는 이번에 추가된 화면 문구(SAML, 프린터, 스토리지, 패스키, 2FA, 보내기 폼 새 항목, vCard 업로드, 비밀번호 찾기, 작업 수정, 입력창 예시 등 약 190개)가 영어로 보임. 언어는 `?lang=코드` 또는 `_LOCALE_` 쿠키로 선택
- **출력함**: 원본과 같은 열·버튼이지만 **가짜 `faxstat` 출력으로만** 확인. 실제 HylaFAX 작업 목록 형식(`JobFmt` 에 `Mailaddr` 열 필요)과 `faxrm`·`faxalter` 소유자 권한은 HylaFAX 서버에서 확인 필요. 웹 서버 사용자·faxmail 사용자 이름은 `WWWUSER`(기본 `www-data`, 원본 기본 `apache`)와 `FAXMAILUSER`(기본 `faxmail`)로 지정하며, HylaFAX 작업 소유자가 이 이름이면 메일 주소로 사용자를 찾음

## 문서가 주장하는 수치·상태

- 한국어 번역 빠진 문구 0개(테스트로 보장), 다른 23개 언어는 새 화면 문구 약 190개가 영어.
- SAML: Keycloak 26 컨테이너로 확인됨, Okta·Entra ID 는 미시험.
- 실제 HylaFAX 연동과 출력함 열·권한: 이 저장소에서 검증 안 함(가짜 `faxstat` 만).
- TOTP 5회 실패 시 잠김.

## 낡았을 가능성이 큰 부분

- 삭제된 `ARCHITECTURE.md` 17장을 가리키므로 코드와의 동기 여부는 이 문서만으로 확인할 수 없다(커밋 `01f2f64` 에서 복원).
- 번역 개수(약 190개 등)는 작성 시점 값이다.
- 스케줄러 4종 서술은 현재 문서와 일치하며, 스케줄러는 웹 프로세스 안에서만 돈다(별도 `namifax scheduler` 는 제거됨, [[scheduler-and-storage]]).
- `JobFmt` 열 순서, `faxrm`·`faxalter` 권한, Okta·Entra ID 연동은 해당 환경에서만 확인할 수 있다.

## 관련 주제 페이지

[[authentication-and-security]] [[hylafax-integration]] [[migration-from-avantfax]] [[operations-and-deployment]] [[scheduler-and-storage]] [[i18n-and-ui]]
