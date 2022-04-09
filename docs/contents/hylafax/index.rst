HylaFAX™
##############

HylaFAX™ 오픈 소스는 클라이언트-서버 아키텍처를 중심으로 설계되었습니다. 팩스 모뎀은 네트워크의 단일 시스템에 상주할 수 있으며 클라이언트는 네트워크의 다른 시스템에서 아웃바운드 작업을 전송할 수 있습니다. 

HylaFAX™는 매우 견고하고 안정적으로 설계되었습니다. 팩스 서버는 소프트웨어, 구성, 하드웨어 및 일반적인 사용에서 예기치 않은 오류를 방지하도록 설계되었습니다. HylaFAX는 여러 모뎀과 많은 트래픽 부하를 지원할 수 있습니다.

HylaFAX™ 설치
**************

HylaFAX™은 배포본에서 제공되는 패키지 또는 소스 코드 컴파일을 통해 설치할 수 있습니다. 본 문서는 Debian/Ubuntu 기반 서버에서 설치하는 방법만 다룹니다. 다음과 같은 명령으로 설치합니다.

.. code-block::

    $ sudo apt-get install hylafax-server mgetty mgetty-voice

HylaFAX™는 반드시 독립된 호스트 컴퓨터에서 설치해야 합니다.


HylaFAX 설정
**************

HylaFAX™ 를 설치하면 첫번째로 Dial-up(다이얼업) 모뎀을 호스트 컴퓨터에 설치합니다. 다이얼업 모뎀은 PCI 방식의 구형 모뎀 또는 USB 모뎀을 사용할 수 있습니다.

.. important::
    **다이얼업 모뎀이 없어요!** PC에 직접 설치하는 모뎀은 더 이상 찾기 어렵지만 USB 형태의 모뎀은 AliExpress 등에서 구입할 수 있습니다. 다이얼업 모뎀이 없으면 HylaFAX™ 구성 단계로 진행할 수 없습니다.

다음 명령을 입력하여 HylaFAX™ 설정을 시작합니다.

.. code-block::

    $ sudo faxsetup

이 명령이 실행되면 HylaFAX™를 사용하기 위해 설정해야 할 항목을 물어봅니다. 다음과 같이 실행 항목을 물어봅니다.

.. code-block::

    Setup program for HylaFAX (tm) 6.0.7.

    Created for x86_64-pc-linux-gnu on Wed, 13 Jan 2021 13:00:13 +0000.

    Reading cached parameters from /var/spool/hylafax/etc/setup.cache.

    Found base64 encoder: /bin/base64
    Found Quoted-Printable encoder: qp-encode
    Found mimencode for compatibilty: mimencode
    Checking system for proper server configuration.

    Make /var/spool/hylafax/bin/ps2fax a link to /var/spool/hylafax/bin/ps2fax.gs.


    Make /var/spool/hylafax/bin/pdf2fax a link to /var/spool/hylafax/bin/pdf2fax.gs.

    Update /var/spool/hylafax/status/any.info.

        HylaFAX configuration parameters are:

        [1] Init script starts faxq:		yes
        [2] Init script starts hfaxd		yes
        [3] Start paging protocol:		no
    Are these ok [yes]?

팩스 서버 설정을 하기 위해 "Enter" 키를 누릅니다.

다음으로, 팩스 설정은 일부 구성 파일을 작성하고 다음과 같이 팩스 프로세스를 재시작할 것인지 물어봅니다.

.. code-block::

    Modem support functions written to /var/spool/hylafax/etc/setup.modem.
    Configuration parameters written to /var/spool/hylafax/etc/setup.cache.

    Restarting HylaFAX server processes.
    Should I restart the HylaFAX server processes [yes]?

"Enter" 키를 눌러 다음 단계로 이동합니다.

.. code-block::

    /etc/init.d/hylafax start
    Starting hylafax (via systemctl): hylafax.service.

    You do not appear to have any modems configured for use.  Modems are
    configured for use with HylaFAX with the faxaddmodem(8) command.
    Do you want to run faxaddmodem to configure a modem [yes]?

아직 모뎀을 설정하지 않았기 때문에 팩스 설정은 'faxaddmodem'을 실행하라는 메시지를 표시합니다. 예라고 대답하려면 Enter 키를 누르세요

팩스 모뎀이 연결된 직렬 포트의 장치 이름을 입력합니다(모뎀이 Parreal 포트가 아닌 COM 포트에 연결되어 있는지 확인). Hint: ttyS0은 첫 번째 Serial 포트용이고 ttyUSB0은 첫 번째 USB-Serial 어댑터입니다.
다음으로 꽤 많은 값을 입력하라는 메시지가 표시됩니다. 대부분의 경우 Enter 키를 눌러 기본값을 수락할 수 있습니다.

.. code-block::

    Serial port that modem is connected to [ttyS0]? ttyACM0

처음으로 모뎀이 동작하는 장치 파일을 물어봅니다. 호스트마다 조금씩 다르겠지만 모뎀 장치가 ttyACM0 이라고 입력하고 Enter 키를 누릅니다. 이 때 장치 파일이 없으면 다음 단계로 넘어가지 못하므로 주의해야 합니다.

.. code-block::

    Ok, time to setup a configuration file for the modem.  The manual
    page config(5) may be useful during this process.  Also be aware
    that at any time you can safely interrupt this procedure.

    Reading scheduler config file /var/spool/hylafax/etc/config.

    No existing configuration, let's do this from scratch.

    Country code [1]?

국가 코드를 물어보면 82 라고 입력하고 Enter 키를 누르세요

.. code-block::

    Area code [415]?

다음으로 팩스 서버가 위치한 지역의 지역번호를 입력합니다. 이 때 앞의 0은 빼고 입력합니다. 지역번호 02일 때 2만 입력하고 Enter 키를 누릅니다.

.. code-block::

    Phone number of fax modem [+1.999.555.1212]?

팩스 번호가 02-123-4567 이면 여기에는 +82.2.123.4567 와 같이 입력하고 Enter 키를 누릅니다.

.. code-block::

    Local identification string (for TSI/CIG) ["NothingSetup"]?

로컬 식별 문자열의 이름을 입력합니다. 아무것도 입력하지 않고 Enter 키를 누르면 설정하지 않습니다. 여기서는 바로 Enter 키를 누릅니다.

.. code-block::

    Long distance dialing prefix [1]? 

장거리로 팩스를 보내려고 할 때 사용할 번호를 입력합니다. 한국은 필요하지 않으므로 0을 입력하고 Enter 키를 누릅니다.

.. code-block::

    International dialing prefix [011]?

국제 전화로 팩스를 보내려고 할 때 사용할 접두사 번호입니다. 00을 입력하고 Enter 키를 누릅니다.

.. code-block::

    Dial string rules file (relative to /var/spool/hylafax) [etc/dialrules]?

다이얼 문자열 규칙 파일의 경로를 적어줍니다. 기본값으로 두고 Enter 키를 누릅니다.

.. code-block::

    Tracing during normal server operation [1]?

 정상적인 서버 운영 중 추적을 할 것인지 물어봅니다. 기본값으로 두고 Enter 키를 누릅니다.

.. code-block::

    Tracing during send and receive sessions [11]?

보내기 및 받기 작업 중 추적을 할 것인지 물어봅니다. 기본값으로 두고 Enter 키를 누릅니다.

.. code-block::
    
    Protection mode for received facsimile [0600]?

수신된 팩스 데이터의 보호 모드에 사용할 파일 권한을 지정합니다. HylaFAX만 사용할 것이면 기본값으로 두지만 NamiFAX를 사용하려면 0644로 입력하고 Enter 키를 입력합니다.

.. code-block::
    
    Protection mode for session logs [0600]?

HylaFAX에서 생성된 세션 로그에 사용할 파일 권한을 지정합니다. HylaFAX만 사용할 것이면 기본값으로 두지만 NamiFAX를 사용하려면 0644로 입력하고 Enter 키를 입력합니다.

.. code-block::

    Protection mode for ttyACM0 [0600]?

다이얼업 모뎀 장치를 HylaFAX 외에도 공유하려면 0666을 입력하고 아니면 기본값으로 두고 Enter 키를 입력합니다.

.. code-block::

    Rings to wait before answering [1]?

응답 전에 대기 벨 소리를 설정할 것인지 지정합니다. 기본값은 1이지만 0으로 설정하면 "보내기 전용" 팩스 시스템으로 설정합니다. 기본값으로 두고 Enter 키를 입력합니다.

.. code-block::

    Modem speaker volume [off]? 

모뎀 스피커 볼륨을 설정합니다. 유효한 값은 OFF, QUIET, LOW, MEDIUM, HIGH이며 이 외의 입력값은 허용하지 않습니다. 테스트 목적으로 HIGH를 설정하는 것이 좋지만 USB 타입의 다이얼업 모뎀에서는 무용지물일 수 있습니다.

.. code-block::

    Command line arguments to getty program ["-h %l dx_%s"]?

getty 프로그램에 대한 명령줄 인수를 입력합니다. 기본값으로 두고 Enter 키를 입력합니다.

.. code-block::

    Pathname of TSI access control list file (relative to /var/spool/hylafax) [""]?

TSI 액세스 제어 목록 파일의 경로 이름을 입력합니다. 기본값으로 두고 Enter 키를 입력합니다.


.. code-block::

    Pathname of Caller-ID access control list file (relative to /var/spool/hylafax) [""]?     

Caller-ID 접근 제어 목록 파일의 경로명을 입력합니다. 기본값으로 두고 Enter 키를 입력합니다.

.. code-block::

    Tag line font file (relative to /var/spool/hylafax) [etc/lutRS18.pcf]? 

태그 라인 글꼴 파일 경로를 입력합니다. 기본값으로 두고 Enter 키를 입력합니다.

.. code-block::

    Tag line format string ["From %%l|%c|Page %%P of %%T"]? 

태그 라인에 찍힐 포맷 문자열을 입력합니다. 기본값으로 두고 Enter 키를 입력합니다.

.. code-block::

    Time before purging a stale UUCP lock file (secs) [30]?

오래된 UUCP 잠금 파일을 제거하기 전의 시간을 입력합니다. 기본값으로 두고 Enter 키를 입력합니다.

.. code-block::

    Hold UUCP lockfile during inbound data calls [Yes]? 

인바운드 데이터 통화 중 UUCP 잠금 파일을 유지할 것인지 입력합니다. 기본값으로 두고 Enter 키를 입력합니다.

.. code-block::

    Hold UUCP lockfile during inbound voice calls [Yes]? 

인바운드 음성 통화 중 UUCP 잠금 파일을 유지할 것인지 입력합니다. 기본값으로 두고 Enter 키를 입력합니다.

.. code-block::

    Percent good lines to accept during copy quality checking [95]? 

복사 품질 검사 중 허용되는 양호한 라인 비율을 입력합니다. 기본값으로 두고 Enter 키를 입력합니다.

.. code-block::

    Max consecutive bad lines to accept during copy quality checking [5]?

복사 품질 검사 중 허용되는 최대 연속 불량 라인 수를 입력합니다. 기본값은 5이나 3까지 줄일 수 있습니다. 기본값으로 두고 Enter 키를 입력합니다.

.. code-block::

    Max number of pages to accept in a received facsimile [25]? 

수신된 팩스에서 허용할 최대 페이지 수를 입력합니다. 기본값은 최대 25로 25 페이지까지만 받는다는 의미입니다. 페이지 수가 많아질 수록 디스크 공간도 고려해야 합니다. 80을 입력하고 Enter 키를 누릅니다.

.. code-block::

    Syslog facility name for ServerTracing messages [daemon]? 

ServerTracing 메시지의 Syslog 기능 이름을 입력합니다. 기본값은 'daemon'이지만 원격 syslog 서버에 로깅하고 다른 로그 메시지와 팩스 로깅을 분리하려는 경우 'local7'로 변경합니다. 기본값으로 두고 Enter 키를 입력합니다.

.. code-block::
    
    Set UID to 0 to manipulate CLOCAL [""]? 

CLOCAL을 조작하려면 UID를 0으로 설정합니다. 기본값으로 두고 Enter 키를 입력합니다.

.. code-block::

    Use available priority job scheduling mechanism [""]? 

사용 가능한 우선순위 작업 스케줄링 메커니즘을 입력합니다. 기본값으로 두고 Enter 키를 입력합니다.

여기까지 모든 입력이 완료되었으면 지금까지 입력한 내용에 대해 다음과 같이 확인 작업을 하게 됩니다.

.. code-block::

    The non-default server configuration parameters are:

    CountryCode:		82
    AreaCode:		2
    FAXNumber:		+82.2.123.4567
    LongDistancePrefix:	0
    InternationalPrefix:	00
    DialStringRules:	etc/dialrules
    SessionTracing:		11
    RingsBeforeAnswer:	1
    SpeakerVolume:		off
    GettyArgs:		"-h %l dx_%s"
    LocalIdentifier:	"NothingSetup"
    TagLineFont:		etc/lutRS18.pcf
    TagLineFormat:		"From %%l|%c|Page %%P of %%T"
    MaxRecvPages:		25

    Are these ok [yes]? 

표시된 내용이 입력된 것과 같으면 Enter 키를 입력합니다.

.. code-block::

    Now we are going to probe the tty port to figure out the type
    of modem that is attached.  This takes a few seconds, so be patient.
    Note that if you do not have the modem cabled to the port, or the
    modem is turned off, this may hang (just go and cable up the modem
    or turn it on, or whatever).

    Probing for best speed to talk to modem: 38400

그러면 이제 다이얼업 모뎀과 통신해 tty 포트를 조사하고 최상의 속도가 검출될 것입니다. 이 때 모뎀에 케이블이 연결되어 있지 않거나 모뎀이 꺼져 있으면 중단될 수 있으므로 주의해야 하니다.

!! TODO.. 여기부터 실제 모뎀 가지고 테스트해야 함

.. code-block::

    This modem looks to have support for Class 1.0, 1 and 2.
    How should it be configured [1.0]? 1

setupfaxmodem은 이제 팩스 모뎀과 통신하여 통신하기에 가장 좋은 속도와 지원하는 팩스 클래스를 결정합니다.
이 단계가 실패하면 모뎀에 통신 문제가 있을 수 있습니다. 일반적인 오류 섹션 에서 가능한 해결 방법을 검토하십시오 .

모뎀이 클래스 1과 클래스 2를 모두 지원하더라도 모든 팩스 기기와의 호환성을 위해 클래스 1로 설정해야 합니다.
그런 다음 모뎀에 특정한 값을 묻는 메시지가 표시됩니다. 모뎀 쿼리와 선택한 클래스의 결과인 기본값을 그대로 사용하려면 Enter 키를 누르기만 하면 됩니다. 그런 다음 Enter 키를 눌러 이러한 값을 확인하라는 메시지가 표시됩니다 .

그러면 기본이 아닌 스케줄러 값이 표시되고 확인 프롬프트가 표시됩니다.
이 모든 값이 올바른지 확인하십시오. 그렇지 않은 경우 아니오 로 답 하고 잘못된 값을 수정하십시오.

긴 문서를 팩스로 보내는 경우 "변환 시 시간 초과 ? PostScript 문서" 에 대한 시간 값을 늘릴 수 있습니다 .

Enter 키 를 눌러 기본값을 승인하면 됩니다.

위의 모든 작업이 순조롭게 진행되었다고 가정하면 이제 팩스addmodem이 제어를 팩스 설정으로 되돌리고 첫 번째 모뎀 구성을 완료했습니다.

.. code-block::

    Do you want to run faxaddmodem to configure another modem [yes]?

하나의 팩스 모뎀만 구성 하는 경우 다른 모뎀을 구성할 것인지 묻는 메시지가 나타나면 아니오 로 대답하십시오. 그렇지 않으면 yes 로 대답 하고 위의 팩스addmodem 관련 단계를 다시 수행하십시오.

.. code-block::

    Should I run faxmodem for each configured modem [yes]? 

그런 다음 기본 예 응답을 수락하여 새로 구성된 모뎀에서 팩스모뎀을 실행하여 설정을 확인합니다.

이제 쉘 프롬프트로 돌아가야 합니다.
이러한 설정이 포함된 파일을 수동으로 편집하려면 /etc/hylafax의 'config' 및 'config.MODEMDEVICE' 파일에서 선호하는 편집기를 사용하십시오(여기서 MODEMDEVICE는 모뎀이 연결된 장치임).
다음으로 시스템을 부팅할 때 자동으로 실행되도록 HylaFAX를 설정합니다. 즐겨 사용하는 텍스트 편집기를 사용하여 /etc/default/hylafax 구성 파일의 내용을 검사합니다.
RUN_HYLAFAX=1 을 포함하는 행의 시작 부분에 # 문자 가 없는지 확인하십시오 .

.. code-block::
    
    $ sudo systemctl restart hylafax.service 

hylaFax 데몬을 재시작합니다.

팩스서비스가 설정대로 잘 재시작되었는지 상태를 점검하기 위해 아래 명령으로 확인합니다.

.. code-block::

    $ sudo faxstat -s

그 결과가 아래 그림과 같이 나오면 잘 설정되어 실행중에 있으며 대기상태에 있음을 알 수 있습니다.

