# HylaFAX 서버 준비

[HylaFAX 연동 설치 가이드](hylafax.md)는 **이미 돌아가는 HylaFAX**에 NamiFAX를 연결하는 방법을 설명합니다. 이 페이지는 그 앞 단계, 곧 HylaFAX 서버 자체를 준비하고 NamiFAX가 기대하는 HylaFAX 쪽 설정을 맞추는 방법을 설명합니다. NamiFAX 쪽 설치(환경 파일, 웹 서비스, 주기 작업)는 다루지 않습니다.

!!! warning "시험하지 못했습니다"
    이 저장소에서는 실제 HylaFAX에 붙여 시험하지 못했습니다(`hylafax.md` 첫머리 참고). 이 페이지는 현재 `deploy/` 파일과 HylaFAX 설치 절차에서 확인되는 것만 적었고, 확인되지 않는 부분은 그렇다고 적었으니 **대상 배포판에서 직접 확인**하십시오. 운영 서버에 적용하기 전에 시험 서버에서 한 번 거치십시오.

## 1. 순서 (HylaFAX 쪽만)

경로 가정은 `hylafax.md`와 같습니다. HylaFAX 스풀은 `/var/spool/hylafax`, 서비스 사용자는 `uucp`입니다.

### 1-1. HylaFAX 설치 (Debian/Ubuntu)

HylaFAX는 배포판 패키지로 설치하거나 소스를 컴파일해 설치할 수 있습니다. 이 페이지는 Debian/Ubuntu 계열 서버의 패키지 설치만 설명합니다. 다른 배포판은 해당 배포판의 HylaFAX 안내를 따르십시오.

```sh
sudo apt-get install hylafax-server mgetty mgetty-voice
```

!!! warning "별도 호스트에 설치하십시오"
    HylaFAX는 반드시 독립된 호스트 컴퓨터에 설치해야 합니다. 필요한 것은 **다이얼업 모뎀**입니다. 구형 PCI 모뎀이나 USB 모뎀을 쓸 수 있고, 모뎀이 없으면 아래 모뎀 설정 단계로 진행할 수 없습니다. 요즘은 PC 내장형을 구하기 어려워 USB 모뎀을 따로 구입하기도 합니다.

### 1-2. `faxsetup` 실행

설치 뒤 root 권한으로 HylaFAX 설정을 시작합니다.

```sh
sudo faxsetup
```

처음 물어보는 항목은 서버 프로세스 구성입니다. 기본값을 그대로 받아들입니다(Enter).

```
HylaFAX configuration parameters are:

    [1] Init script starts faxq:        yes
    [2] Init script starts hfaxd        yes
    [3] Start paging protocol:          no
Are these ok [yes]?
```

이어서 설정 파일을 쓰고 HylaFAX 서버 프로세스를 다시 시작할지 묻습니다(`Should I restart the HylaFAX server processes [yes]?`). Enter를 눌러 진행합니다. 아직 모뎀이 없다면 `faxaddmodem`을 실행할 것인지 묻는데(`Do you want to run faxaddmodem to configure a modem [yes]?`), yes로 답해 다음 단계로 넘어갑니다.

### 1-3. 모뎀 추가 (`faxaddmodem`)

모뎀(또는 가상 IAX 모뎀)마다 `faxaddmodem`을 실행합니다. `faxsetup`에서 이어서 실행되거나 `sudo faxaddmodem <장치>`로 직접 실행할 수 있습니다. 이 명령이 `config.<장치>` 파일을 만들며, 장치 이름은 파일 이름의 `config.` 뒤 부분입니다(`config.ttyACM0`의 `ttyACM0`).

먼저 모뎀이 연결된 직렬 포트의 **장치 이름**을 입력합니다. COM(직렬) 포트에 연결되어 있어야 하며 병렬 포트는 안 됩니다. 첫 번째 직렬 포트는 `ttyS0`, 첫 번째 USB-직렬 어댑터는 `ttyUSB0`, USB 모뎀은 `ttyACM0`인 경우가 많습니다. 호스트마다 다르므로 `ls /dev/tty*`로 실제 이름을 확인하십시오. **장치 파일이 없으면 다음 단계로 넘어가지 못합니다.**

그다음 질문이 이어집니다. 아래 표는 한국에서 쓰는 예입니다. 표에 없는 질문은 기본값(Enter)으로 두면 됩니다.

| 질문 | 입력 | 설명 |
|---|---|---|
| Country code | `82` | 국가 번호 |
| Area code | `2` | 지역 번호에서 앞의 0을 뺀 값(02이면 2) |
| Phone number of fax modem | `+82.2.123.4567` | 팩스 번호가 02-123-4567일 때의 형식 |
| Local identification string (TSI/CIG) | 비워 둠 | 설정하지 않으려면 Enter |
| Long distance dialing prefix | `0` | 한국은 시외 접두 번호가 필요하지 않아 0 |
| International dialing prefix | `00` | 국제 전화 접두 번호 |
| Dial string rules file | 기본값 `etc/dialrules` | |
| Tracing during normal server operation / send and receive sessions | 기본값 `1` / `11` | |
| **Protection mode for received facsimile** | **`0644`** | 기본값은 `0600`입니다. **NamiFAX를 쓰려면 `0644`**여야 웹 서비스 사용자가 수신 팩스를 읽을 수 있습니다. HylaFAX만 쓰면 기본값으로 둡니다 |
| **Protection mode for session logs** | **`0644`** | 위와 같은 이유로 NamiFAX를 쓰면 `0644` |
| Protection mode for `<장치>` | 기본값 `0600` | 모뎀을 HylaFAX 밖에서도 공유하려면 `0666` |
| Rings to wait before answering | 기본값 `1` | `0`이면 "보내기 전용" 팩스 시스템이 됩니다 |
| Modem speaker volume | 기본값 `off` | `OFF`, `QUIET`, `LOW`, `MEDIUM`, `HIGH`만 허용. 시험할 때는 `HIGH`가 좋지만 USB 모뎀에서는 소용없을 수 있습니다 |
| Command line arguments to getty program | 기본값 `-h %l dx_%s` | |
| TSI / Caller-ID access control list file | 기본값(비움) | |
| Tag line font file / format string | 기본값 | `etc/lutRS18.pcf`, `From %%l\|%c\|Page %%P of %%T` |
| UUCP lock 관련 3개 | 기본값 | 오래된 잠금 파일 제거 시간 30초, 데이터·음성 통화 중 잠금 유지 |
| Percent good lines / max consecutive bad lines | 기본값 `95` / `5` | 복사 품질 검사. 연속 불량 라인은 3까지 줄일 수도 있습니다 |
| **Max number of pages to accept in a received facsimile** | `80` | 기본값은 `25`쪽까지만 받습니다. 쪽수가 늘수록 디스크도 더 필요합니다 |
| Syslog facility name for ServerTracing | 기본값 `daemon` | 원격 syslog로 분리하려면 `local7` |
| CLOCAL용 UID, 우선순위 스케줄링 | 기본값(비움) | |

입력을 마치면 기본값과 다른 설정만 모아 보여 주며 확인을 요청합니다. 입력한 값과 같으면 Enter를 누릅니다.

```
The non-default server configuration parameters are:

CountryCode:         82
AreaCode:            2
FAXNumber:           +82.2.123.4567
LongDistancePrefix:  0
InternationalPrefix: 00
...
MaxRecvPages:        80
Are these ok [yes]?
```

그러면 `faxaddmodem`이 tty 포트를 조사해 모뎀과 통신하는 **가장 좋은 속도**를 찾습니다. 이때 모뎀에 케이블이 연결되어 있지 않거나 전원이 꺼져 있으면 멈출 수 있으니 먼저 확인하십시오.

```
Probing for best speed to talk to modem: 38400
This modem looks to have support for Class 1.0, 1 and 2.
How should it be configured [1.0]? 1
```

모뎀이 Class 1과 Class 2를 모두 지원하더라도 모든 팩스 기기와 호환되도록 **Class 1**로 설정합니다. 이어서 모뎀별 값을 묻는데, 모뎀 조회 결과가 기본값으로 제안되므로 Enter로 받아들이면 됩니다. 긴 문서를 보낸다면 PostScript 변환 제한 시간을 늘릴 수 있습니다. 이 단계가 실패하면 모뎀 통신 문제일 수 있으니 HylaFAX 문서의 일반 오류 항목을 보십시오.

끝나면 "다른 모뎀을 설정할 것인가"를 묻습니다. 모뎀이 하나뿐이면 no, 더 있으면 yes로 답해 같은 단계를 되풀이합니다. 마지막 질문(`Should I run faxmodem for each configured modem [yes]?`)은 기본값 yes로 둡니다. 설정한 값을 직접 고치려면 `/etc/hylafax`의 `config`와 `config.<장치>` 파일을 편집하십시오.

!!! note "시험 범위"
    이 절의 질문 목록과 입력값은 `search5/nami-fax` 저장소의 `docs/contents/hylafax/index.rst`에서 가져왔습니다. 그 문서에도 모뎀을 조사하는 단계 이후는 "실제 모뎀으로 시험해야 함"이라고 적혀 있습니다. 질문의 순서와 기본값은 HylaFAX 버전(문서의 예는 6.0.7)에 따라 다를 수 있습니다.

### 1-4. 서비스 시작

HylaFAX는 서버 데몬 `faxq`(대기열), `hfaxd`(클라이언트 접속), 모뎀마다 `faxgetty`(수신·모뎀 관리)로 이뤄집니다. 오늘날 systemd 배포판에서는 단위 이름이 다르므로(`hylafax` 하나로 묶인 곳도, `faxq`·`hfaxd`·`faxgetty@ttyS0`로 나뉜 곳도 있습니다) **대상 배포판에서 확인하십시오.**

```
systemctl enable --now hylafax      # 단위 이름은 배포판에 따라 다름
```

Debian/Ubuntu 패키지에서는 부팅할 때 자동으로 시작되도록 `/etc/default/hylafax`를 열어 `RUN_HYLAFAX=1`이 들어 있는 줄 앞에 `#`이 없는지 확인하십시오. 설정을 마쳤으면 HylaFAX를 다시 시작하고 상태를 점검합니다.

```sh
sudo systemctl restart hylafax.service
sudo faxstat -s
```

`faxstat -s`의 모뎀 줄이 `Running and idle`(대기 상태)로 나오면 설정대로 잘 실행되고 있는 것입니다.

### 1-5. NamiFAX가 기대하는 HylaFAX 설정

`hylafax.md` 1단계가 훅 파일 복사와 설정 줄 붙이기를 설명합니다. 긴 설명을 반복하지 않고, 여기서는 설정 값만 `deploy/hylafax/`와 똑같이 적습니다.

모뎀 설정(`config.<장치>`, 모뎀마다 한 번씩. `deploy/hylafax/config.namifax`):

```
FaxRcvdCmd:     bin/faxrcvd
DynamicConfig:  bin/dynconf
UseJobTSI:      true
```

서버 설정(`deploy/hylafax/etc-faxq.snippet`와 `hfaxd.conf.snippet`):

```
NotifyCmd:      bin/notify
CoverCmd:       bin/faxcover
JobFmt: "%-3j %3i %1a %15o %40M %-12.12e %5P %5D %7z %.25s"
```

설명:

- `FaxRcvdCmd`, `DynamicConfig`, `NotifyCmd`, `CoverCmd`의 `bin/...`은 `$SPOOL/bin/` 아래의 파일입니다. 훅 스크립트(`deploy/hylafax/bin/faxrcvd`, `dynconf`, `notify`, `faxcover`)를 거기에 복사하고 실행 권한을 주십시오. 이 스크립트들은 `/etc/namifax.env`를 읽은 뒤 `namifax-*` 실행 파일로 `exec`합니다.
- `JobFmt`는 NamiFAX가 `faxstat -s`, `faxstat -d` 출력을 읽는 열 순서와 같아야 합니다.
- 설정 파일의 위치는 배포판과 HylaFAX 버전에 따라 다릅니다. `deploy/hylafax/etc-faxq.snippet`은 `NotifyCmd`와 `CoverCmd`를, `hfaxd.conf.snippet`은 `JobFmt`를 `$SPOOL/etc/config`에 두라고 안내합니다. 표지가 만들어지지 않거나 출력함이 어긋나면 대상 HylaFAX 버전에서 그 값이 읽히는 파일(`config`, `hyla.conf`, `sendfax.conf` 등)을 확인하고, 적용 여부는 `faxstat -s` 출력으로 확인하십시오(2절).
- 설정을 바꾼 뒤에는 HylaFAX를 다시 시작하십시오.

### 1-6. `hfaxd` 접근

NamiFAX는 TCP로 `hfaxd`에 직접 접속하지 않고 같은 서버에서 `sendfax`, `faxstat`, `faxrm`, `faxalter`, `faxinfo`를 실행합니다. 그래도 이 명령들은 `hfaxd`에 접속하므로, `hfaxd`가 로컬 접속(예: `localhost`)을 허용하고 그 사용자 이름으로 작업을 낼 수 있어야 합니다. **`hosts.hfaxd`의 형식과 사용자 등록 방법은 HylaFAX 문서와 대상 배포판에서 확인하십시오.** HylaFAX 사용자는 `faxadduser`/`faxdeluser`로 등록·삭제하며, NamiFAX가 계정과 함께 이를 자동으로 하게 하려면 다음 항목의 sudo 설정과 `HYLAFAX_USER_SYNC=1`이 필요합니다.

### 1-7. sudo

`deploy/sudoers.d/namifax`를 `/etc/sudoers.d/namifax`로 복사(모드 0440, `visudo -cf`로 확인)하십시오. 허용 내용은 `reboot`, `halt`, `faxdeluser`, `faxadduser`뿐이며, 서비스 사용자(`uucp`)를 맞춰야 합니다. `faxadduser`/`faxdeluser`는 `HYLAFAX_USER_SYNC=1`일 때만 쓰입니다. 자세한 조건은 `hylafax.md` 3단계를 보십시오.

### 1-8. NamiFAX에 모뎀 등록

**관리자 > 팩스 모뎀 장치**에서 `faxaddmodem`으로 만든 장치 이름을 직접 입력하십시오([팩스 회선과 라우팅](../manual/admin/fax-lines.md)). 이 화면은 기록만 하며, 장치가 HylaFAX에 실제로 있어야 합니다. 설정과 관련된 파일을 고치기 전에는 `/etc/hylafax`의 `config*`를 백업해 두십시오.

## 2. 확인

`hylafax.md` 7단계와 [운영 점검표](operations-checklist.md)의 HylaFAX 항목이 기준입니다. HylaFAX 쪽에서 먼저 아래를 확인하십시오.

1. `faxstat`이 서버에 접속하고 모뎀 상태가 `Running and idle`로 나오는지 확인합니다. 나오지 않으면 `faxgetty` 로그부터 보십시오.
2. 큐 출력 열이 맞는지 `faxstat -s`로 확인합니다(`JobFmt`가 적용되었는지).
3. 동적 설정 훅을 시험합니다. 아무것도 출력하지 않고 끝나야 하며, 차단 번호면 `RejectCall: true`가 나옵니다.

    ```
    sudo -u uucp /var/spool/hylafax/bin/dynconf ttyS0 5551234
    ```

4. 관리자 > 팩스 모뎀 장치에서 모뎀을 만들고 상태를 확인합니다.
5. 시험 팩스를 보내고 받아서 `notify`와 `faxrcvd`가 동작하는지 봅니다(`hylafax.md` 7단계).
