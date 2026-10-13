# 설치 시작

## 요구 사항

- Python 3.11 이상
- 데이터베이스: SQLite(별도 설치 불필요), MySQL/MariaDB, PostgreSQL(서버 필요)
- HylaFAX: 실제로 팩스를 보내고 받을 때 필요
- Ghostscript(있으면): PostScript 변환과 보낸 팩스의 PDF 미리보기에 쓰입니다
- Tesseract(선택): 받은 팩스 본문 검색(OCR)

## 개발·시험용으로 바로 띄우기

```sh
uv sync                                    # 의존성 설치 (MySQL/PostgreSQL은 --extra mysql / --extra postgresql)
uv run namifax createuser -u admin         # 관리자 계정 만들기 (비밀번호는 물어봅니다. 기본값은 없습니다)
uv run namifax serve --host 127.0.0.1 --port 8000
```

`namifax serve`는 개발용 서버입니다. 데이터베이스는 `DATABASE_URL` 환경 변수로 정하고, 없으면 현재 폴더의 SQLite 파일을 만듭니다. 화면 스타일을 바꾸려면 `npm run build:css`로 Tailwind CSS를 다시 만들어야 합니다.

## 운영 서버에 설치

운영에서는 `production.ini`와 `pserve`(waitress) 또는 `systemd/namifax.service`를 씁니다. 순서는 다음과 같습니다.

1. HylaFAX 서버가 아직 없으면 [HylaFAX 서버 준비](hylafax-server.md)를 먼저 거칩니다.
2. [HylaFAX 연동 설치](hylafax.md)를 따라 환경 파일, HylaFAX 훅, 웹 서비스, 주기 작업을 설정합니다.
3. 이메일로 팩스를 보내려면 [이메일로 팩스 보내기](email-to-fax.md)를 설정합니다. 수신 스풀 이동과 정리 같은 운영 지식은 [HylaFAX 운영 메모](hylafax-operations.md)에 있습니다.
4. [운영 점검 목록](operations-checklist.md)으로 보안 설정과 백업을 확인합니다.
5. 이미 AvantFAX 3.x를 쓰고 있다면 위 단계에 앞서 [AvantFAX 3.x에서 옮기기](migration.md)를 읽습니다.

설치 파일은 저장소의 `deploy/`(apache, nginx, postfix, hylafax, cups, cron.d, sudoers.d)와 `systemd/`에 있습니다.

## 이 매뉴얼 만들기

```sh
pip install -r requirements-docs.txt
mkdocs serve          # http://127.0.0.1:8000 에서 미리 보기
mkdocs build          # site/ 에 정적 사이트 생성
```
