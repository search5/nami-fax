---
title: 다국어와 화면(Jinja2 + Tailwind)
type: topic
updated: 2026-10-03
sources: [src/namifax/i18n.py, src/namifax/__init__.py, src/namifax/routes.py, src/namifax/cli/i18n.py, src/namifax/cli/populate_ko.py, src/namifax/cli/populate_all_locales.py, src/namifax/cli/populate_missing_translations.py, babel.cfg, package.json, tailwind.config.js, src/namifax/static/css/input.css, src/namifax/templates/layout.jinja2, src/namifax/templates/admin_layout.jinja2, tests/unit/test_ko_catalog_complete.py, tests/unit/test_ko_pages.py, tests/test_i18n.py, src/namifax/templates/ (grep extends/main.css), src/namifax/static/, src/namifax/views/outbox.py, "[[architecture-md-part2]]", "[[agents-md-legacy-instructions]]"]
verified: true
---

# 다국어와 화면

## 로케일
- 지원 코드 24개: `en, ko, ja, de, fr, es, it, zh_CN, zh_TW, ru, nl, pt_BR, pt_PT, pl, ar, tr, sv, no, hu, el, cs, ro, bg, sr`. `src/namifax/locale/<코드>/LC_MESSAGES/namifax.{po,mo}` 가 모두 있고 템플릿은 `locale/namifax.pot`. [코드] `src/namifax/i18n.py` `SUPPORTED_LOCALES`, `git ls-files src/namifax/locale`
- 기본 로케일은 `en`(`pyramid.default_locale_name`, `setdefault`), 도메인은 `namifax`(`jinja2.i18n.domain`, `add_translation_dirs("namifax:locale")`). [코드] `src/namifax/__init__.py`
- 원본 AvantFAX 별칭을 받는다: `zh→zh_CN`, `zh-cn`, `zh-tw`, `pt-br`, `pt-pt`, `cz→cs`, `rs→sr`. 대소문자 무시. [코드] `src/namifax/i18n.py` `LEGACY_LOCALE_ALIASES`, `tests/test_i18n.py`
- 협상 순서(`custom_locale_negotiator`): 쿼리 `_LOCALE_` 또는 `lang` → 쿠키 `_LOCALE_` → `request.current_user.language` → 세션 `language` → 없으면 기본값. [코드] `src/namifax/i18n.py`, `tests/test_i18n.py::test_locale_negotiator_priority`
- `.mo` 는 저장소에 커밋된다(빌드 산출물이지만 추적 대상). [코드] `git ls-files` 에 `*.mo` 포함

## 문자열 표시 방식
- 템플릿은 `{{ _('...') }}` 를 쓰고 `jinja2.ext.i18n` 으로 추출한다. 파이썬 쪽 `_` 는 `namifax.i18n._`(`TranslationStringFactory("namifax")`). [코드] `babel.cfg`, `src/namifax/i18n.py`, `src/namifax/templates/layout.jinja2`
- `babel.cfg`: `src/namifax/**.py` 와 `src/namifax/templates/**.jinja2` 를 대상으로 한다. [코드] `babel.cfg`

## 카탈로그 갱신 절차
`namifax i18n {extract|update|compile|init}` 는 `pybabel` 을 감싼 것이다(`-l <로케일>` 은 init 에서 필수). [코드] `src/namifax/cli/i18n.py`
1. 문자열을 추가·변경한 뒤 `uv run namifax i18n extract` → `locale/namifax.pot` 갱신.
2. `uv run namifax i18n update` → 모든 `.po` 에 새 항목 병합. 새 항목은 빈 번역이거나 fuzzy 가 된다.
3. 한국어 번역을 채운다. 보조 스크립트 `namifax.cli.populate_ko` 는 파일 안의 사전 `KO_TRANSLATIONS` 로 `ko` `.po` 를 채우고 fuzzy 표시를 지운 뒤 `.po` 와 `.mo` 를 함께 쓴다(`namifax` 하위 명령에는 등록되어 있지 않다). [코드] `src/namifax/cli/populate_ko.py`
4. `uv run namifax i18n compile` → `.mo` 생성. 새 로케일은 `init -l <코드>`.
- 다른 22개 로케일(`LANG_FILE_MAP` 22개, `en`·`ko` 제외)용 보조 스크립트: `populate_all_locales`(원본 AvantFAX 언어 사전 `legacy/avantfax/includes/langs/*.php` 에서 채우고 `.po`·`.mo` 를 쓰며, 끝에 `en` 의 msgstr 을 모두 비운다), `populate_missing_translations`(`scratch/translations_<언어>.json` 을 읽어 `.po` 에 넣고 babel `compile` 을 서브프로세스로 실행). [코드] 두 파일
  > 모순(낡음): 두 스크립트의 입력인 `legacy/` 와 `scratch/` 는 현재 저장소에 없다(`ls` 로 확인, 2026-10-02). `legacy/` 는 `git checkout 9408385 -- legacy` 로 되살려야 `populate_all_locales` 가 동작하고, `scratch/` 는 직접 만들어야 한다.
- 주의: `tests/test_i18n.py::test_i18n_cli_compile` 가 `run_i18n(["compile"])` 을 실제로 실행하므로 시험을 돌리면 `.mo` 가 다시 쓰인다. 작업 트리의 `.mo` 가 변경될 수 있다. [코드] `tests/test_i18n.py`

## 한국어 완전 번역 규칙과 시험
- 규칙: `locale/namifax.pot` 의 모든 메시지가 `ko` 카탈로그에 번역(비어 있지 않고 fuzzy 가 아님)되어 있어야 하고, 번역은 영어 원문의 자리표시자(`%(name)s`, `%(n)d`, `%s`, `%d`)를 같은 개수·종류로 유지해야 한다. [코드] `tests/unit/test_ko_catalog_complete.py`
- 시험 3개(`test_every_message_of_the_template_is_translated_into_korean`, `test_translations_keep_the_placeholders_of_the_original_text`, `test_the_compiled_catalog_has_the_new_texts`): 템플릿 메시지 전부 한국어 번역됨 / 자리표시자 보존(위키 지시문의 `placeholders_translated` 에 해당하는 시험은 이 파일의 `test_translations_keep_the_placeholders_of_the_original_text`) / 컴파일된 `.mo` 가 새 문구를 가짐(`"Send Password"`→`비밀번호 보내기`, `"Schedule Send Time"`→`전송 시각 예약`). [코드] 같은 파일
- 화면 시험 `tests/unit/test_ko_pages.py`(시험 5개): `?lang=ko` 로 `/forgot`, `/sendfax`, `/login` 이 한국어로 나오고 영어 예시가 남지 않는지(`e.g. Jane Doe` 부재, `예: 김영희`, 세미콜론 안내 `세미콜론`, `Enter your username` 부재) 확인하며, `/forgot` 은 기본이 영어다(`Send Password`). [코드] 같은 파일
- 따라서 새 문자열을 추가하면 `.pot` 재추출 후 `ko` 번역과 `.mo` 컴파일까지 해야 시험이 통과한다. 다른 로케일의 완전성을 지키는 시험은 찾지 못했다(`tests/test_i18n.py::test_translation_multilingual` 은 `Inbox`/`Send Fax`/`Archive` 몇 개만 `en, ko, ja, de, fr` 에서 확인). [코드] `tests/` 검색 결과. 번역 완성도(2026-10-03, `babel` 로 `namifax.pot` 766개 메시지 중 번역이 비어 있지 않고 fuzzy 가 아닌 수): `ko` 766(100%), `en` 374(48.8%), 나머지 22개 로케일은 317~344(41.4~44.9%). 즉 `ko` 를 뺀 로케일은 절반 넘게 영어 원문으로 보인다.
> 모순: 위키 작업 지시에 `placeholders_translated` 라는 시험 이름이 있었으나 그 이름의 시험은 없다. [코드] `tests/` 전체 검색에서 해당 문자열 없음. 실제 이름은 `test_translations_keep_the_placeholders_of_the_original_text`.

## Tailwind CSS
- 스타일은 Tailwind CSS 3(`tailwindcss ^3.4`)이고 소스 `src/namifax/static/css/input.css`, 산출물 `src/namifax/static/css/main.css`(최소화, **저장소에 커밋됨**). [코드] `package.json`, `git ls-files`
- 빌드: `npm run build:css` = `npx tailwindcss -i ./src/namifax/static/css/input.css -o ./src/namifax/static/css/main.css --minify`. [코드] `package.json`
- **새 Tailwind 클래스를 템플릿이나 뷰에 쓰면 CSS 를 다시 빌드해 `main.css` 도 함께 커밋해야 한다.** 빌드 때 클래스를 스캔하는 곳은 `./src/namifax/templates/**/*.jinja2` 와 `./src/namifax/views/**/*.py` 뿐이다(그 밖의 위치에 쓴 클래스는 빠진다). [코드] `tailwind.config.js` `content`
- 테마: 색 `m3.*`(Material Design 3 밝은 테마, `m3.dark.*` 어두운 테마), 레거시 색 `af.*`, 반지름 `m3-*`, 그림자 `m3-1..5`. [코드] `tailwind.config.js`
- `input.css` 의 `@layer components` 는 `.m3-btn-filled` 와 `.inputsubmit`, `.m3-btn-tonal` 과 `.inputbutton`, `.m3-card` 와 `.af-box`, `input[type="text"]`, `select`, `textarea` 등 원본 클래스 이름에 같은 스타일을 입힌다. [코드] `src/namifax/static/css/input.css`
- CSS 캐시 버전 쿼리: 템플릿이 `/static/css/main.css?v=3.6.0` 처럼 고정 문자열로 링크한다. `layout.jinja2`, `admin_layout.jinja2` 와 단독 페이지 15개(총 17개 파일)가 각각 직접 적고 있어 값이 한곳에 모여 있지 않다. 정적 뷰 `cache_max_age=3600`. CSS 를 바꾸고 브라우저에 확실히 반영하려면 모든 `?v=` 를 함께 올려야 한다. [코드] `grep -rn "main.css" src/namifax/templates`, `src/namifax/routes.py`
- `static/theme.css` 는 존재하지만 `src/`, `tests/` 어디에서도 `theme.css` 문자열 참조를 `grep` 으로 찾지 못했다(2026-10-02). [코드] 저장소 전체(`llm-wiki` 제외)에서도 참조가 없고 첫 커밋(`82aa2d2 init`)부터 있던 파일이다(`git log --follow`, 2026-10-03). 저장소 안에서는 쓰이지 않았고 2026-10-03 에 사용자 결정으로 삭제했다([[known-gaps-and-decisions]] §2).

## 레이아웃과 템플릿 규칙
- 상속: `layout.jinja2`(사용자 화면, 흰 헤더 + 가운데 내비게이션 `Inbox/Send Fax/Outbox/Archive/Contacts`, 접근 키 `i s o a c`) 를 16개 템플릿이(15개는 `{% extends "layout.jinja2" %}`, `home.jinja2` 는 `"namifax:templates/layout.jinja2"`), `admin_layout.jinja2`(어두운 `slate-950` 배경의 관리자 콘솔) 를 17개 템플릿이 확장한다. [코드] `grep extends src/namifax/templates`
- 모달·팝업·로그인류(`modal_*`, `assignx`, `login`, `forgot`, `pwdexpired`, `logout`, `no_database`, `distrolist_helper`, `contact_picker`, `batch_delete` 등)는 상속 없이 자체 `<html>` 을 가진다(상속하지 않는 템플릿은 두 레이아웃 외 18개). [코드] `grep -L extends src/namifax/templates/*`
- 기본 `<html lang="en">` 고정이다(로케일에 맞춰 바뀌지 않음). [코드] `layout.jinja2`, `admin_layout.jinja2`
- 모든 템플릿에 들어가는 변수는 `create_app` 의 `BeforeRender` 구독자가 넣는다(`add_switches`: 스위치와 `server_name`, 이어서 `_add_page_counters`: 로그인한 경우 `num_inbox`, `user_full_name`, `modem_devices`; 예외는 삼킨다). 헤더의 `num_outbox` 는 여기서 넣지 않고 `views/outbox.py` 가 넘긴다. [코드] `src/namifax/__init__.py`, `src/namifax/views/outbox.py`
- JS 는 `static/js/{archive,livefilter,notify,scheduler,sendfax,storage,twofa}.js`. 본문 속성 `data-inbox-poll="30"`, `data-modem-poll="20"` 로 폴링 주기를 준다. [코드] `layout.jinja2`, `git ls-files src/namifax/static/js`
- 원칙(원본의 UI 일치, Tailwind 현대화)은 [[agents-md-legacy-instructions]] 에 기록된 옛 지침이며, 지금은 골든 마스터 비교가 없으므로 시험이 아니라 사람의 검토에 의존한다. [문서]/[코드] [[testing]]
- 관련: [[architecture-and-modules]], [[overview]]
