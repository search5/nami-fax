# 이메일로 팩스 보내기 (Postfix)

`<번호>@fax.example.com` 으로 보낸 메일을 팩스로 바꾸는 설정입니다. 변환은 NamiFAX 가 아니라 HylaFAX 의 `faxmail` 이 맡고, NamiFAX 는 접수된 작업을 **누구의 팩스로 보여 줄지**만 정합니다.

!!! warning "시험 범위"
    이 저장소는 실제 HylaFAX 에 붙여 시험하지 못했습니다([HylaFAX 연동 설치](hylafax.md)와 같습니다). Postfix → `faxmail` → `sendfax` 구간은 NamiFAX 코드가 아니라 외부 프로그램이며, NamiFAX 쪽에서는 소유자 매핑 로직만 시험되어 있습니다. 운영 서버에 적용하기 전에 시험 서버에서 먼저 확인하십시오.

## 동작 방식

1. 외부에서 `<팩스번호>@fax.example.com` 으로 메일이 도착합니다. 받는 주소의 앞부분이 수신 팩스 번호가 됩니다.
2. Postfix 는 이 도메인의 메일을 `transport_maps` 에 따라 `fax` 서비스(`master.cf` 의 `pipe`)로 넘깁니다.
3. `pipe` 가 지정한 사용자(`faxmail`)로 HylaFAX 의 `faxmail` 을 실행하면, `faxmail` 이 메일 본문과 첨부를 팩스 문서로 바꿔 `sendfax` 로 대기열에 넣습니다.
4. 이렇게 접수된 작업의 소유자는 `faxmail` 입니다. NamiFAX 의 보낸 팩스함과 완료 알림(`notify`)은 소유자가 `FAXMAILUSER`(또는 웹 서비스 사용자 `WWWUSER`)이면 작업의 `mailaddr`(보낸 사람의 이메일)로 사용자를 찾아 그 사람의 팩스로 보여 줍니다.

## 준비

- 팩스용 도메인(여기서는 `fax.example.com`)의 MX 레코드가 이 서버를 가리켜야 합니다.
- 메일 사용자(`faxmail` 또는 `uucp` 등)가 `/etc/passwd` 에 있어야 합니다.
- `/etc/namifax.env` 의 `FAXMAILUSER` 를 아래 `master.cf` 의 `user=` 와 같은 이름으로 맞춥니다(기본값 `faxmail`).

```
FAXMAILUSER=faxmail
```

## Postfix 설정

이 저장소는 시스템 파일을 자동으로 고치지 않으므로 아래를 직접 넣으십시오. 명령과 설정은 `deploy/postfix/setup-email2fax.md` 와 같습니다.

1. `/etc/postfix/master.cf`:

       fax       unix  -       n       n       -       1       pipe
         flags= user=faxmail argv=/usr/bin/faxmail -d -n -NT ${user}

2. `/etc/postfix/transport`:

       fax.example.com    fax:localhost

   그런 다음 `postmap /etc/postfix/transport` 를 실행합니다.

3. `/etc/postfix/main.cf`:

       transport_maps = hash:/etc/postfix/transport
       fax_destination_recipient_limit = 1

4. `/etc/hylafax/faxmail.conf`:

       AutoCoverPage: false
       TextPointSize: 12pt
       Headers: Message-id Date Subject From
       MailUser: faxmail

5. `systemctl reload postfix`

## 보낸 사람과 사용자 매핑 (`FAXMAILUSER`)

- 이 방식으로 접수된 작업은 `faxmail` 소유로 큐에 들어갑니다. **보내기** 화면에서 낸 작업과 달리 NamiFAX 사용자 이름이 소유자가 아닙니다.
- 발신함(Outbox)은 작업의 `mailaddr` 가 NamiFAX 사용자의 이메일과 같으면 그 사용자에게 작업을 보여 줍니다. 그래서 **NamiFAX 에 등록된 이메일 주소로 메일을 보내야** 본인 팩스로 보입니다.
- `FAXMAILUSER` 가 Postfix `user=` 와 다르면 소유자 매핑이 맞지 않아 작업이 사용자에게 연결되지 않습니다.
- 팩스가 끝났을 때의 성공·실패 메일도 같은 규칙으로 보낸 사람을 찾습니다.

## 확인

```sh
# 1) Postfix 설정 다시 읽기와 transport 확인
postmap -q fax.example.com /etc/postfix/transport      # fax:localhost 가 나와야 합니다
# 2) 시험 메일을 보냅니다(번호는 시험 회선 번호로 바꿉니다)
echo "test" | mail -s "test" 0212345678@fax.example.com
# 3) 접수 확인
faxstat -s                                             # 대기열에 작업이 보여야 합니다
tail /var/log/mail.log                                 # 배포판에 따라 /var/log/maillog
```

NamiFAX 의 **발신함**에서 그 작업이 보이는지도 확인하십시오(보낸 사람의 이메일이 NamiFAX 사용자 이메일과 같아야 합니다).

## 보안 참고

- 팩스 도메인으로 오는 메일은 누구든 팩스를 만들 수 있습니다. 열린 중계(open relay)가 되지 않게 하고, 외부에 노출한다면 발신자 제한(허용 목록, SMTP 인증, 사내망 한정)을 Postfix 쪽에서 반드시 거십시오. NamiFAX 는 이 구간의 발신자를 검증하지 않습니다.
- `fax_destination_recipient_limit = 1` 은 메일 한 통이 `faxmail` 한 번 호출로 한 수신처만 처리하게 합니다. 빼지 마십시오.
- `faxmail` 사용자 계정에는 로그인 셸이 필요 없습니다.
- 스팸이 팩스 요금으로 이어질 수 있으므로 팩스 회선의 발신 제한과 요금 감시도 함께 두십시오.

## 이 저장소가 자동으로 설치하지 않는 것

- Postfix 패키지 설치, `master.cf`/`main.cf`/`transport`/`faxmail.conf` 편집, DNS(MX) 설정. 위 단계는 모두 직접 합니다.
- Postfix 이외의 메일 서버(sendmail 등) 설정.
- `faxmail` 사용자 계정 생성.

다음: [HylaFAX 운영 메모](hylafax-operations.md), [운영 점검 목록](operations-checklist.md)
