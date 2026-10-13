# NamiFAX

NamiFAX는 HylaFAX 팩스 서버의 웹 프런트엔드입니다. [AvantFAX](http://www.avantfax.com) 3.x를 Python(Pyramid, SQLAlchemy)으로 다시 만든 것으로, 관리자는 브라우저로 사용자와 권한, 팩스 회선(모뎀), 분류 등을 관리하고 사용자는 사내 네트워크 안팎 어디서든 팩스를 보고 보내고 보관할 수 있습니다. 원본 AvantFAX가 쓰던 MySQL/MariaDB 데이터베이스를 그대로 이어서 쓸 수 있고, SQLite와 PostgreSQL도 지원합니다.

원본에 없던 기능이 있습니다: 2단계 인증(TOTP)과 패스키, SAML 로그인, Argon2id 비밀번호 해시, 관리자 화면에서 설정하는 정기 작업(APScheduler), S3 호환 스토리지로의 수신 팩스 업로드와 보존 정책, 인쇄해서 팩스 보내기(CUPS), 24개 언어(한국어는 전체 번역).

**상태**: 이 저장소에서는 실제 HylaFAX, CUPS, S3에 붙여 시험하지 못했습니다. 이 부분은 가짜 실행 파일과 mock으로만 확인했습니다. SAML은 Keycloak 26으로 시험했고, Okta·Entra ID 등 다른 IdP와의 연동은 시험하지 못했습니다. 운영에 쓰기 전에 시험 서버에서 `docs/ko/install/hylafax.md`와 `docs/ko/install/operations-checklist.md`를 한 번 거치십시오.

AvantFAX는 David D. Mimms, Jr. <david(at)avantfax.com>가 만들었습니다. NamiFAX는 그 코드를 바탕으로 다시 만든 파생물이며(Lee Ji-ho), 화면 이미지와 번역의 상당 부분이 원본에서 왔습니다.

**라이선스**: NamiFAX가 새로 쓴 코드와 문서는 BSD 3-Clause 라이선스입니다(`LICENSE`). 원본 AvantFAX에서 가져온 자료(이미지, 번역, 원본 설치 SQL, 기여자 목록)는 원본의 GNU General Public License 2판을 따릅니다(`COPYING.txt`, http://www.fsf.org/licenses/gpl.html). 어느 파일이 어느 쪽인지는 `NOTICE.txt`에 있습니다.

아이콘(AvantFAX 로고 제외)은 Silvestre Herrera가 디자인했고 GNU General Public License 2판으로 공개되었습니다.

원본 AvantFAX에 번역과 수정을 기여한 사람들은 `CONTRIBUTORS.txt`에 있습니다(원본의 목록 그대로).

## 설치와 시작

**요구 사항**: Python 3.11 이상, HylaFAX(실제 팩스를 보내고 받을 때), 데이터베이스(SQLite는 별도 설치 불필요. MySQL/MariaDB/PostgreSQL은 서버가 필요). 시스템에 Ghostscript가 있으면 PostScript 변환과 보낸 팩스의 PDF 미리보기가 동작합니다.

**운영 서버**: `docs/ko/install/hylafax.md`에 HylaFAX 훅 연결, 서비스, 정기 작업, 이메일로 팩스 보내기, 가상 프린터, 파일 권한, 설치 후 점검 순서가 있습니다. 설치 파일은 `deploy/`(apache, nginx, postfix, hylafax, cups, cron.d, sudoers.d)와 `systemd/`에 있습니다. 설정은 `/etc/namifax.env`의 환경 변수로 하며(원본의 `local_config.php`는 읽지 않습니다), 자세한 대응표는 `docs/ko/install/migration.md`에 있습니다.

**이미 AvantFAX 3.x를 쓰고 있을 때**: `docs/ko/install/migration.md`를 먼저 읽으십시오(기존 DB를 이어 쓰는 방법, 달라 보이는 점, 옛 주소 리다이렉트).

**개발·시험용으로 바로 띄워 보기**:

```sh
uv sync                                    # 의존성 설치 (MySQL/PostgreSQL은 --extra mysql / --extra postgresql)
uv run namifax createuser -u admin         # 관리자 계정 만들기 (비밀번호는 물어봅니다. 기본값은 없습니다)
uv run namifax serve --host 127.0.0.1 --port 8000
```

`namifax serve`는 개발용 서버입니다. 운영에서는 `production.ini`와 `pserve`(waitress) 또는 `systemd/namifax.service`를 쓰십시오. 데이터베이스는 `DATABASE_URL` 환경 변수로 정하고, 없으면 현재 폴더의 SQLite 파일을 만듭니다. 화면 스타일을 바꾸려면 `npm run build:css`로 Tailwind CSS를 다시 만들어야 합니다.

**시험**: `uv run pytest tests -k "not serverdb"` (서버 DB 시험은 별도 설정이 필요합니다: `llm-wiki/topics/testing.md`).

## 문서

`docs/`에 한국어·영어 매뉴얼(가이드, 설치, 사용 매뉴얼, 관리자 매뉴얼)이 MkDocs(Material 테마) 소스로 있습니다. `pip install -r requirements-docs.txt` 후 `mkdocs serve` 로 미리 보고, `mkdocs build` 로 `site/` 를 만듭니다.

`llm-wiki/`에 이 프로젝트의 구조, 보안, 스케줄러와 스토리지, HylaFAX 연동, 알려진 한계가 코드와 대조해 정리되어 있습니다(`index.md`부터 읽으십시오). 위키를 만들고 갱신하는 규칙은 `llm-wiki/CLAUDE.md`에 있습니다.

## SUPPORT

이 저장소의 이슈로 문의하십시오(https://github.com/search5/nami-fax). 원본 AvantFAX 3의 상용 지원처로 안내되던 YetOpen S.r.l.(www.yetopen.it)과 iFAX Solutions, Inc(www.ifax.com)는 원본에 대한 안내이며, NamiFAX를 지원한다는 뜻은 아닙니다.

## LANGUAGES

`ar bg cs de el en es fr hu it ja ko nl no pl pt_BR pt_PT ro ru sr sv tr zh_CN zh_TW`(24개).

새 언어를 추가하거나 번역을 고치려면:

```sh
uv run namifax i18n init -l <언어코드>      # 새 언어 (이미 있으면 update)
uv run namifax i18n extract                # 화면 문구 추출
uv run namifax i18n update                 # 번역 파일 갱신
# src/namifax/locale/<언어코드>/LC_MESSAGES/namifax.po 를 번역한 뒤
uv run namifax i18n compile
```

화면에 문구를 추가할 때는 `_()` 로 감싸고 한국어 번역을 함께 채우십시오(`tests/unit/test_ko_catalog_complete.py`가 빠진 번역을 잡습니다).
