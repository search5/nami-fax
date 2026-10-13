"""The new texts show up in Korean when Korean is chosen (``?lang=ko`` or the ``_LOCALE_`` cookie)."""

from __future__ import annotations


def test_the_lost_password_page_is_in_korean(testapp):
    page = testapp.get("/forgot?lang=ko")
    assert "비밀번호 보내기" in page.text and "이메일 주소" in page.text


def test_the_send_fax_form_is_in_korean(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    page = testapp.get("/sendfax?lang=ko")
    assert "전송 시각 예약" in page.text and "만료 시간" in page.text


def test_english_stays_english(testapp):
    assert "Send Password" in testapp.get("/forgot").text


def test_the_send_fax_hints_and_examples_are_in_korean_and_name_the_semicolon(testapp):
    testapp.post("/login", {"username": "admin", "password": "password", "_submit_check": "1"})
    page = testapp.get("/sendfax?lang=ko")
    assert "세미콜론" in page.text and "예: 김영희" in page.text and "e.g. Jane Doe" not in page.text
    assert "쉼표로 구분하세요" not in page.text


def test_the_login_examples_are_in_korean(testapp):
    page = testapp.get("/login?lang=ko")
    assert "사용자 이름을 입력하십시오" in page.text and "Enter your username" not in page.text
