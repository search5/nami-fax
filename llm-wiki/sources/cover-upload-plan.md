---
title: 팩스 표지 업로드 계획
type: source
updated: 2026-10-13
sources: ["docs/ko/dev/cover-upload-plan.md", "docs/en/dev/cover-upload-plan.md"]
verified: false
---

> 원본은 `docs/ko/dev/cover-upload-plan.md`(2026-10-03 작성, 2026-10-13 에 MkDocs 구조로 이동. 이전 경로 `docs/COVER_UPLOAD_PLAN.md`)다. 영문판 `docs/en/dev/cover-upload-plan.md` 가 있으나 이 요약은 한국어 원문 기준이다. 문서는 **계획이며 구현된 것은 없다**고 밝힌다. 현재 코드와의 대조는 [[known-gaps-and-decisions]] §3 에 있다.

## 요약

- 목적: 관리자 화면 `/admin/covers` 에서 표지 파일을 올리고(새 표지 추가·편집 모드 모두), 이미 올라간 파일을 찾아보아 고른다. [[new-features-plan]] §3.5 가 약속했으나 구현하지 못한 부분이며, 위키 `known-gaps-and-decisions.md` §3 의 "표지 스튜디오" 줄이 "코드 존재"로만 적혀 구현이 끝난 것처럼 읽히는 점도 바로잡는다는 것이 배경이다.
- 확인된 현재 상태(2026-10-03 에 코드와 원본 `git show 9408385:legacy/avantfax/...` 를 읽어 확인): 원본은 업로드가 없고(서버에서 직접 복사) 파일 이름을 글자로 입력하며 파일 존재를 확인하지 않고, 같은 파일 이름은 "Cover page already exists"로 거절한다. 저장 뒤 편집하면 원본은 제목만 바뀌지만 NamiFAX는 파일 이름도 바뀐다(차이). 발송은 `AVANTFAX_INSTALLDIR/images/<파일>` 을 읽는다(`views/sendfax.py`, `services/sendfax_command.py`). `services/cover_studio.py` 의 `CoverStudioService` 는 `.ps`, `.pdf`, `.html`, `.jinja2` 를 받아 저장·등록하지만 **호출하는 곳이 없다**. 표지에는 업로드 크기 한도가 없다(첨부용 `NAMIFAX_MAX_UPLOAD_BYTES`, `services/upload_check.py` 는 있음).
- 발견한 어긋남 두 가지: (1) 서비스 기본 저장 위치 `/var/spool/hylafax/covers` 가 발송이 읽는 `images` 와 달라 올린 표지가 목록에는 보여도 발송 때 파일을 찾지 못한다. (2) 표지 생성기가 쓰는 형식은 `.ps`, `.html`/`.htm`(`USE_HTML_COVERPAGE` 필요)뿐이라 `.pdf`·`.jinja2` 는 올릴 수 있어도 쓰지 못한다.
- 목표: 업로드, 찾아보기, 올린 표지가 실제 발송에 쓰임, 원본 폼 계약 유지(제목·파일 이름 필수, 중복 등록 거절). 범위 밖: 썸네일 미리보기(`.ps` 변환 방법 미정), `.pdf`·`.jinja2` 표지, 표지 파일 삭제(등록 해제만 유지).
- 결정 대기 3건(`[NEEDS_CLARIFICATION]`, 확정 전에는 권장안으로 계획): D1 같은 이름 파일(기본 거절 + 덮어쓰기 체크 시에만 허용 권장), D2 업로드 형식을 `.ps`·`.html`(`.htm` 포함)로 축소, D3 편집 화면의 파일 이름 변경(원본처럼 제목만 바뀌게 할지; 결정 전에는 현재 동작 유지).
- 설계: 폼 계약(`title`, `file`, `cover_id`, `_submit_check`, 버튼 `create`/`save`/`delete`)은 그대로 두고 선택 요소로 `cover_upload`(multipart), `overwrite`, 찾아보기 목록, `csrf_token` 을 더한다. 기존 `title`+`file` 만 보내는 요청은 계속 동작해야 한다. 저장 위치는 `AVANTFAX_INSTALLDIR/images` 로 통일하고 `AVANTFAX_COVERS_DIR` 는 쓰지 않거나 같은 폴더를 가리키게 한다. 서비스에 파일 이름 검사(경로 구분자·숨김 파일 금지, 허용 문자 제한), 크기 상한(표지 전용, 첨부보다 작게), 내용 확인(`.ps` 는 `%!PS` 시작, `.html` 은 텍스트), 같은 이름 처리, 등록된 이름 거절을 더한다. 찾아보기는 같은 폴더의 허용 형식 파일만 이름 순으로 나열하고 사용 중인 표지(제목) 또는 "등록 안 됨"을 표시하며 상위 경로는 볼 수 없다. 화면은 Tailwind, 드래그앤드롭은 스크립트가 있을 때만(없어도 파일 선택 가능). 새 문구는 `ko/namifax.po` 에만 추가한다.
- 구현 순서(단계마다 시험 먼저): 서비스 → 뷰(`/admin/covers` 업로드·폼 토큰·권한) → 찾아보기·폼 → 발송 연결(발송 계획 수준 확인) → 문서·위키 갱신. 시험 계획은 서비스(형식·확장자·경로 섞인 이름·크기·같은 이름·등록 중복), 뷰(두 모드 업로드, 토큰 없음 거절, 비관리자 거절, 기존 방식, 목록 범위), 발송 연결로 나뉜다. DB를 새로 쓰지 않으므로 SQLite 시험이면 충분하되 전체 시험은 4개 DB에서 한 번 돌린다.
- 완료 기준: 위 시험 통과 + 전체 시험에서 새 실패 없음 + 업로드 표지가 발송 화면·계획에 반영 + 위키가 실제 상태로 갱신(PDF·Jinja2·썸네일은 "미구현").
- 위험: `images` 폴더 쓰기 권한(화면 오류 + 배포 문서), 덮어쓰기로 다른 표지 결과 변경(기본 거절 + 사용 중 표지 경고), 올린 HTML 안 스크립트(서버 변환용이라 화면 위험은 낮으나 변환 도구의 외부 자원 접근 확인 필요), `USE_HTML_COVERPAGE` 꺼짐(안내 + 시험), 원본과 다른 파일 이름 변경(D3).
- 확인하지 못한 것: HTML 표지 변환 도구 `html2ps` 의 외부 자원 접근, 실제 HylaFAX `faxcover` 와의 발송(명령 구성까지만 확인), 실제 배포의 `images` 폴더 소유자·권한.
