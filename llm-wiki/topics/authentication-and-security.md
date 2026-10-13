---
title: 인증과 보안
type: topic
updated: 2026-10-03
verified: true
sources:
  - src/namifax/common/passwords.py
  - src/namifax/services/user_account.py
  - src/namifax/views/auth.py
  - src/namifax/views/settings_2fa.py
  - src/namifax/views/webauthn.py
  - src/namifax/views/saml.py
  - src/namifax/services/totp.py
  - src/namifax/services/webauthn.py
  - src/namifax/services/saml.py
  - src/namifax/services/fax_access.py
  - src/namifax/security.py
  - src/namifax/sessions.py
  - src/namifax/origin_guard.py
  - src/namifax/common/secretbox.py
  - src/namifax/__init__.py
  - src/namifax/db/bootstrap.py
  - src/namifax/db/seed.py
  - src/namifax/services/login_throttle.py
  - src/namifax/auth/alternate.py
  - src/namifax/common/settings.py
  - src/namifax/models/useraccount.py
  - src/namifax/models/types.py
  - src/namifax/cli/user.py
  - src/namifax/cli/encrypt_secrets.py
  - src/namifax/views/ajax.py
  - src/namifax/views/fax_rights.py
  - src/namifax/views/sendfax.py
  - src/namifax/main.py
  - systemd/namifax.service
  - "[[defects-report-summary]]"
  - "[[defects-rounds-1-2]]"
  - "[[defects-rounds-3]]"
  - "[[defects-rounds-4-5]]"
  - "[[porting-gaps]]"
  - "[[operations-checklist]]"
  - "[[migrating-from-avantfax3]]"
---

# 인증과 보안

이 페이지는 2026-10-02 시점(`git log` HEAD `47295d4`, 로그인 시도 제한·SAML Issuer 검사·`NAMIFAX_SESSION_SECURE` 도입 커밋 `403b549` 이후)의 `src/`·`tests/` 를 직접 읽고 쓴 것이다. 과거 결함 보고([[defects-report-summary]], [[defects-rounds-1-2]] 등)는 당시 시점의 주장이며, 아래에서 코드로 다시 확인한 항목만 현재 상태로 적었다. 시험은 이 세션에서 실행하지 않았고 시험 이름과 목적만 읽었다(통과 여부는 확인하지 않음). 다른 주제: [[architecture-and-modules]], [[database-and-migrations]], [[operations-and-deployment]], [[known-gaps-and-decisions]], [[migration-from-avantfax]].

## 1. 비밀번호 해시

- 새로 쓰는 해시는 Argon2id(`argon2-cffi` 라이브러리 기본값)이다. 비용은 `NAMIFAX_ARGON2_TIME_COST`, `NAMIFAX_ARGON2_MEMORY_COST`, `NAMIFAX_ARGON2_PARALLELISM` 환경변수로 조정한다. [코드] `src/namifax/common/passwords.py` (`_hasher`, `hash_password`)
- 원본 AvantFAX 의 MD5(32자리 16진수)는 검증만 받아 준다. 판별은 "길이 32 + 16진수" 이고, `$argon2` 로 시작하면 Argon2, 그 밖의 형식은 항상 불일치다. 예외는 던지지 않는다. [코드] `passwords.py` (`_is_md5`, `verify_password`)
- 로그인에 성공한 계정이 MD5 해시를 갖고 있으면 그 자리에서 Argon2id 로 교체한다(`needs_rehash`). 비밀번호가 틀리면 아무것도 바꾸지 않는다. [코드] `src/namifax/services/user_account.py` `login()`; 시험 `tests/unit/test_password_hashing.py` (`test_an_md5_account_logs_in_and_is_upgraded`, `test_a_wrong_password_does_not_upgrade_anything`)
- `NAMIFAX_PASSWORD_HASH=md5` 이면 새 비밀번호도 MD5 로 쓰고 업그레이드는 하지 않는다. 원본 PHP 와 한 DB 를 같이 쓰는 동안을 위한 스위치다(원본은 Argon2 를 읽지 못함). [코드] `passwords.py` (`legacy_mode`, `needs_rehash`); 시험 `test_password_hashing.py` (`test_md5_mode_keeps_the_originals_format`, `test_in_md5_mode_nothing_is_upgraded`); 운영 안내는 [[operations-checklist]], [[migrating-from-avantfax3]] 4.3 [문서]
- 해시 열 폭: 마이그레이션 0026 이 `UserAccount.password`, `UserPasswords.pwdhash` 를 `String(64)` 에서 `String(255)` 로 넓힌다. [코드] `src/namifax/alembic/versions/20261002_0026_password_hash_width.py`; 시험 `test_password_hashing.py::test_the_columns_are_wide_enough_for_an_argon2id_hash`
- 비밀번호 재사용 방지용 이력(`UserPasswords`)에는 평문이 아니라 해시를 저장한다. [코드] 시험 `tests/unit/test_user_passwords.py::test_the_hash_not_the_password_is_stored`, `test_password_hashing.py::test_the_history_holds_argon2id_hashes`
- 비밀번호 길이: 기본 최소 8, 최대 15 이다(`MIN_PASSWD_SIZE`, `MAX_PASSWD_SIZE` 설정). 최대 15 는 원본 값을 그대로 가져온 것이며 현대 기준으로는 짧다. [코드] `src/namifax/common/settings.py` (`min_passwd_size`, `max_passwd_size`), `user_account.py` `change_password()`
- 테스트 스위트는 Argon2 비용을 낮춰(`tests/conftest.py` 상단 `setdefault`) 시험을 빠르게 한다. 운영은 라이브러리 기본값이다. [코드] `tests/conftest.py`

> 모순: [[defects-rounds-1-2]] 의 SEC-06("해시가 salt 없는 MD5")과 [[defects-rounds-4-5]] 의 "비밀번호 무염 MD5" 는 현재 코드에 해당하지 않는다. 새 해시는 솔트 있는 Argon2id 이고 MD5 는 기존 행을 읽기 위한 수용·업그레이드 경로로만 남았다(`legacy_mode` 켠 경우 제외, 그때는 의도적으로 MD5 를 쓴다).

## 2. 로그인 흐름

[코드] `src/namifax/views/auth.py`, `src/namifax/services/user_account.py`, `src/namifax/auth/alternate.py`

1. `POST /login`: 먼저 시도 제한(아래 8번)을 확인해 잠겨 있으면 비밀번호를 보지 않고 거절한다. 그 다음 대체 인증(PAM/pwauth 등, `alternate.enabled()`)이 켜져 있으면 그것을, 꺼져 있거나 `fallback()` 이 허용되면 계정 자체 비밀번호(`NFUserAccount.login`)를 검사한다. 시험 `tests/unit/test_alternate_auth.py`, `tests/unit/test_auth_pam.py`
2. 웹서버가 인증한 `REMOTE_USER` 로 들어오는 경로(`GET /login`)는 `alternate.webserver_login()` 이 켜진 경우에만 동작한다. 시험 `test_alternate_auth.py::test_the_web_server_login_is_off_unless_asked_for`, `test_remote_user_logs_in_when_the_web_server_authenticates`
3. 계정이 비활성(`acc_enabled`)이면 별도 메시지("Account is disabled")를 보이고 로그에 남긴다. 실패 로그의 비밀번호는 끝 3자리만 남기고 가린다(`XXXXXX` + 마지막 3자). 시험 `tests/unit/test_login_audit_log.py`
4. 비밀번호 만료·최초 로그인(`last_login` 없음)·관리자 초기화(`wasreset`) 중 하나면 로그인 쿠키를 발급하기 전에 `/pwdexpired` 로 보내 새 비밀번호를 정하게 한다. 이 페이지는 로그인 직후 세션에 보관된 계정 하나만 바꿀 수 있고 사용자 이름을 요청에서 받지 않는다. 시험 `tests/unit/test_forced_password_change.py` (`test_the_page_cannot_be_used_to_change_somebody_elses_password`, `test_two_factor_still_applies_after_the_change`)
5. 2단계 인증이 켜져 있으면 `session["2fa_pending_uid"]` 를 두고 `/login/totp` 로 보낸다. 코드가 맞아야 로그인 쿠키가 발급된다. 시험 `tests/unit/test_sso_and_2fa_login.py::test_a_user_with_2fa_logs_in_through_the_code_step`
6. 비밀번호 분실(`/forgot`): 이메일로 임시 비밀번호를 보내고, 메일 발송이 실패하면 이전 비밀번호를 되살린다(`undo_reset`). 새 비밀번호는 로그에 쓰지 않는다. 시험 `tests/unit/test_forgot_password.py`
7. 로그아웃은 GET 으로는 확인 화면만 보이고 CSRF 토큰이 있는 POST 로만 세션을 지운다. 시험 `tests/unit/test_logout_post.py`
8. 비밀번호 로그인 시도 제한(2026-10-03 변경: **계정 잠금은 관리자만 해제**): `POST /login` 에서 사용자 이름별·접속 주소별로 시도를 센다. 계정은 연속 실패가 5회(`NAMIFAX_LOGIN_MAX_FAILURES`)가 되면 잠기고, 그 뒤에는 올바른 비밀번호도 보지 않고 "Too many failed sign-in attempts. This account is locked until an administrator unlocks it." 를 돌려준다. 이 잠금은 **시간이 지나도 풀리지 않는다**(시험은 1년 뒤까지 확인). 계정 실패 횟수는 시간으로 만료되지 않고 마지막 성공 로그인부터 센다. 5번째 시도는 비밀번호를 확인하되 틀리면 그 순간 잠기고, 그 시도가 맞으면 잠기지 않는다(5번째에 처음 맞는 경우). 접속 주소는 한도가 10배(`IP_FACTOR`, 기본 50회)이고 `NAMIFAX_LOGIN_LOCK_MINUTES`(15분) 동안만 잠근다(사무실이나 프록시 하나가 한 주소로 보이기 때문). 존재하지 않는 이름도 똑같이 센다(없는 이름이 잠겨도 있는 이름과 같은 응답). 계수기는 `SystemConfig` 행(`login_throttle:user|ip:<sha256 앞 32자>`)에 JSON 으로 저장돼 워커가 여러 개여도 공유된다. 새 계정을 만들면 그 이름에 남아 있던 카운터를 지운다(남이 먼저 시도해 둔 이름이 잠긴 채 시작하지 않게). [코드] `src/namifax/services/login_throttle.py`, `views/auth.py` `login_post_view`; 시험 `tests/unit/test_login_account_lock.py`, `test_login_throttle.py`
   - 범위: `login_throttle` 은 `auth.py` 의 `POST /login` 에서만 호출된다(`grep -rn LoginThrottle src`). `REMOTE_USER` 로그인(`GET /login`), 패스키, SAML, `/pwdexpired`, `/forgot` 에는 적용되지 않는다. [코드]
   - 주소는 `request.remote_addr` 를 그대로 쓴다. 코드에는 `X-Forwarded-For` 를 해석하거나 `ProxyFix` 를 쓰는 곳이 없고(`grep -rn "X-Forwarded-For\|ProxyFix" src` 결과 없음), `deploy/nginx/namifax.conf` 는 `X-Forwarded-For` 만 넘긴다. 실제 서버(`wsgiref`)에 서로 다른 `X-Forwarded-For`·`X-Real-IP` 헤더를 단 틀린 로그인 3번을 보냈더니 세 번 모두 접속 상대 주소 `127.0.0.1` 의 카운터에 세어졌고, 헤더가 가리킨 주소의 카운터는 생기지 않았다(2026-10-03, 임시 SQLite DB). 따라서 프록시 뒤에서는 접속 상대가 프록시 주소 하나이므로 모든 사용자가 주소 한도(기본 50회)를 함께 소진한다. 헤더를 읽지 않으므로 헤더를 꾸며 한도를 피할 수는 없다. [코드] 실제 nginx 를 앞에 두고 확인하지는 않았다.
   - 해제 [코드]: 관리자 사용자 목록(`/admin/users`)에서 잠긴 계정에 "Locked" 표시와 "Unlock" 버튼(폼 토큰 필요, `unlock_uid` POST, 관리자 권한 화면)이 나오고, 서버에서는 `namifax unlock-user <이름>`(`cli/user.py` `run_unlock_user`)을 쓴다. 해제하면 그 계정의 카운터를 비운다. 비밀번호 찾기 화면(`/forgot`)이나 다른 로그인 방식의 성공은 잠금을 풀지 않는다(시험으로 확인한 것은 `/forgot`).
   - 한계(그대로 남은 것): 계정 잠금은 서비스 거부에 쓰일 수 있다. 남이 내 사용자 이름으로 5번 틀리면 관리자가 풀어 줄 때까지 내가 로그인하지 못한다. 이전에는 15분이면 풀렸지만 지금은 아니다. 관리자 계정도 같은 규칙으로 잠기며, 관리자 계정이 잠겼을 때는 서버에서 `namifax unlock-user` 를 써야 한다. 한도(5회)는 지침에 따른 값이다. [코드: `begin_attempt` 는 인증 여부와 무관하게 센다]
   - 동시 요청 [코드]: 시도는 **비밀번호를 확인하기 전에** 센다. `auth.py` 의 `POST /login` 이 `LoginThrottle.begin_attempt` 를 먼저 부르면 사용자 이름 키와 접속 주소 키의 행을 잠그고(`SystemConfigService.lock`, 사용자 이름이 항상 먼저), 둘 중 하나라도 잠겨 있으면 아무것도 세지 않고 거절해서 비밀번호를 보지 않는다. 아니면 이번 시도를 바로 1회로 센다. 한도에 닿는 시도는 확인하되 그 순간 계정을 잠근다(`locked` 표시, 시각 `since`). 비밀번호가 맞으면 `record_success(이름, 주소)` 가 사용자 이름을 지우고 주소 카운터에서 방금 센 1회와(그 시도가 만든 잠금도) 되돌린다(성공한 로그인이 사무실 전체의 주소 한도를 깎지 않게. 주소를 지우지는 않는다). 틀렸을 때는 이미 센 것이라 따로 기록하지 않는다. `record_failure` 는 이후에 세는 방식으로 남아 있고 로그인 화면은 쓰지 않는다.
   - 병렬 시도 [코드: 시험으로 확인]: 예전에는 "잠겼나" 확인과 실패 기록이 비밀번호 확인을 사이에 두고 떨어져 있어서, 한 번에 도착한 요청이 모두 잠금 확인을 통과해 한도보다 많이 확인되었다. 지금은 로그인 화면에 틀린 비밀번호를 동시에 30개 보내도 확인은 한도만큼만 일어나고 나머지는 "Too many failed sign-in attempts" 화면을 받는다(`test_login_throttle_reserve.py`, PostgreSQL·MySQL·MariaDB 25번 반복). 남는 대가: 로그인 시도마다(성공 포함) 한 번 쓰기가 생기고, 같은 사용자 이름이나 같은 주소의 요청은 이 트랜잭션이 끝날 때까지 줄을 선다.

> 모순: [[defects-rounds-1-2]] F3-01("2FA 가 로그인에서 전혀 강제 안 됨")은 현재 코드와 다르다. `_finish_login()` 이 `TotpService.is_totp_enabled` 를 검사해 코드 단계를 거치게 한다.

## 3. 2단계 인증(TOTP)

[코드] `src/namifax/services/totp.py`, `src/namifax/views/settings_2fa.py`, `src/namifax/views/auth.py`

- 방식: RFC 6238 TOTP(`pyotp`). 설정 화면에서 비밀키·`otpauth://` URI·QR 을 보여 준다. 가입 대기 중인 비밀키는 흐름 쿠키 세션에 암호화(`secretbox`)해서 둔다. 시험 `tests/unit/test_totp_enrollment.py` (`test_the_pending_secret_is_not_kept_in_the_clear` 등), `tests/unit/test_totp.py`, `tests/unit/test_totp_orm.py`
- 저장: 시드는 `secretbox.encrypt` 로 `UserTOTP.secret_key` 에 암호화 저장한다. 복호화가 안 되면(키 분실·틀림) 거부(fail closed)하고 로그에 남긴다. 시험 `tests/unit/test_secret_box.py::test_totp_seed_is_encrypted_and_still_verifies`, `test_a_seed_that_cannot_be_decrypted_locks_the_user_out_safely`, `test_a_totp_seed_stored_before_encryption_still_works`
- 복구 코드: 8개, 31자 알파벳(혼동 문자 제외)에서 10자, `XXXXX-XXXXX` 형식(약 49비트). 저장은 솔트 있는 scrypt 해시(`scrypt$<salt>$<digest>`)만 한다. 평문이던 옛 8자리 16진수 코드는 한 번 쓸 수 있게 계속 받아 준다. 6자리 숫자 입력은 TOTP 시도로만 보고 느린 해시 비교를 생략한다. 시험 `tests/unit/test_totp_recovery_codes.py` (`test_the_database_holds_only_salted_hashes`, `test_a_code_works_once_however_it_is_typed`, `test_codes_saved_before_hashing_still_work_once`)
- 무차별 대입 방어: 사용자별 실패를 DB 에 원자적으로 센다(`failed_attempts`, `locked_until`). 5회 실패 시 15분 잠그고, 잠금 중에는 올바른 코드도 거절한다. 시험 `tests/unit/test_totp_lockout.py` (마이그레이션 `20261001_0021_totp_lockout.py` 가 열 추가)
- 복사·내려받기: 복구 코드 화면은 클립보드 복사와 텍스트 파일 저장을 제공한다. 저장 파일에는 복구 코드만 들어가고 인증기 키는 넣지 않는다. 시험 `tests/unit/test_totp_copy_download.py`, 프런트 `src/namifax/static/js/twofa.js` (보안 컨텍스트가 아니면 복사 API 대신 대체 경로 사용 [코드: twofa.js 의 `isSecureContext` 분기만 확인])
- 끄기·복구 코드 재생성: 모두 CSRF 토큰이 필요하고, 코드(실패는 잠금에 반영)가 맞아야 하며 끄기는 비밀번호도 필요하다. 시험 `test_totp_enrollment.py` (`test_a_request_without_the_csrf_token_is_refused`, `test_disabling_needs_the_password_and_a_valid_code`, `test_wrong_codes_while_disabling_count_towards_the_lockout`)
- 관리자 CLI 로 사용자의 2FA 를 초기화할 수 있다(`namifax` 의 `reset-2fa`, `src/namifax/cli/user.py::run_reset_2fa`). 시험 `test_totp_enrollment.py::test_an_administrator_can_reset_a_users_2fa_from_the_command_line`
- 암호화 키가 없으면 설정 화면이 오류 대신 안내를 보인다. 시험 `test_totp_enrollment.py::test_without_an_encryption_key_setup_explains_instead_of_failing`

> 모순: [[defects-rounds-1-2]] SEC-07("TOTP 비밀키/백업코드 DB 평문")과 K08("TOTP 활성화 UI 경로 없음")은 현재와 다르다. 시드는 암호화, 복구 코드는 해시로 저장하고 `/settings/2fa/setup` 등(`src/namifax/routes.py` 의 `totp_*` 라우트)가 있다.

한계: 패스키와 SAML 로그인은 TOTP 단계를 거치지 않는다(§4, §5). [코드] `views/webauthn.py`, `views/saml.py` 는 `TotpService` 를 호출하지 않음. 패스키와 SAML 은 TOTP 를 쓰지 않는 것이 의도다(사용자 결정 2026-10-03). TOTP 는 비밀번호 로그인에만 적용된다. 코드에 근거 주석은 없다.

## 4. WebAuthn(패스키)

[코드] `src/namifax/services/webauthn.py`, `src/namifax/views/webauthn.py`, 모델 `src/namifax/models/userwebauthn.py`

- 라이브러리: `webauthn`(py_webauthn). 등록 옵션은 resident key(discoverable credential) 필수(`ResidentKeyRequirement.REQUIRED`, `require_resident_key=True`), 사용자 확인 `PREFERRED`, 증명 `NONE`. 그래서 로그인 화면이 사용자 이름 없이 패스키를 제안할 수 있다.
- RP ID 는 요청의 호스트에서 포트를 뗀 도메인이고, 기대 origin 은 `scheme://host` 이다(`_get_webauthn_service`). 따라서 패스키는 접속 도메인에 묶인다. 도메인을 바꾸면(예: IP 접속에서 도메인 접속으로) 등록한 패스키는 쓸 수 없고, 보안 컨텍스트(HTTPS)에서만 동작한다 [문서: MDN "Web Authentication API"(2026-10-03 조회): 보안 컨텍스트 전용이고, 서버는 origin 과 RP ID 가 기대한 값인지 검사하며, 서명은 사이트 origin 에 묶인다]. [코드, 측정 2026-10-03] RP ID 와 origin 은 요청의 `Host` 헤더와 WSGI 의 `wsgi.url_scheme` 로 만들고 `X-Forwarded-Host`·`X-Forwarded-Proto` 는 읽지 않는다. 라이브러리는 `expected_origin` 과 클라이언트가 보낸 origin 을 문자열로 비교한다(`webauthn/registration/verify_registration_response.py:140`). 동봉한 `deploy/nginx/namifax.conf`(443 에서 TLS 를 끝내고 백엔드에는 http 로 넘기며 `Host` 는 그대로 전달)와 같은 환경을 흉내 낸 요청으로는 기대 origin 이 `http://fax.example.com` 으로 계산되고 브라우저는 `https://fax.example.com` 을 보내므로 일치하지 않는다. 이 구성에서는 패스키 등록과 로그인이 실패하게 된다. 실제 브라우저와 보안 키로는 확인하지 못했다.
- 자격 증명 ID 는 base64url 문자열로 저장·조회한다(브라우저가 보고하는 `id` 와 같은 형식). 공개 키는 16진수 문자열로 저장한다(`credential_public_key.hex()`). 시험 `tests/unit/test_webauthn_orm.py`, `tests/unit/test_sso_and_2fa_login.py` (`test_a_passkey_logs_the_user_in_and_counts_the_use`)
- 챌린지는 일회용이다: 등록·인증 검증 모두 세션에서 `pop` 한다. 시험 `test_sso_and_2fa_login.py::test_a_passkey_needs_a_fresh_challenge`, `test_an_unknown_passkey_is_rejected`
- 서명 횟수(`sign_count`)는 검증 후 갱신하고 `last_used_at` 을 기록한다. 비활성 계정은 패스키로도 로그인할 수 없다(`login_webauth` 가 `acc_enabled` 를 검사). 시험 `test_a_passkey_cannot_log_in_a_disabled_account`
- 등록·목록·삭제는 로그인한 사용자만 쓴다(401). 삭제는 `uid` 를 같이 조건에 걸어 남의 패스키는 지워지지 않는다. 시험 `test_sso_and_2fa_login.py::test_registering_a_passkey_needs_a_session_and_a_login`, `tests/unit/test_pyramid_webauthn.py`
- 이 뷰들은 `@view_config` 에 `permission` 이 없다(앱 전체 기본 권한도 설정하지 않음). 인증이 필요한 뷰는 뷰 코드가 직접 사용자를 확인한다. 등록·삭제 POST 의 출처 확인은 §8 의 `origin_guard` 에 의존한다. [코드]
- 인증 검증은 `require_user_verification=False` 이다(PIN/생체 확인을 강제하지 않음). [코드] `services/webauthn.py`

> 모순: [[defects-rounds-3]] R3B-14("WebAuthn 챌린지가 일회용이 아님")와 [[defects-rounds-4-5]] R5F-01(저장된 패스키 조회 실패)은 현재 코드와 다르다. 챌린지는 `pop` 으로 한 번만 쓰이고 조회는 ORM `select` 이다. 패스키 로그인 후 세션 미생성(F3-15)도 현재는 `remember()` 로 쿠키를 발급한다.

## 5. SAML 2.0 서비스 공급자

[코드] `src/namifax/services/saml.py`, `src/namifax/views/saml.py`, 설정 화면 `src/namifax/views/admin.py`(SAML 항목), 템플릿 `admin_saml.jinja2`

설정은 `SystemConfig` 키 `saml_*` 로 저장한다(관리자 화면에서 편집): `saml_enabled`, `saml_idp_entity_id`, `saml_idp_sso_url`, `saml_idp_x509_cert`, `saml_jit_provisioning`, `saml_default_role`, 역할 매핑용 `saml_role_mapping`, `saml_role_attribute`, `saml_role_admin`, `saml_role_superuser`, `saml_role_can_del`, `saml_role_any_modem`, `saml_attr_modems`, `saml_attr_faxcats`, `saml_attr_didroutes`. SP 주소(entity ID, ACS, SLS)는 요청의 `application_url` 에서 만든다. 꺼져 있으면 로그인 화면의 SAML 버튼이 숨겨지고 `/auth/saml/login` 은 "설정되지 않음" 메시지로 돌려보낸다. 시험 `tests/unit/test_saml_security.py` (`test_the_button_is_hidden_until_saml_is_set_up`, `test_a_disabled_saml_does_not_redirect_even_with_an_idp`)

ACS(`POST /auth/saml/acs`)에서 `process_saml_response` 가 확인하는 것(순서대로 거절 사유 반환):

1. SAML 이 켜져 있고 IdP 인증서가 설정돼 있는지.
2. 이 브라우저가 시작한 로그인 요청의 ID(`expected_request_id`, 세션에 저장·한 번 `pop`)가 있는지. 없으면 거절. 시험 `test_a_response_without_a_started_sign_in_is_refused`
3. XML 을 DTD 금지·엔티티 해석 금지·네트워크 금지 파서로 읽는다. 시험 `test_xml_with_an_entity_bomb_is_refused`
4. `StatusCode` 가 Success 인지, `InResponseTo` 가 기대한 요청 ID 인지. 시험 `test_an_answer_to_another_request_is_refused`
5. 서명 검증(`signxml.XMLVerifier`, 설정한 IdP 인증서로). 서명된 요소에서만 이름·속성을 읽는다. 서명 없음/다른 IdP 서명/서명 후 변조 거절. 시험 `test_an_unsigned_response_is_refused`, `test_a_response_signed_by_somebody_else_is_refused`, `test_changing_the_signed_assertion_breaks_the_signature`, `tests/unit/test_saml.py::test_an_unsigned_response_is_not_believed`
6. Issuer: 관리자가 `saml_idp_entity_id` 를 설정했으면 서명된 Assertion 안의 `Issuer` 텍스트가 그 값과 같아야 한다(다르거나 없으면 `saml_wrong_issuer` 로 거절). 설정이 비어 있으면 검사하지 않고 경고를 남긴다("no IdP entity ID is configured..."). 시험 `test_a_response_from_another_issuer_is_refused_even_if_the_signature_is_good`, `test_the_configured_issuer_is_accepted`, `test_without_a_configured_issuer_the_check_is_skipped_with_a_warning`
7. `Conditions` 의 `NotBefore`/`NotOnOrAfter`(시계 오차 120초), Audience 가 SP entity ID 인지, `SubjectConfirmationData` 의 `Recipient`=ACS URL·`InResponseTo`·만료. 시험 `test_a_response_for_another_time_audience_or_address_is_refused`
8. 재전송 방지: assertion ID 를 만료 시각 + 300초까지 기억하고 두 번째는 거절. 이 기억은 프로세스 메모리(`_USED`)라 워커가 여러 개면 워커별로 따로다. 시험 `test_the_same_response_cannot_be_used_twice` [한계: 다중 워커 공유는 코드상 없음]
9. NameID 가 있어야 한다.

계정 연결: 기존 계정은 이메일로만 찾는다(NameID 의 `@` 앞부분으로 맞추지 않아 `admin@다른회사` 가 로컬 `admin` 으로 로그인하는 것을 막음). 없으면 JIT 프로비저닝이 켜진 경우에만 새 계정(비어 있지 않은 무작위 비밀번호, 사용자명은 비어 있는 이름 선택, `saml_default_role=admin` 이고 역할 매핑이 꺼진 경우에만 관리자)을 만든다. 시험 `tests/unit/test_sso_and_2fa_login.py` (`test_saml_never_attaches_to_an_account_by_the_local_part_of_the_name_id`, `test_saml_provisioning_picks_a_free_username_and_a_random_password`, `test_saml_without_jit_does_not_create_accounts`, `test_saml_refuses_disabled_accounts`)

역할 매핑(`saml_role_mapping=1`): 로그인할 때마다 IdP 가 준 `role_attribute` 값으로 `superuser`, `is_admin`(superuser 이면 함께 켬), `can_del`, `any_modem` 을 덮어쓴다. 해당 역할 이름(`role_admin` 등) 설정이 비어 있으면 그 권리는 항상 꺼진다(켜진 권리를 회수함). `attr_modems`/`attr_faxcats`/`attr_didroutes` 는 이름 목록을 모뎀·카테고리·DID 경로 ID 로 바꾸며, 없는 이름은 무시하고, 속성 이름 설정이 비어 있으면 그 열은 건드리지 않는다(`test_a_blank_attribute_name_leaves_that_setting_alone`). [코드] `saml.py::apply_role_mapping`. 시험 `tests/unit/test_saml_role_mapping.py` (`test_roles_set_the_flags`, `test_a_role_that_is_gone_takes_the_right_away`, `test_a_blank_attribute_name_leaves_that_setting_alone`, `test_the_roles_are_only_believed_when_signed`).

릴레이 상태는 `/` 로 시작하고 `//`·`\` 가 없는 경로만 허용해 오픈 리다이렉트를 막는다. 시험 `test_the_relay_state_stays_on_this_site`. ACS/SLS 는 IdP 가 다른 사이트에서 POST 하므로 `origin_guard` 예외다. 시험 `tests/unit/test_origin_guard.py::test_the_identity_providers_callbacks_are_exempt`

한계: AuthnRequest 에 서명하지 않는다(메타데이터도 `AuthnRequestsSigned="false"`). SLS(`saml_sls_view`)는 로그아웃 메시지를 검증하지 않고 흐름 쿠키 세션(`namifax_flow`)만 비우고 `/login` 으로 보낸다. 로그인 세션(`namifax_session` 토큰)은 파기하지 않는다. Keycloak 26 이 아닌 IdP(Okta, Entra ID 등)와의 연동은 시험하지 못했다고 과거 보고가 밝혔다. [코드] `saml.py::generate_sp_metadata`, `views/saml.py::saml_sls_view`; [문서] [[defects-report-summary]]

> 모순: [[defects-rounds-1-2]] K04("SAML 응답 서명/Audience/NotOnOrAfter/InResponseTo 검증 없음"), K05(설정 미사용), F3-15, F3-16 은 현재 코드와 다르다. 서명·Audience·기간·수신처·InResponseTo·재전송을 모두 검사하고 `saml_*` 설정을 읽는다. Issuer 는 이전 판에서는 비교하지 않았으나 커밋 `403b549` 이후 `saml_idp_entity_id` 가 설정돼 있으면 비교한다(위 6번). 다만 값이 비어 있으면 여전히 검사하지 않는다(경고만). [코드] `services/saml.py` `process_saml_response`

## 6. 권한 모델

[코드] `src/namifax/models/useraccount.py`, `src/namifax/security.py`, `src/namifax/services/fax_access.py`

- 계정 플래그(`UserAccount` 열): `is_admin`(관리 콘솔), `superuser`(모든 팩스), `can_del`(삭제 권리), `any_modem`(발송 시 "아무 회선" 선택), `pwd_reuse`, `acc_enabled`, `deleted`, `wasreset`. 모뎀·DID 경로·카테고리 제한은 `modemdevs`/`didrouting`/`faxcats` 에 `|` 로 이은 문자열이다.
- Pyramid ACL(`RootContext.__acl__`): 모두에게 `public`, 로그인 사용자에게 `view`·`send_fax`, `role:admin` 에게 `admin`, 그 밖은 `admin` 거부. `is_admin` 이거나 `superuser` 이면 `role:admin`, 아니면 `role:user` 로 취급한다(superuser 는 관리 콘솔도 쓸 수 있음). 단 비밀·인증서를 다루는 SMTP·프린터·스토리지·SAML 화면(`/admin/smtp`, `/admin/printers`, `/admin/storage`, `/admin/saml`)은 라우트 권한(`admin`)을 통과한 뒤 뷰가 다시 `superuser` 또는 `is_superadmin` 만 허용한다. `is_admin` 만 있는 일반 관리자는 403(커밋 `26fcf82`, 이전에는 `is_admin` 도 통과). [코드] `views/admin.py`(`admin_smtp_view` 등 4개); 시험 `tests/unit/test_admin_secret_pages_superuser.py`(읽기만 함, 실행 안 함). 시험 `tests/unit/test_security_policy.py`, `tests/unit/test_pyramid_authorization.py`
- 뷰마다 `permission` 을 지정한다. `admin` 은 22곳(`grep -rno 'permission="admin"' src/namifax/views`, 2026-10-02), `public` 은 로그인 관련 `auth.py` 9곳, `archive.py` 1곳(OpenSearch 설명서 `/search`), `default.py` 1곳(작은따옴표, `home`)에서 쓰고, 나머지 일반 화면은 `view`(로그인 사용자), 팩스 발송은 `send_fax` 다. 기본 권한(`set_default_permission`)은 설정하지 않으므로 `permission` 이 없는 뷰(`webauthn.py`, `saml.py`, `notfound`, `forbidden`, `no_database`)는 공개다. 시험 `tests/unit/test_anonymous_access.py::test_every_route_needs_a_login` 은 `PUBLIC` 으로 미리 뺀 12개 라우트(`home`, `login`, `logout`, `forgot`, `pwdexpired`, `login_totp`, `saml_*` 4개, `api_webauthn_auth_options`, `api_webauthn_auth_verify`)를 제외한 라우트를 익명으로 GET·POST 해 200 이 나오는 것이 `GET /search` 뿐이라고 단언한다(코드로 읽음, 실행하지 않음). `api_webauthn_register_*`·`credentials*` 는 뷰가 직접 401 을 돌려준다.
- 팩스 단위 권한(`FaxAccess`): superuser 는 설정된 모뎀·DID 경로의 모든 팩스를 본다. 그 밖의 사용자는 자기 모뎀(또는 DID 경로)·카테고리에 속한 팩스와 자기가 보낸 팩스만 보고 바꾼다. 삭제는 `can_del` 이 있어야 하며 거절은 로그("Access denied ...")에 남긴다. 권한은 요청마다 DB 에서 읽으므로 관리자의 변경이 즉시 적용된다. 시험 `tests/unit/test_fax_access_control.py` (`test_a_pdf_can_only_be_downloaded_with_the_right`, `test_deleting_needs_the_flag_and_the_right_ajax`, `test_a_refused_delete_is_logged` 등), `tests/unit/test_modemstatus_rights.py`
- `any_modem`: 발송 화면의 회선 드롭다운에 "Any Available Line (Auto)" 선택지를 줄지 결정한다. [코드] `src/namifax/views/sendfax.py` `_lines()`(`account.get("any_modem")` 이 참일 때만 "Any Available Line (Auto)" 선택지를 넣음)
- 플래그 열은 `LegacyBoolean` 타입으로 읽는다. 옛 코드가 문자열 `'False'` 로 써 둔 값을 `Boolean` 이 참으로 읽어 권한이 생기는 사고를 막기 위해, 알 수 없는 문자열은 거짓이다. 시험 `tests/unit/test_boolean_flags.py::test_the_orm_never_reads_the_text_false_as_true`

> 모순: [[defects-report-summary]] 의 USR-04("사용자별 모뎀 접근 제한 완전 비동작"), SEC-03(IDOR), USR-06(`/ajax/faxalter` 쉘 주입), SEC-04(`/ajax/deletefaxes` 반사 XSS)는 현재 코드에서 다르다. 모뎀·카테고리 제한은 `FaxAccess` 로 강제되고 시험이 있다. `fids` 는 숫자만 골라 `int` 로 바꾼다(`views/ajax.py::_fids`). 셸 주입 시험은 `tests/unit/test_security_audit_phase1.py` (`test_faxalter_safe_execution_and_meta_char_safety`, `test_killjob_safe_execution_and_meta_char_safety`).

## 7. 비밀 저장(secretbox)

[코드] `src/namifax/common/secretbox.py`, `src/namifax/__init__.py`(`set_default_key(settings.get("secret.key"))`), `src/namifax/cli/encrypt_secrets.py`

- 키는 환경변수 `NAMIFAX_SECRET_KEY` 가 우선이고 없으면 ini 의 `secret.key` 다. Fernet 키(44자 base64url)이거나 16자 이상 임의 문구(HKDF-SHA256 으로 키를 만듦)다. 쉼표로 여러 키를 주면 첫 키로 암호화하고 모든 키로 복호화한다(회전).
- 저장 값은 `enc:v1:<토큰>` 형식이다. 접두사가 없는 값은 옛 평문으로 보고 그대로 읽으며 다음 저장 때 암호화된다. `namifax encrypt-secrets` 가 한꺼번에 바꾼다(재실행 안전, 평문 복구 코드는 해시로 변환).
- 키가 없으면 평문으로 저장하지 않고 `SecretKeyError`, 틀린 키·훼손은 `SecretDecryptError`(호출자는 "비밀 사용 불가"로 처리). 사용처: 클라우드 스토리지 비밀 키(`SystemConfig.cloud_secret_key`), SMTP 비밀번호, TOTP 시드. 로그인 비밀번호는 읽을 필요가 없으므로 암호화가 아니라 해시다.
- 시험 `tests/unit/test_secret_box.py` (왕복, 틀린 키, 변조, 회전, 키 없음, 설정 화면·SMTP·TOTP·`encrypt-secrets`), `tests/unit/test_smtp_settings.py`, `tests/unit/test_cloud_storage.py`
- 시험 환경은 `tests/conftest.py` 가 고정 시험용 키를 환경변수로 넣는다(값은 여기 적지 않음).
- 키를 잃으면 암호화 값을 복구할 수 없다는 운영 경고는 [[operations-checklist]] [문서].

## 8. origin_guard, CSRF, 세션

- origin_guard(tween): POST/PUT/PATCH/DELETE 가 `Origin`(없으면 `Referer`)을 말하면 이 사이트(요청 host, `X-Forwarded-Host` 첫 값, ini `csrf.trusted_origins` 목록)여야 하고 아니면 403. `Origin: null` 은 거절. 둘 다 없는 요청(스크립트·시험 클라이언트)은 통과, GET 등은 검사하지 않는다. SAML `/auth/saml/acs`, `/auth/saml/sls` 는 예외. [코드] `src/namifax/origin_guard.py`, `src/namifax/__init__.py`(tween 등록); 시험 `tests/unit/test_origin_guard.py`
- 명시적 CSRF 토큰: 로그아웃, 2FA 설정 4종, 받은 팩스함·보낼 팩스함·모달 일부(회전·회사 지정 등)가 Pyramid `check_csrf_token` 을 쓴다. 그 밖의 대부분의 POST 는 토큰이 아니라 `SameSite=Lax` 쿠키와 origin_guard 에 의존한다. [코드] `grep -rn check_csrf_token src/namifax/views` 에서 import 를 뺀 호출 지점: `auth.py` 1(로그아웃), `inbox.py` 2(회전·회사 지정), `modals.py` 1, `outbox.py` 1, `settings_2fa.py` 1(`_guard()` 가 2FA 설정 4개 POST 뷰를 모두 대표). 시험 `tests/unit/test_state_changing_posts.py`, `test_logout_post.py`

> 모순: [[porting-gaps]] B3("상태 변경 POST 에 CSRF 토큰 없음, SameSite=Lax 의존")은 부분적으로만 맞다. 일부 흐름에는 토큰이 생겼고, origin_guard 가 추가됐다. 전 경로에 토큰이 있는 것은 아니다.

- 로그인 세션: 로그인하면 `SessionManager` 가 무작위 토큰(`secrets.token_hex(32)`)을 만들고, 쿠키 `namifax_session`(`HttpOnly; SameSite=Lax; Path=/`)에 담는다. 세션은 서버 프로세스 메모리의 딕셔너리이고 비활동 7200초 후 만료된다. 로그인 쿠키의 `Secure` 속성은 `session.secure`(ini)가 있으면 그 값이, 없으면 `NAMIFAX_SESSION_SECURE`(기본 `false`)가 정한다(`1`/`true`/`yes` 만 참; `security.py::_cookie_secure` 가 `remember` 와 `forget` 의 `Set-Cookie` 끝에 `; Secure` 를 붙임. 흐름 쿠키와 같은 규칙; 2026-10-02 커밋 `740e12e` 로 바뀜. 그 전에는 이 쿠키에 `Secure` 가 없었다).  `Authorization: Bearer` 헤더도 토큰으로 받는다. [코드] `src/namifax/security.py`, `src/namifax/sessions.py`; 시험 `tests/unit/test_sessions_module.py`, `test_security_policy.py::test_remember_and_forget`
- 흐름 상태용 서명 쿠키(`namifax_flow`; 2FA 대기, 패스키 챌린지, SAML 요청 ID, 임시 TOTP 비밀): `HttpOnly`, `SameSite=Lax`, 30분 시간 제한(`timeout=1800`), `Secure` 는 ini `session.secure` 가 있으면 그 값이, 없으면 환경변수 `NAMIFAX_SESSION_SECURE`(기본 `false`)가 정하며 `1`/`true`/`yes` 만 참이다(ini 가 환경변수보다 우선). ini 는 `namifax serve --config <ini>` 또는 `NAMIFAX_INI` 가 있을 때만 읽는다. 비밀은 `session.secret` 또는 `NAMIFAX_SESSION_SECRET`, 없으면 프로세스마다 무작위 값을 쓰고 경고를 남긴다(재시작·다른 워커에서 흐름 상태를 잃음). 시험 `test_sso_and_2fa_login.py::test_the_flow_cookie_is_http_only_and_same_site`, `tests/unit/test_session_secure_flag.py` (`test_it_is_off_by_default`, `test_the_environment_variable_turns_it_on`, `test_the_ini_wins_over_the_environment`), `tests/unit/test_serve_main_db.py`. `systemd/namifax.service` 는 `EnvironmentFile=-/etc/namifax.env` 로 환경변수를 받는다.

## 9. 알려진 보안 판단과 한계(코드 기준)

| 항목 | 현재 상태 | 근거 |
|---|---|---|
| 로그인 세션 저장소 | 메모리. 재시작하면 모두 로그아웃, 워커가 여러 개면 서로 세션을 모름 | `sessions.py` |
| 로그인 쿠키 `Secure` | 기본 꺼짐. `session.secure`(ini) 또는 `NAMIFAX_SESSION_SECURE=true` 로 켬(ini 가 우선). 로그인(`remember`)과 로그아웃(`forget`)의 `Set-Cookie` 모두에 붙음. 커밋 `740e12e` 에서 바뀜 | `security.py::_cookie_secure`; `tests/unit/test_session_secure_flag.py` |
| 흐름 쿠키 `Secure` | 기본 꺼짐. `session.secure`(ini) 또는 `NAMIFAX_SESSION_SECURE=true` 로 켬 | `__init__.py::_session_factory`; `tests/unit/test_session_secure_flag.py` |
| 비밀번호 시도 제한 | `POST /login` 에 있음: 이름별 10회·주소별 50회 실패(기본) 시 15분 잠금, DB 공유. 패스키·SAML·`REMOTE_USER` 로그인에는 없음. 프록시 뒤 주소 판별은 위 §2 8번 참고 | `services/login_throttle.py`, `views/auth.py` |
| 비밀번호 최대 길이 | 기본 15(원본 계승) | `common/settings.py` |
| SAML 재전송 캐시 | 프로세스 메모리 | `services/saml.py::_seen_before` |
| SAML AuthnRequest | 서명하지 않음 | `generate_sp_metadata` |
| SAML Issuer 검사 | `saml_idp_entity_id` 가 설정된 경우에만(서명 검증 뒤). 비어 있으면 경고만 하고 통과 | `services/saml.py::process_saml_response` |
| 패스키 사용자 확인 | 강제하지 않음 | `require_user_verification=False` |
| 데모 계정 | 기본 꺼짐. SQLite 새 DB 에서 `NAMIFAX_DEMO_DATA=1`(또는 `demo.data = true`)일 때만 알려진 비밀번호의 계정이 생기고 서버 DB 에는 만들지 않는다. 첫 관리자는 `namifax createuser` 로 만든다(비밀번호 기본값 없음, 8자 이상) | `db/bootstrap.py`, `db/seed.py`, `cli/user.py`; 시험 `tests/unit/test_demo_data_optin.py` |
| 레거시 DB 의 기본 관리자 | 원본 설치의 기본 관리자는 로그인 시 비밀번호 변경을 강제 | 시험 `tests/unit/test_forced_password_change.py::test_the_installers_administrator_must_change_the_default_password`, `test_legacy_database_compat.py::test_the_legacy_administrator_can_log_in_and_must_change_the_password` |
| 시드 덮어쓰기 | 재시작해도 이미 있는 데이터를 바꾸지 않음 | `db/seed.py`, 시험 `tests/unit/test_schema_seed_safety.py` |

> 모순: [[defects-report-summary]] 의 ADM-01/COR-02("앱 시작마다 seed 가 운영 데이터 덮어쓰기")는 현재 코드와 다르다. `ensure_schema` 가 이미 최신이면 바로 돌려보내고, 시드는 비어 있는 테이블·새 DB 에서만 쓴다.
