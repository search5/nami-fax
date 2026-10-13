---
title: 3라운드 결함 요약 (A-H)
type: source
verified: false
sources: 
  - "git show 01f2f64:docs/numfax-defects-details/round3-a.md"
  - "git show 01f2f64:docs/numfax-defects-details/round3-b.md"
  - "git show 01f2f64:docs/numfax-defects-details/round3-c.md"
  - "git show 01f2f64:docs/numfax-defects-details/round3-d.md"
  - "git show 01f2f64:docs/numfax-defects-details/round3-e.md"
  - "git show 01f2f64:docs/numfax-defects-details/round3-f.md"
  - "git show 01f2f64:docs/numfax-defects-details/round3-g.md"
  - "git show 01f2f64:docs/numfax-defects-details/round3-h.md"
updated: 2026-10-02
---

## 요약

3라운드는 당시 완성 상태인 NamiFAX 포팅의 모든 계층(뷰, 서비스, DB, CLI, 웹앱, UI)을 8개 파일 단위로 정독하여 162건의 당시 보고 결함을 발견했다. 심각도로는 높음 4건, 중간 75건, 낮음 83건이 섞여 있으며, 유니코드 숫자 형식 체크 우회, 기본값 1 으로 인한 데이터 삭제, 폐기된 회사 참조 고아화, 일괄 쓰기로 인한 동시 수정 충돌, 폴백 웹앱 무한 루프, 마이그레이션 실패로 인한 데이터 고립 등 핵심적인 결함들이 포함된다. 특히 배포 구조(wheel 미포함 avantfax, 이중 모듈)와 명세 대조(서비스 선택 기능 미구현, 필터 권한 무시 fail-open, 레거시 동작 미복제)에서 유래한 구조적 결함이 눈에 띈다.

## 라운드별 핵심

### 3라운드 A (views/admin, main, security 등 1227줄+)
- R3A-01 [중간] 유니코드 숫자(例: ²)가 isdigit()를 통과해 int() 500 - 6개 관리자 CRUD 라우트 확인
- R3A-06 [중간] 회사 삭제 시 팩스번호와 아카이브 참조를 고아로 남김 - 레거시는 예약 회사로 재배정
- R3A-09 [중간] 사용자 삭제의 관리자 보호 검사 우회(uid="01" 통과)
- R3A-14 [낮음] 시드가 조작된 감사 기록을 삽입하여 가짜 이벤트만 보임

### 3라운드 B (views/*.py 1997줄: ajax, helpers, modals 등)
- [높음] R3B-01: 이메일 연락처 "추가"가 1번을 덮어씀
- [높음] R3B-02: 배포목록 도우미가 회사 ID를 목록으로 저장(레거시 fnid|팩스 형식 미지원)
- [높음] R3B-03: /assign 모달의 회사 병합이 db 없이 항상 무동작, 결과는 조용히 성공 표시
- R3B-04 [높음] fid 기본값 1로 파라미터 없는 POST가 팩스 #1 삭제
- R3B-06 [중간] 이메일북 수정이 서비스 검증을 우회해 빈 값/오류 주소 저장
- R3B-14 [중간] WebAuthn 챌린지가 일회용이 아니라 재전송 공격 가능
- R3B-19 [낮음] 회전 링크가 JSON 페이지로 이동, 이전/다음 탐색 컨텍스트 전달 안 됨

### 3라운드 C (services 3417줄: 15개 모듈)
- [높음] R3C-01: 모뎀/라우트 목록이 비면 접근 제한 사라짐(fail-open)
- R3C-02 [중간] 카테고리 비교가 문자열 대 정수라 권한만 있는 사용자 상세 접근 거부
- R3C-06 [중간] PK 없으면 UPDATE가 INSERT로 떨어짐 - 중복 행이나 잘못된 삭제
- R3C-07 [중간] QueryBuilder가 None 조건을 col=NULL로 만들어 불일치(중복 검사 실패)
- R3C-11 [중간] 캐시된 dbdata 전체를 되써서 동시 변경이 되돌려짐(비활성 계정 부활)
- R3C-15 [낮음] reset_password가 튜플을 반환하여 실패도 참으로 평가

### 3라운드 D (services 2702줄: 특화 기능+auth+common)
명세 항목별 구현 검증: SmtpConfig, 클라우드 스토리지, 프린터, OCR 등 선택 기능의 명세 미충족 확인. 테스트된 새 결함 41건.

### 3라운드 E (CLI, 설정, 자산 1000줄+)
- [높음] R3E-02: faxcover가 바이너리 표지(cover.ps)를 UTF-8로 읽어 출력 손상
- [높음] R3E-03: faxcover PostScript 정화 없어 괄호/백슬래시가 PS 구문 깨고 코드 주입 가능
- R3E-05 [중간] faxinfo 출력에 Latin-1 바이트 있으면 전체 해석 버려 발신자/시각 손실
- R3E-07 [낮음] i18n init -l 이 기존 번역을 경고 없이 덮어씀
- R3E-17 [낮음] CLI 스크립트 실행 비트 제각각 - 일부만 PATH에서 실행 불가

### 3라운드 F (DB 계층 421줄+)
- [높음] R3F-02: 쓰기 실패 시 롤백 없어 다른 프로세스가 "database is locked" 받음
- [높음] R3F-03: seed의 INSERT OR REPLACE fid=1이 기존 팩스를 데모 레코드로 덮어씀
- [높음] R3F-04: 폴백 웹앱 /api/inbox/list가 무한 루프로 서버 메모리 고갈
- R3F-05 [중간] 폴백 웹앱 핸들러가 Session을 AFUserAccount 전용 API로 호출하여 500
- R3F-06 [중간] 폴백 웹앱 로그인이 구조적으로 성공 불가
- R3F-12 [중간] 신규 DB 시드에 위조된 감사 기록, 마이그레이션 순서로 첫 기동 abook_id NULL
- R3F-15 [중간] 전체 행 write-back으로 동시 수정 시 나중 저장이 다른 변경 덮어씀(lost update)

### 3라운드 G (배포 트리 및 모듈 이중화)
- [높음] R3G-01: wheel 배포 시 avantfax 부재로 모든 경로가 200 "Ready" 텍스트 스텁
- [높음] R3G-02: 폴백 JSON 로그인이 username 속성 부재로 500, 시드 계정 평문 비밀번호
- R3G-03 [중간] paste 진입점이 모듈과 이름 충돌하여 로드 실패
- R3G-04 [중간] editable 설치와 pythonpath로 avantfax 의존 가려움, 이중 로드
- R3G-05 [중간] 뷰가 avantfax 스텁에 묶여 namifax 수정이 닿지 않고, 엔진 클래스 이종
- R3G-06 [중간] CLI 5개 서브명령이 미디어 스텁인 avantfax 코드 실행 - 개선 우회

### 3라운드 H (템플릿, 인라인 JS 브라우저 점검)
- R3H-01 [높음] POST /delete가 fid 없이도 1번 팩스 삭제
- R3H-02 [중간] URL 쿼리 값 미인코딩으로 '&', '+', '#' 포함 시 깨짐
- R3H-06 [중간] 설정의 패스키 목록이 서버 500을 "등록된 키 없음"으로 표시
- R3H-12 [중간] 모바일 375px: 사이드바 펼쳐짐, 375px/768px에서 가로 스크롤
- R3H-14 [중간] 팩스 보기 화면에서 보관/삭제/메모/회사 동작과 이전/다음 이동 빠짐
- R3H-17 [중간] refax/note 모달이 가짜 기본값 미리 채움(+1-555-0199, "검토 완료" 등)

## 보고서가 주장하는 수치

- 3라운드 전체 새 결함: 162건 (높음 4, 중간 75, �음 83)
- A 16건, B 27건, C 31건, D 41건, E 21건, F 27건, G 10건, H 23건
- 읽은 코드: views 1997줄, services 3417줄, CLI 1000줄+, DB 421줄+, 템플릿/JS 브라우저 점검 45개 화면

## 한계·시험하지 못한 것

- 당시 보고자가 명시한 한계:
  - R3B-09: 웹오토 실제 인증기 없이 끝단 재현 불가
  - R3C-21: 제목에 개행 있는 실제 팩스 통지 불가(테스트 시드에 없음)
  - R3E-05: 실제 ISDN/CNAM 바이트 재현 못 함(가짜 faxinfo로만 확인)
  - R3F-21: MySQL 실제 wait_timeout 테스트 미실행
  - R3H-08: WebAuthn 실제 인증기 없음
  - R3G: docker 이미지 빌드 미실행, HylaFAX 바이너리 미사용
- 응급 상황/스케줄러 타이밍/고부하 시뮬레이션 전무
- 라우트 간 상호작용의 광범위 조합 테스트 부재

## 관련 주제 페이지

[[migration-from-avantfax]] [[architecture-and-modules]] [[database-and-migrations]] [[authentication-and-security]] [[scheduler-and-storage]] [[testing]] [[known-gaps-and-decisions]]
