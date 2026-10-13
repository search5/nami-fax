---
title: NamiFAX 시스템 전수 정밀 감사 보고서
type: source
updated: 2026-10-02
sources: [git 01f2f64:docs/LEGACY_DIVERGENCE_AUDIT_REPORT.md]
verified: false
---

## 요약

NamiFAX의 E2E Golden Master(68개) 및 단위 테스트(362개) 100% 통과 상태에서 소스 코드 전체를 심층 정밀 감사한 결과, **18건의 중대 불일치, 가짜 스텁 구현, 보안 취약점** 식별. 골든 마스터 검증 환경(HylaFAX 부재, 실제 모뎀/프린터 미연결)에서 HTTP 200 OK를 유지하기 위해 심어진 가짜 바이너리 생성기(합성 PDF, 빈 썸네일), 하드코딩 폴백(Acme Corp, ttyS0, 고정 일시), 모의 성공 반환(팩스 발송 시뮬레이션, 첨부파일 폐기) 다수 포함. 관리자 인증 백도어(`admin/password` 무조건 통과), 셸 명령어 인젝션, SQL 인젝션 등 상용 배포 전 반드시 조치할 중대 보안 결함 3건도 확인. 위험도별 4단계(Critical 2건, High 5건, Medium 7건, Low 4건) 및 정상화 단계 4단계(보안·가짜·미구현·UI 폴백) 정의.

## 핵심 내용

**§1 개요 및 위험도 통계**
- 총 18건 감사 항목: Critical 2, High 5, Medium 7, Low 4
- 골든 마스터 검증을 위한 가짜 구현 다수(HTTP 200 유지용)
- 중대 보안 취약점: 인증 백도어, 셸 인젝션, SQL 인젝션

**§2 세부 감사 항목 (18개)**

**Critical (2건)**
- **AUDIT-01 관리자 인증 우회 백도어**: `admin`/`password` 조합이면 DB 확인 없이 무조건 로그인(운영 환경에서 초기 비밀번호 변경 후에도 접근 가능)
- **AUDIT-02 HylaFAX 제어 명령 셸 인젝션**: `faxalter`, `killjob`에서 `shell=True` + 문자열 결합으로 RCE 위험

**High (5건)**
- **AUDIT-03 시스템 로그 검색 SQL 인젝션**: 검색 키워드를 f-string SQL에 직접 결합(타 테이블 데이터 추출 가능)
- **AUDIT-04 파일 부재 시 가짝 합성 PDF 바이너리**: 디스크 파일 없으면 하드코딩 PDF 헤더만 반환(골든 마스터 Content-Type 검증 통과용)
- **AUDIT-05 변환 실패 시 가짜 PDF 헤더/0바이트 은폐**: 변환 도구 실패 시 0바이트 또는 가짜 헤더 파일 생성 + `return True`(무결성 훼손)
- **AUDIT-06 주소록 검색 가짜 Acme Corp 자동완성**: 검색 결과 없으면 강제 주입(신규 설치 후 비어있음에도 나타남)
- **AUDIT-07 팩스 발송 시뮬레이션**: HylaFAX 부재 시 첨부파일 폐기 + 가짜 job_id 반환으로 발송 성공 위장

**High (계속)**
- **AUDIT-10 사용자 설정 완전 스텁**: DB 연동 없이 하드코딩 딕셔너리만 표시, 저장 눌러도 DB 미반영(비밀번호 변경 안 됨)
- **AUDIT-11 시스템 관리 기능 완전 스텁**: 백업·재부팅 버튼이 메시지만 반환(실제 action 없음)

**Medium (7건)**
- **AUDIT-08 하드코딩 표지 페이지 폴백**: DB에 없으면 `["standard", "urgent", "confidential"]` 임의 제공
- **AUDIT-09 수신함/팩스 보기 폴백 데이터**: Acme Corp, 2026-09-29 고정 일시, ttyS0 모뎀명이 뷰와 템플릿에 하드코딩(실제 값 없으면 노출)
- **AUDIT-12 모뎀 상태·HylaFAX 버전 고정 문자열**: `faxstat` 미호출, 버전 "6.0.7" 하드코딩
- **AUDIT-13 CUPS 인쇄 수신 처리 스텁**: 딕셔너리만 모의 반환, 실제 팩스 발송 큐 연동 없음
- **AUDIT-15 미구현 바코드·OCR 헬퍼**: `return None` 스텁만 존재
- **AUDIT-16 `faxrcvd` 미정의 변수 참조**: `faxname` 변수 미정의(`NameError`) + 예외 무시로 조용히 실패
- **AUDIT-17 발송 큐 작업 삭제 실패 은폐**: `faxrm` 실패해도 항상 `return True`, 사용자에게 성공 메시지 표시

**Low (4건)**
- **AUDIT-14 주소록/배포목록 ID 1번 하드코딩 폴백**: ID 1 요청에 첫 번째 행 강제 매핑
- **AUDIT-18 잘못된 임포트 경로**: `avantfax.*` 대신 `namifax.*`로 통일 필요

**§3 종합 평가 및 정상화 로드맵**

**Phase 1: 보안 취약점 즉시 제거**
- AUDIT-01: `auth.py` 하드코딩 조건 제거
- AUDIT-02: `faxqueue.py` `shell=True` 제거, 파라미터 분리 실행
- AUDIT-03: `admin.py` 시스템 로그 검색 SQL 인젝션 방어

**Phase 2: 가짜 바이너리·더미 생성 로직 제거**
- AUDIT-04: `inbox.py` 합성 PDF 제거, 404 응답
- AUDIT-05: `helpers.py` 0바이트/가짜 헤더 제거, 실패 전파
- AUDIT-06: `ajax.py` Acme Corp 자동완성 제거

**Phase 3: 미구현 비즈니스 로직 정상화**
- AUDIT-07: `sendfax.py` 모의 성공 제거, 실제 상태 반영
- AUDIT-10: `settings.py` DB 로드/저장 연동 구현
- AUDIT-11: `admin.py` 백업/재부팅 실제 구현
- AUDIT-13: `printer.py` FaxQueue 연동 구현
- AUDIT-15: `helpers.py` 바코드/OCR 서비스 호출
- AUDIT-16: `faxrcvd.py` 변수 버그 수정
- AUDIT-17: `faxqueue.py` 실제 실패 검사 + 뷰 오류 메시지

**Phase 4: UI 폴백·임포트 정리**
- AUDIT-08: `sendfax.py` 하드코딩 폴백 제거
- AUDIT-09: 템플릿 Acme Corp/고정 날짜/ttyS0 제거
- AUDIT-12: `admin.py` 실제 `faxstat` 호출
- AUDIT-14: 특수 폴백 제거
- AUDIT-18: `avantfax` 임포트를 `namifax`로 통합

## 문서가 주장하는 수치·상태

- E2E Golden Master: 68개 100% 통과 (당시 상태)
- 단위 테스트: 402개 100% 통과 (당시 상태)
- 골든 마스터 검증 환경 제약: HylaFAX 서버 데몬 부재, 실제 모뎀/프린터 미연결, 빈 데이터베이스
- 감사 범위: 뷰(views/), 도메인 서비스(services/), CLI 훅(cli/), 공통 헬퍼(common/helpers.py), 템플릿(templates/)
- 감사 일자 및 조치: 2026년 10월 1일
- 조치 결과: 18개 항목 전수 TDD 리팩토링 및 100% 무회귀 조치 완료 (당시 선언)

## 낡았을 가능성이 큰 부분

- 문서 작성 일자가 2026-10-01이고 "조치 완료" 선언이 되어 있지만, 이는 그 시점의 상태이며 이후 코드 변경이 있었을 수 있음
- 18개 항목의 "조치 완료"가 실제 코드에서 여전히 존재할 수 있음(예: AUDIT-10 `settings.py`, AUDIT-11 시스템 관리, AUDIT-04 합성 PDF 등)
- Critical/High로 분류된 보안 취약점(AUDIT-01 인증 백도어, AUDIT-02 셸 인젝션)이 실제로 제거되었는지 현재 코드에서 확인 필요
- "100% 무회귀 조치 완료"는 당시 테스트 통과 기준이며, 이후 신규 기능 추가로 회귀 가능성 존재
- 문서가 삭제된 파일(커밋 01f2f64)이라 현재 코드의 상태 반영이 안 될 수 있음

## 관련 주제 페이지

[[architecture-and-modules]] [[authentication-and-security]] [[testing]] [[known-gaps-and-decisions]] [[database-and-migrations]]
