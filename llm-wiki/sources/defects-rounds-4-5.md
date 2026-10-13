---
title: 4·5라운드 결함 요약
type: source
verified: false
sources:
  - "git show 01f2f64:docs/numfax-defects-details/round4-e2e.md"
  - "git show 01f2f64:docs/numfax-defects-details/round4-files.md"
  - "git show 01f2f64:docs/numfax-defects-details/round4-fuzz.md"
  - "git show 01f2f64:docs/numfax-defects-details/round4-unmask.md"
  - "git show 01f2f64:docs/numfax-defects-details/round5-legacy.md"
  - "git show 01f2f64:docs/numfax-defects-details/round5-unmask.md"
  - "git show 01f2f64:docs/numfax-defects-details/round5-files.md"
updated: 2026-10-02
---

## 요약

4라운드는 E2E 브라우저 시나리오 13개(로그인, 발송, 수신함, 관리자, SMTP 등)로 당시 보고 결함 재현과 가짜 성공 패턴을 확인했고, 미정독 PHP 브리지와 골든 마스터 및 53,500회 퍼징으로 30건의 당시 보고 결함을 찾았다. 5라운드는 레거시 페이지 33개와 대조(14건), 광범위 패치 후 새로 드러난 권한 우회(9건), 테스트와 문서의 은폐 패턴(15건)을 당시 보고했다. 4-5라운드의 핵심은 (1) 가짜 성공 응답으로 인한 사용자 오인 광범위화, (2) 권한 필터의 fail-open 패턴, (3) 테스트-실제 동작의 괴리, (4) 문서와 코드의 사실성 차이다.

## 라운드/영역별 핵심

### 4라운드 E2E 브라우저 (시나리오 13개, 114장 스크린샷)
- S1 로그인~로그아웃: 정상(쿠키 Secure 없음, 로그아웃 경로 유실)
- S2 사용자 생성: 가짜 성공(피드백 없음, DB 불변) - 비밀번호 무염 MD5, 다음 로그인 실패
- S3 주소록: 부분 동작(팩스/이메일 정보 유실, 1번 덮어씀)
- S5 팩스 발송: 가짜 성공(입력 유실, 다중 수신처 문제, 파일 잔존)
- S6 수신함/모달: 부분 동작(썸네일 없음, 가짜 문서, 메모 피드백 없음)
- S7 아카이브 검색: [중간] R4E-01 가짜 결과 생성 - 검색어를 회사/문서명으로 에코
- S9 SMTP/스토리지: [낮음] R4E-02 테스트 후 입력값 손실
- S11 언어: 쿠키는 갱신되나 DB 불변, 1년 쿠키, 768px에서 가로 스크롤

### 4라운드 미정독 파일 (PHP 브리지 22개 + 파이썬 912줄)
- [높음] R4F-01: PHP 브리지의 삽입 안 되는 메서드와 키(AFAddressBookBridge 45개 중 16개만)
- R4F-02 [중간] bridge_cli가 호출마다 새 프로세스라 연결 상태 유지 안 됨
- R4F-03 [중간] 파일 업로드 폼이 파일명 검증 없이 저장
- R4F-04 [중간] AFUserAccountBridge의 password 암호화 변형(레거시 SHA1 → 구현 MD5)
- R4F-05 [중간] FaxPDFArchiveBridge의 설정 읽기(installdir 등) 미구현

### 4라운드 퍼징 (53,500회 자동 입력)
- [높음] R4Z-01: 텍스트 필드에 파일 파트 보내면 40개 라우트 500(AttributeError) - 인증 전 라우트 포함
- R4Z-02 [중간] fax_download가 fid/format을 Content-Disposition에 검증 없이 삽입(CR/LF 주입 가능)
- R4Z-03 [중간] /admin/fax2email 생성이 부분 저장(회사 행만, 팩스 행 INSERT 실패 무시)
- R4Z-04 [낮음] NUL/10만자가 SQL 오류로 조용히 삼켜져 성공/빈 결과

### 4라운드 광범위 차단 제거 후 (1차 패치 8건 + 2차 패치 12건)
- 시나리오 기존 가짜 성공이 부분적 개선되었으나 당시 보고되지 않은 권한 우회 5건 드러남

### 5라운드 레거시 페이지 대조 (루트 PHP 33개 + admin 21개 + ajax 13개)
- [높음] R5L-06: 주소록 편집이 팩스번호별 속성 편집/복수 번호 관리 미지원
- R5L-01 [중간] viewfax가 이전/다음 정보를 전혀 넘기지 않음
- R5L-03 [중간] 표지/파일 없는 팩스 제출이 허용되고 outbox로 리다이렉트
- R5L-05 [중간] 회사 삭제 시 팩스재지정, 팩스번호 정리 없음
- R5L-08 [중간] 새 팩스 도착 알림음(audiofile) 기능 통째로 없음
- R5L-10 [중간] 관리자 사용자 폼에 프로필, 환경 필드 없음
- R5L-11 [중간] 이메일 모달이 cc/bcc, 첨부 파일명, 분류, 보관 옵션 누락
- R5L-13 [중간] faxalter 모달이 폼-서비스 키 불일치로 대부분 수정 미적용

### 5라운드 2차 패치 후 권한 우회 (9건)
- [높음] R5U-01: 모뎀/분류 없는 사용자의 아카이브가 fail-open으로 전체 팩스 노출
- [높음] R5U-07: 재전송 모달이 원본 팩스 fid를 쓰지 않아 파일 미첨부
- R5U-02 [중간] 분류 삭제 시 FaxArchive.faxcatid 정리 안 됨
- R5U-03 [중간] 모뎀 삭제 후 권한에 장치 이름 남아 부활 가능
- R5U-04 [중간] 주소록 UI로 만든 회사의 팩스번호가 목록/검색에서 미표시
- R5U-05 [중간] faxrcvd 이미 있는 회사명이면 새 번호 미등록(faxnumid=0)
- R5U-06 [중간] /ajax/inbox 신규 팩스 수가 접근 제한 무시
- R5U-08 [낮음] 작업 삭제가 없는 작업에도 성공 메시지 표시
- R5U-09 [낮음] 이메일북 폼의 company 입력이 버려져 연락처 미연결

### 5라운드 테스트와 문서 (tests 69개, PHP 브리지, ARCHITECTURE.md)
- R5F-01 [중간] WebAuthn이 QueryResult를 리스트로 취급해 저장된 패스키 조회 실패
- R5F-02 [중간] pserve 기동에서 스케줄러 미시작(문서는 반대로 서술) - 변형
- R5F-03 [중간] phb가 모든 회사 팩스번호를 비워 PBOOK이 빈 항목만 생성
- R5F-10 [낮음] PHP 브리지의 레거시 공개 메서드 미구현(AFAddressBook 45→16)
- R5F-13, R5F-14, R5F-15 [낮음] ARCHITECTURE.md가 존재하지 않는 파일/경로 사실처럼 기술, 테스트 수 불일치

## 보고서가 주장하는 수치

- 4라운드 E2E: 새 결함 5건(높음 0, 중간 2, 낮음 3) + 기존 결함 20+건 재현
- 4라운드 미정독+퍼징: 30건(높음 2, 중간 13, 낮음 15)
- 5라운드 레거시 대조: 14건(높음 1, 중간 6, 낮음 7)
- 5라운드 2차 패치 후: 9건(높음 2, 중간 5, 낮음 2)
- 5라운드 테스트+문서: 15건(높음 0, 중간 3, 낮음 12)
- 퍼징 총 호출: 53,500회(라우트 72개, 파라미터 220쌍, 사용자 3종)
- E2E 스크린샷: 114장

## 한계·시험하지 못한 것

- 당시 보고자가 명시한 한계:
  - R4E: 실제 HylaFAX 서버와 통합 미실행(가짜 바이너리 사용)
  - R4F-04: 실제 SMTP 암호화 비교 미실행(코드 읽기만)
  - R4Z: 응답 지연/메모리 급증 관찰 없음(RSS 최대 242MB, 대부분 시간 < 1초)
  - R5L: 관리자 편집 화면 일부(conf_* 등) 정독 미완료
  - R5U: 패치 전 전체 상태 미재현(1차 패치 기초 위에 2차 패치)
- 원본 PHP 레거시 동작 재확인 없음(git show 코드 대조만)
- MySQL 데이터베이스 테스트 없음(SQLite만)
- 다중 사용자 동시 부하 테스트 부재

## 관련 주제 페이지

[[migration-from-avantfax]] [[authentication-and-security]] [[operations-and-deployment]] [[testing]] [[known-gaps-and-decisions]] [[hylafax-integration]]
