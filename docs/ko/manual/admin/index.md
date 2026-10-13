# 관리자 매뉴얼

이 매뉴얼은 NamiFAX의 관리 화면(`/admin`)을 설명합니다. 모든 설명은 이 저장소의 화면 템플릿과 코드를 읽어 확인한 내용입니다.

## 관리 화면을 열 수 있는 사람

접근 여부는 사용자 계정의 두 가지 플래그로 정해집니다([사용자](users.md) 화면에서 지정합니다).

| 플래그(사용자 양식의 이름) | 효과 |
|---|---|
| **관리자 콘솔**(`is_admin`) | 관리 화면을 열 수 있습니다. |
| **최고 관리자 권한**(`superuser`) | 관리 화면도 열 수 있고, 받은 팩스함·보낸 팩스함·보관함에서 모든 회선과 카테고리의 팩스를 다룹니다. |

- `/admin`의 모든 페이지는 두 플래그 중 하나를 요구합니다. 둘 다 없는 사람은 브라우저에서 받은 팩스함으로 돌려보내지고, 브라우저 화면 요청이 아니면 `403`을 받으며, 로그인하지 않은 사람은 로그인 화면으로 갑니다.
- 네 페이지는 **최고 관리자** 플래그가 따로 필요합니다. **SMTP 게이트웨이**, **네트워크 프린터**, **스토리지 및 클라우드**, **SAML 2.0 SSO**입니다. *관리자 콘솔*만 가진 계정에도 이 메뉴가 보이지만, 열면 거부되어 받은 팩스함으로 돌아갑니다.
- 플래그는 로그인할 때 세션에 복사됩니다. 누군가의 *관리자 콘솔*이나 *최고 관리자* 플래그를 바꾸면 그 사람이 다음에 로그인할 때부터 적용됩니다. 팩스 회선, DID 경로, 카테고리, 삭제 권한은 요청마다 데이터베이스에서 읽으므로 바로 적용됩니다.
- 첫 관리자는 서버에서 `namifax createuser`로 만듭니다(`--user-only`를 주지 않으면 두 플래그를 모두 가진 계정이 만들어집니다).

!!! note "이름 아래의 글자"
    사이드바 맨 아래 칸에는 사용자 이름 아래에 항상 *Superuser*라고 표시됩니다. 고정된 글자이며 실제 플래그를 반영하지 않습니다.

## 메뉴 구성

사이드바(좁은 화면에서는 *Module Switcher* 드롭다운)는 아래처럼 묶여 있습니다. 한국어 이름은 언어를 한국어로 했을 때 보이는 이름입니다.

| 묶음 | 항목 | 설명 페이지 |
|---|---|---|
| 개요 (Overview) | 대시보드 (Dashboard) | 아래 설명 |
| 접근 제어 (Access Control) | 사용자 계정 관리 (User Accounts) | [사용자](users.md) |
| 하드웨어 및 회선 (Hardware & Lines) | 팩스 모뎀 장치 (Fax Modems) | [팩스 회선](fax-lines.md) |
| | 네트워크 프린터 (Network Printers) | [시스템](system.md) |
| 수신 라우팅 (Inbound Routing) | DID 수신 라우팅 (DID Routing) | [팩스 회선](fax-lines.md) |
| | 팩스-이메일 라우팅 (Fax to Email) | [팩스 회선](fax-lines.md) |
| | 바코드 라우팅 (Barcode Routing) | [팩스 회선](fax-lines.md) |
| 콘텐츠 및 템플릿 (Content & Templates) | 팩스 카테고리 관리 (Fax Categories) | [팩스 회선](fax-lines.md) |
| | 표지 템플릿 관리 (Cover Pages) | [표지](covers.md) |
| 보안 및 시스템 (Security & System) | 동적 차단 목록(DynConf) (Blacklist (DynConf)) | [팩스 회선](fax-lines.md) |
| | 시스템 감사 로그 (System Audit Logs) | [시스템](system.md) |
| | 시스템 기능 (System Functions) | [시스템](system.md) |
| | SMTP 게이트웨이 (SMTP Gateway) | [시스템](system.md) |
| | 스토리지 및 클라우드 (Storage & Cloud) | [스토리지와 스케줄러](storage-scheduler.md) |
| | 예약 작업 (Scheduled Tasks) | [스토리지와 스케줄러](storage-scheduler.md) |
| | SAML 2.0 SSO | [인증](authentication.md) |

사이드바에는 받은 팩스함으로 돌아가는 **사용자 포털(User Portal)** 버튼과 **로그아웃** 버튼도 있습니다.

!!! note "기능을 켰을 때만 나타나는 메뉴"
    - **DID 수신 라우팅**은 환경변수 `ENABLE_DID_ROUTING`이 `1` 또는 `true`일 때만 나타납니다.
    - **바코드 라우팅**은 `ENABLE_BARDECODE_SUPPORT`(철자가 이렇게 쓰입니다)가 `1` 또는 `true`일 때만 나타납니다.

    같은 변수를 HylaFAX 수신 훅도 읽으므로 웹 서비스와 훅이 같은 값을 써야 합니다. [HylaFAX 설치](../../install/hylafax.md)를 참고하십시오.

## 대시보드

`/admin`에는 다음이 나옵니다.

- 카드 네 장: **팩스 회선** 수, **사용자** 수, HylaFAX 버전(**Backend Core**, 읽을 수 없으면 `알 수 없음`), **스케줄러** 카드.
- **등록된 사용자 계정**: 모든 계정의 이름, 사용자 이름, 마지막 로그인, 이메일과 **사용자 관리** 링크.
- **구성된 모뎀**: 모든 팩스 회선과 현재 상태([팩스 회선](fax-lines.md) 참고).
- 사용자, 모뎀, DID 라우팅, 로그로 가는 바로가기와 세 가지 짧은 안내가 있는 **관리자 워크플로우 가이드**.

!!! warning "대시보드의 일부 표시는 고정된 글자입니다"
    *SYSTEM OPERATIONAL*, *하드웨어 준비 완료*, **스케줄러** 카드(*APScheduler*, *실행 중*), *APScheduler Active*, **데이터베이스 엔진** 옆의 *SQLAlchemy / SQLite*, 상단 막대의 *어플라이언스 엔진 정상 가동 중*은 항상 같은 글자로 나오며 실제 상태를 점검한 결과가 아닙니다. 스케줄러가 실제로 돌고 있는지는 [예약 작업](storage-scheduler.md) 화면에서 확인하십시오. 실제 데이터베이스는 MySQL, MariaDB, PostgreSQL, SQLite 중 무엇이든 될 수 있습니다.

## 이 매뉴얼의 페이지

1. [사용자](users.md): 계정, 권한, 비밀번호 규칙, 잠금.
2. [팩스 회선](fax-lines.md): 모뎀, DID·바코드 라우트, 카테고리, 팩스-이메일, 발신자 차단.
3. [표지](covers.md): 지금 이 화면으로 할 수 있는 일.
4. [시스템](system.md): 시스템 기능, 로그, SMTP 게이트웨이, 네트워크 프린터.
5. [스토리지와 스케줄러](storage-scheduler.md): 저장소 종류, 보존 기간, 예약 작업.
6. [인증](authentication.md): SAML, 패스키, TOTP, 로그인 시도 제한, 세션.

사용자 화면은 [받은 팩스함](../inbox.md)부터 보십시오.
