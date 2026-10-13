# 로그 (추가만 한다)

`grep "^## \[" log.md | tail -5` 로 최근 항목을 본다.

## [2026-10-02] schema | 위키 시작
Karpathy 의 LLM Wiki gist(2026-04-04)를 읽고 [[CLAUDE]] 를 만들었다. 원본 자료는 현재 코드·문서와 git 의 삭제된 파일(커밋 01f2f64, 72a7324, 9408385)로 하고, 복사하지 않는다.

## [2026-10-02] ingest | 원본 문서 요약 17개 (하이쿠 6개 에이전트)
ARCHITECTURE.md(앞·뒤 절반), 결함 보고서(종합과 1~5라운드), 감사 보고서, 설계·계획·이력 문서, 운영·이전 가이드, AGENTS.md 를 `sources/` 로 요약했다. 모두 `verified: false`(문서가 주장하는 바이며 코드 확인 없음).

## [2026-10-02] topic | 주제 종합 11개 (소넷 4개 에이전트, 코드 대조)
`topics/` 를 코드를 읽어 확인하며 썼다. 문서와 코드가 달랐던 곳은 각 페이지에 `> 모순:` 으로 남겼다.

## [2026-10-02] lint | 첫 점검
형식(frontmatter)·링크·고아 페이지·비밀 값 점검: 문제 없음(HylaFAX 문법 `[[FAX: 번호]]` 는 코드 표기로 바꿔 링크로 오인되지 않게 함).
에이전트 주장 4건을 코드로 직접 확인: systemd 단위에 `EnvironmentFile` 없음, `upload_file` 의 바깥 호출처 없음, `export_phonebook` 이 개수가 아니라 0 을 반환, `namifax serve` 가 `wsgiref` 로 `create_app` 을 설정 없이 호출. 모두 일치.
코드 쪽 결함 후보(위키에는 `> 모순:` 으로 기록, 아직 고치지 않음): 전화번호부 작업 요약이 항상 "0 entries", 정기 실행이 프로세스 간 동시 실행을 막지 않음, 환경 파일이 서비스에 전달되지 않음, `namifax serve` 가 ini 설정을 읽지 못함.

## [2026-10-02] topic | 코드 수정 반영과 [코드] 전체 재검증
직전 두 커밋 `740e12e`, `26fcf82` 의 변경을 현재 코드로 확인해 topics 에 반영했다.
로그인 쿠키 `Secure` 가 `session.secure`/`NAMIFAX_SESSION_SECURE` 를 따름(authentication), 시스템 기능 데몬 상태가 `pgrep` 실제 값(known-gaps), 숫자 판정 `isdecimal`·비밀 화면 superuser 한정·가상 프린터 `sendfax` 연결을 known-gaps 새 행으로 기록.
hylafax-integration 의 "sendfax 를 호출하지 않는다"와 scheduler-and-storage 의 "일반 관리자도 `/admin/storage` 가능"을 정정, operations 3.1 의 환경 파일 따옴표 경고를 문서화·시험됨으로 갱신.
`cli/print_in.py` 가 `pyproject.toml`·`main.py`·`deploy/` 어디에도 연결돼 있지 않다는 점은 다시 확인해 그대로 남김. 시험은 읽기만 했다.

## [2026-10-02] topic | 마무리: 추가 수정과 푸시
`[코드]` 재검증 뒤에 더 고친 것: 로그인 쿠키 `Secure`(`NAMIFAX_SESSION_SECURE`), 시스템 기능 화면의 데몬 상태를 `pgrep` 실제 값으로, 숫자 판정 `isdigit`→`isdecimal`(위첨자 숫자 500), 가상 프린터가 실제로 `sendfax` 에 넘김과 `namifax print-in`·CUPS 백엔드 연결, 환경 파일 값에 `&`·공백이 있으면 큰따옴표, SMTP·프린터·스토리지·SAML 화면은 슈퍼유저만.
위키 반영: [[authentication-and-security]], [[known-gaps-and-decisions]], [[hylafax-integration]], [[operations-and-deployment]], [[scheduler-and-storage]]. 일반 시험 2274개 통과(AI 실행). 서버 DB 시험은 AI 가 돌리지 않았고, 선생님이 4개 DB 통합 시험을 직접 실행했다고 알려 주셨다. 커밋 `9408385..21a56e2` 푸시.
알고도 고치지 않은 것과 이유는 [[known-gaps-and-decisions]] 5절에 모았다.

## [2026-10-02] ingest | 원본 문서 2개 삭제(PORTING_GAPS, NEW_FEATURES_PLAN)
`docs/PORTING_GAPS.md` 는 [[known-gaps-and-decisions]] 로, `docs/NEW_FEATURES_PLAN.md` 는 `topics/` 의 코드 기준 서술로 대체되어 삭제했다. 두 `sources/` 요약의 원본 경로는 `git show 61c3663:...` 로 바꿨다.


## [2026-10-02] topic | hylafax-operations-notes 추가, 설계 문서 삭제
`docs/hylafax_avantfax_integration_architecture.md` 에서 위키에 없던 내용(원문 3장 수신 스풀 이동, 4.2·5장 `faxqclean`·팩스 한 통의 파일 구조, 10장 발송 첨부 형식, 11장 print-to-fax)을 [[hylafax-operations-notes]] 로 옮기고 문서를 삭제했다. 아카이브 단계 파일 이름과 보관 폴더 설정(`AVANTFAX_ARCHIVE`), 업로드 형식 검사는 코드로 직접 확인했다. 나머지 장은 [[hylafax-integration]]·[[scheduler-and-storage]] 에 이미 있거나 설계안(미구현)이라 옮기지 않았다.

## [2026-10-02] topic | DB 계층 전환 기록 삭제, 유효한 규칙만 이전
`docs/history/db-layer-refactor-log.md` 에서 지금도 유효한 규칙을 코드로 확인해 [[database-and-migrations]] 8절(방언 주의점: NULL 정렬, 이름·타입)과 9절(시드 안전 규칙), [[testing]] 'mock 시험의 함정' 으로 옮기고 문서를 삭제했다. `DatabaseEngine`·`cli_unit`·`bridge_cli` 등 지금 없는 이름의 변천 과정은 옮기지 않았다. NULL 정렬 근거(`OrmRepository.select` 의 `CASE` 순위, 시험 `test_select_puts_null_values_first...`)는 직접 확인했다.

## [2026-10-02] schema | 라이선스 표기
프로젝트 라이선스는 BSD 3-Clause(`LICENSE`, `pyproject.toml` 의 `license`). 원본 AvantFAX 에서 가져온 자료(이미지 51개는 원본과 바이트까지 같음, 이어받은 번역, 원본 설치 SQL, 기여자 목록)는 GPL v2 로 남기고 `NOTICE.txt`·`COPYING.txt` 에 구분해 적었다. 원본 PHP 에서 이식한 코드를 BSD 로 배포해도 되는지는 법률 검토를 받지 않았다.

## [2026-10-02] lint | 서버 DB 시험 서술 정정
선생님이 4개 DB 통합 시험을 직접 실행했다고 알려 주셔서, "서버 DB 시험 미실행" 서술을 "AI 가 돌리지 않았고 선생님이 실행함(결과 세부는 기록 없음)"으로 고쳤다([[known-gaps-and-decisions]] 5.1, [[testing]], [[database-and-migrations]]).

## [2026-10-02] topic | 4개 DB 전체 시험 실행 결과 기록
커밋 `0c77622` 에서 SQLite(2278 passed), PostgreSQL 16.15(2417 passed), MySQL 8.4.11 과 MariaDB 10.11.16(각각 2415 passed, 2 failed)을 AI 가 직접 실행했다. 실패 2건은 스케줄러 시험이고 MySQL 계열의 기본 격리 수준(`REPEATABLE-READ`)에서만 나며 `READ-COMMITTED` 에서는 통과함을 직접 확인했다. 원인 설명 중 메커니즘은 [추정]으로 표시했다. 고칠지는 미결. 반영: [[testing]], [[database-and-migrations]], [[known-gaps-and-decisions]].

## [2026-10-02] topic | 겹치는 요청의 설정 쓰기와 로그인 실패 횟수를 고침, 서버 DB 시험 전부 통과
MySQL·MariaDB 의 스케줄러 시험 2건 실패를 따라가다 `SystemConfigService.set`(`merge`)이 낡은 스냅샷에서 INSERT 하려는 것을 확인했고, 같은 원인으로 로그인 제한이 병렬 실패를 덜 세는 것을 로그인 화면으로 측정했다(MySQL 3~40개 동시 실패가 1~3회로 기록, 오류 화면 70~90%). `set` 을 DB 별 원자적 upsert 한 문장으로, 카운터를 `locked_update`(행 잠금)로 바꿨다(`c353db5`). 저장점+재시도 방법은 MySQL 계열에서 교착을 내서 버렸다. 서버 3종 각 2443 passed. 반영: [[testing]], [[database-and-migrations]], [[authentication-and-security]], [[known-gaps-and-decisions]].

## [2026-10-02] topic | 로그인 시도를 비밀번호 확인 전에 세도록 바꿈
한 번에 도착한 요청은 모두 "잠겼나" 확인을 통과해 한도보다 많이 확인되던 점(검사-후-행동 사이의 틈)을 `LoginThrottle.begin_attempt`(행 잠금 후 먼저 센다, 성공하면 주소 카운터를 되돌린다)로 고쳤다(`baf16ca`). 로그인 화면에 틀린 비밀번호 30개를 동시에 보내도 확인은 한도만큼만 일어남을 서버 3종에서 시험으로 확인했다. 서버 3종 각 2456 passed, SQLite 2290 passed. 반영: [[authentication-and-security]], [[testing]], [[database-and-migrations]], [[known-gaps-and-decisions]].

## [2026-10-03] topic | 비밀번호 5회 초과 시 계정 잠금, 해제는 관리자만
요청: 시도가 5회를 넘으면 맞는 비밀번호도 막고 해제는 관리자만. `LoginThrottle` 계정 카운터에서 시간 만료와 시간제 잠금을 없애고(`locked` 표시), 한도 기본 5회, 주소 카운터는 시간제 잠금을 유지하되 한도를 10배로 해 50회를 지켰다(`c87a87d`). 해제는 관리자 사용자 목록의 Unlock 버튼과 `namifax unlock-user`. 반영: [[authentication-and-security]], [[operations-and-deployment]], [[migration-from-avantfax]], [[overview]], [[known-gaps-and-decisions]], [[testing]].

## [2026-10-03] ingest | 팩스 표지 업로드 계획
`docs/COVER_UPLOAD_PLAN.md` 를 요약해 [[cover-upload-plan]] 을 만들고 index 에 올렸다. 계획을 쓰며 코드를 대조해 표지 스튜디오가 화면에 연결되지 않았음을 확인했고, [[known-gaps-and-decisions]] §3 의 "코드 존재" 서술을 고쳐 모순 블록을 남겼다.

## [2026-10-03] lint | 오늘 고친 topics 의 날짜·근거 경로 정리
계정 잠금과 표지 업로드 계획을 반영한 topics 6쪽의 `updated` 를 2026-10-03 으로 맞추고, [[known-gaps-and-decisions]] 와 [[authentication-and-security]] 의 `sources` 에 새로 근거로 읽은 코드 경로를 더했다. 링크 점검: 이름 중복 없음, 고아 페이지 없음. `[[FAX: 번호]]` 형태로 잡히는 항목은 인쇄 문구 예시와 규칙 문서의 예시라 끊긴 링크가 아니다.

## [2026-10-03] lint | topics 의 `[추정]` 27곳 확인
`topics/` 의 `[추정]` 27곳을 코드 읽기와 실행으로 확인해 모두 `[코드]`, `[문서]`, 삭제, 결정 대기로 바꿨다. 코드로 확인: 계층 의존(엄격한 하향이 아님, 강제 장치 없음), 프록시 뒤 주소 카운터(헤더 무시, 측정), 패스키 origin 계산, `ProtectSystem=full`·`NoNewPrivileges` 동작(systemd 259 대조 실험), `wsgiref` 대 `waitress` 부하 비교, 정기 작업 표지 경쟁(4개 DB 39/40), print-in 의 PDF 태그, 전화번호부 출력 대조, S3 API 서버 상대 시험(에뮬레이터), 번역 완성도, `MagicMock` 사용 현황. 문서로 확인: HylaFAX `faxqclean`·`faxcron`·`hfaxd` 설명서(Debian manpages), MDN 웹 인증 API. 삭제: 근거 없는 NFS 일반론, 근거 없는 골든 마스터 삭제 이유 추론, 원문이 정의하지 않은 `REMOTE_*` 대응. 결정 대기: 패스키·SAML 의 TOTP 생략, `theme.css` 제거. 새로 확인된 결함 후보는 [[known-gaps-and-decisions]] 5.0 에 모았다. 확인하지 못한 것: 실제 HylaFAX 의 `JobFmt` 출력, 실제 브라우저의 패스키 동작, AWS S3·MinIO. 시험 중 스크립트 오류로 개발용 `namifax.db` 에 임시 행(로그인 카운터 4개, 로그 9개)이 들어갔고 모두 지웠다. 반영: [[architecture-and-modules]], [[authentication-and-security]], [[database-and-migrations]], [[hylafax-integration]], [[hylafax-operations-notes]], [[i18n-and-ui]], [[known-gaps-and-decisions]], [[operations-and-deployment]], [[scheduler-and-storage]], [[testing]].

## [2026-10-03] topic | 별도 스케줄러 `namifax scheduler` 제거
사용자 결정: 웹 서버 하나로 운영하고 systemd 별도 서비스는 쓰지 않는다. 같은 DB 의 스케줄러 프로세스가 둘이면 같은 작업을 같은 순간 시작하는 경쟁이 있었으므로(4개 DB 39/40) 별도 스케줄러를 없앴다. 제거: `namifax scheduler` 명령, `run_scheduler_standalone`, `scheduler_main`, 스크립트 `namifax-scheduler`, `systemd/namifax-scheduler.service`, `start(blocking=True)` 경로. 화면 안내문과 한국어 번역에서 별도 스케줄러 문구를 뺐다. 스케줄러는 웹 프로세스 안(`namifax serve`)에서만 돈다. 표지 경쟁 자체는 코드로 고치지 않았고, 같은 DB 에 웹 서비스를 둘 이상 띄울 때만 생긴다. 반영: [[scheduler-and-storage]], [[operations-and-deployment]], [[overview]], [[architecture-and-modules]], [[hylafax-integration]], [[migration-from-avantfax]], [[known-gaps-and-decisions]].

## [2026-10-03] topic | 웹 서비스를 한 DB 에 둘 이상 띄우는 시험
사용자 지적("같은 DB 에 웹 서비스를 둘 이상 띄우면 죽는다")을 임시 SQLite DB 에 `namifax serve` 두 개로 확인했다. 마이그레이션이 필요한 DB 에서 동시에 시작하면 두 번째가 `alembic_version` 중복 오류로 죽고, 시작한 뒤에는 A 에서 로그인한 쿠키가 B 에서 401 이다. 위 별도 스케줄러 제거 기록에서 "웹 서비스를 둘 이상 띄울 때만 경쟁이 생긴다"고 쓴 서술을 "한 DB 에는 웹 서비스를 하나만 운영한다"로 바로잡았다. 반영: [[operations-and-deployment]], [[scheduler-and-storage]], [[known-gaps-and-decisions]].

## [2026-10-03] topic | 결정 반영: TOTP 생략은 의도, theme.css 삭제
사용자 결정: 패스키와 SAML 은 TOTP 를 쓰지 않는 것이 의도이고(TOTP 는 비밀번호 로그인에만 적용), `static/theme.css` 는 삭제한다. `theme.css` 를 지우고 시험 `test_dead_static_files_removed.py` 를 더했다. TOTP 동작을 고정하는 시험은 만들었다가 필요 없다는 지적에 따라 지웠다. 이 결정을 처음에 "이 서비스는 TOTP 를 쓰지 않는다"로 잘못 적었다가 같은 날 바로잡았다. 반영: [[authentication-and-security]], [[known-gaps-and-decisions]], [[i18n-and-ui]].

## [2026-10-13] topic | 결정 반영: FaxOCR 제거, OCR 텍스트는 faxcontent 한 곳
원본 AvantFAX(`9408385:legacy/`)는 OCR 텍스트를 `FaxArchive.faxcontent` 에만 저장하고 `FaxOCR` 테이블이 없다. 이식본의 `FaxOCR` 는 검색 화면이 쓰지 않았고 수신 때 Tesseract 를 두 번 돌리는 원인이었다. 사용자 수락에 따라 모델·`OcrService` 의 저장/검색 메서드를 지우고 리비전 `0027` 로 테이블을 지운다. `faxrcvd` 는 OCR 을 한 번만 돌려 `faxcontent` 에 넣는다.

## [2026-10-13] schema | 위키를 `docs/llm-wiki/` 에서 저장소 루트 `llm-wiki/` 로 이동
사용자 요청. `README.md`, `docs/COVER_UPLOAD_PLAN.md`, `topics/i18n-and-ui.md`, `topics/hylafax-integration.md` 안의 경로를 바꿨다. 위키 안의 `[[링크]]` 는 이름만 쓰므로 영향이 없다.

## [2026-10-13] ingest | docs/ 5개 요약 갱신
문서가 `docs/ko/`·`docs/en/` MkDocs 구조로 옮겨져(`docs/ko/install/{hylafax,migration,operations-checklist}.md`, `docs/ko/dev/{cover-upload-plan,gcs-on-hold}.md`) 다섯 요약(`install-hylafax`, `migrating-from-avantfax3`, `operations-checklist`, `cover-upload-plan`, `future-gcs-storage`)을 한국어 원문 기준으로 다시 썼다. 새 테이블 5개·`FaxOCR` 제거(리비전 `0027`), 환경 파일 서식과 `NAMIFAX_INI`, CUPS 가상 프린터, 스케줄러 4종 등 편집된 내용을 반영했고 frontmatter 의 `sources` 를 새 경로와 영문판으로 바꿨다. `install-hylafax` 는 문서가 아직 "`namifax scheduler` 별도 서비스"를 말하는 점을 `> 모순:` 으로 남겼다(코드에서는 제거됨).

## [2026-10-13] lint | 위키 점검: 링크·고아·경로·수치
`[[링크]]` 끊김 없음(`[[FAX: 번호]]` 는 팩스 태그 예시 문자열), 고아 페이지 없음, index 누락 없음, frontmatter 5항목 모두 있음. 고친 것: ① 옛 `docs/*.md` 경로를 `docs/ko/...` 로(topics 5편), ② `database-and-migrations` 의 head `0026`→`0027`과 `FaxOCR` 삭제 반영, ③ `testing` 의 로그인 제한 "기본 10회"를 계정 5회(관리자만 해제)·주소 50회로, 삭제된 `test_ocr_orm.py` 언급 제거, ④ 삭제된 `NEW_FEATURES_PLAN.md` 를 `git show 61c3663:` 로 표기, ⑤ `operations-and-deployment` 에 MkDocs 매뉴얼 절 추가. topics 전체 [코드] 주장을 코드와 한 줄씩 다시 대조하지는 않았다(경로 존재, 수치 몇 건만 확인).
