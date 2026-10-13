---
title: E-mail to fax with Postfix 설정
type: source
updated: 2026-10-02
sources: [deploy/postfix/setup-email2fax.md]
verified: false
---

## 요약

메일을 팩스로 변환하는 Postfix 설정. `<number>@fax.example.com`으로 보낸 메일이 HylaFAX의 `faxmail` 을 통해 팩스가 된다. DNS MX 레코드, `/etc/passwd` 사용자, Postfix master.cf와 transport, 그리고 HylaFAX faxmail.conf 설정 6단계.

## 핵심 내용

### 0단계: 선행 조건
- DNS: 팩스 도메인(예: `fax.example.com`)이 이 호스트로 라우팅되어야 함(MX 레코드)
- `/etc/passwd`: 메일 사용자가 존재해야 함(예: `faxmail` 또는 `uucp`). NamiFAX에서 `FAXMAILUSER`로 같은 이름을 지정

### 1단계: `/etc/postfix/master.cf` 수정
파이프 서비스 추가. 송신 메일을 `faxmail` 사용자로 실행하는 명령으로 전달:

```
fax       unix  -       n       n       -       1       pipe
  flags= user=faxmail argv=/usr/bin/faxmail -d -n -NT ${user}
```

- `user=faxmail`: 명령을 이 사용자로 실행
- `argv=/usr/bin/faxmail -d -n -NT ${user}`: HylaFAX `faxmail` 실행, `${user}`는 수신 주소의 사용자명(예: `5551234`)

### 2단계: `/etc/postfix/transport` 작성
팩스 도메인을 위의 파이프 서비스로 라우팅:

```
fax.example.com    fax:localhost
```

그 후 postmap:

```bash
postmap /etc/postfix/transport
```

### 3단계: `/etc/postfix/main.cf` 수정
transport 맵 활성화 및 수신자 제한:

```
transport_maps = hash:/etc/postfix/transport
fax_destination_recipient_limit = 1
```

### 4단계: `/etc/hylafax/faxmail.conf` 설정
HylaFAX faxmail 동작 구성:

```
AutoCoverPage: false
TextPointSize: 12pt
Headers: Message-id Date Subject From
MailUser: faxmail
```

- `AutoCoverPage: false`: 자동 표지 없음(필요 시 켬)
- `TextPointSize: 12pt`: 텍스트 크기
- `Headers`: 메일 헤더에 포함할 항목
- `MailUser: faxmail`: 메일 사용자 이름(위의 `/etc/passwd` 사용자명과 일치)

### 5단계: Postfix 재로드
```bash
systemctl reload postfix
```

### 6단계: 검증
- 이 방식으로 제출한 작업은 `faxmail` 사용자 소유
- Outbox 페이지는 작업의 `mailaddr`(이메일 주소)로 사용자를 찾아 그 사용자에게만 표시
- NamiFAX에서 `FAXMAILUSER`를 위의 사용자명(예: `faxmail`)으로 같게 설정해야 메일 주소로 사용자 찾기 가능

## 문서가 주장하는 수치·상태

- **master.cf 파이프 개수**: 1개 추가. 기존 설정과 충돌 없음 가정
- **transport 항목**: 1개(`fax.example.com` → `fax:localhost`)
- **HylaFAX 실행 파일**: `/usr/bin/faxmail` (기본 위치 가정)
- **메일 사용자**: `/etc/passwd`에 존재해야 함

## 낡았을 가능성이 큰 부분

- **Postfix 버전 호환성**: 문서는 표준 Postfix 설정을 가정. 매우 오래된 버전이나 커스텀 빌드에서는 `pipe` 서비스나 `transport_maps` 문법이 다를 수 있음
- **HylaFAX `faxmail` 위치**: `/usr/bin/faxmail`가 기본 위치로 가정. 배포판이나 커스텀 설치에서는 다를 수 있음 (경로는 `BINARYDIR` 환경변수로도 지정 가능)
- **`fax.example.com` 도메인**: 예시 도메인. 실제 환경에서는 DNS MX 레코드 설정 필요 여부와 TTL 갱신 시간이 명시되지 않음
- **`AutoCoverPage: false`**: HylaFAX 기본값이 `true`일 수 있음. 실제 환경에서는 확인 필요
- **원본 `setup-postfix.sh` 마이그레이션**: 이 문서는 원본 스크립트를 이식했지만, 원본 스크립트 코드를 보여주지 않으므로 누락된 설정이 있을 수 있음 (원본 소스는 커밋 9408385의 `legacy/` 에서 복원 가능)
- **`mailaddr` 필드 신뢰성**: Outbox 페이지가 작업의 `mailaddr` 필드로 사용자를 찾는다고 가정. HylaFAX의 작업 포맷(`JobFmt`)이나 필드 이름 변경 시 동작 변경 가능

## 관련 주제 페이지

[[hylafax-integration]] [[operations-and-deployment]]
