"""Unit tests for NamiFAX pyramid.i18n localization system and CLI.

Following Pyramid 2.1 i18n documentation:
https://docs.pylonsproject.org/projects/pyramid/en/2.1-branch/narr/i18n.html
"""

from pyramid import testing
from pyramid.i18n import (
    TranslationString,
    TranslationStringFactory,
    get_localizer,
    negotiate_locale_name,
)

from namifax.cli.i18n import run_i18n
from namifax.i18n import _, custom_locale_negotiator, normalize_locale, SUPPORTED_LOCALES


class DummyUser:
    def __init__(self, language: str = "en"):
        self.language = language


class DummyRequest:
    def __init__(self, params=None, cookies=None, current_user=None, session=None):
        self.params = params or {}
        self.cookies = cookies or {}
        self.current_user = current_user
        self.session = session or {}


def test_supported_locales():
    assert "en" in SUPPORTED_LOCALES
    assert "ko" in SUPPORTED_LOCALES
    assert "ja" in SUPPORTED_LOCALES
    assert "de" in SUPPORTED_LOCALES
    assert "fr" in SUPPORTED_LOCALES
    assert "es" in SUPPORTED_LOCALES
    assert len(SUPPORTED_LOCALES) == 24


def test_locale_normalization():
    assert normalize_locale("zh") == "zh_CN"
    assert normalize_locale("zh-tw") == "zh_TW"
    assert normalize_locale("pt-br") == "pt_BR"
    assert normalize_locale("cz") == "cs"
    assert normalize_locale("rs") == "sr"
    assert normalize_locale("KO") == "ko"
    assert normalize_locale("en") == "en"


def test_locale_negotiator_priority():
    # 1. Query parameter takes highest precedence
    req1 = DummyRequest(
        params={"_LOCALE_": "ko"},
        cookies={"_LOCALE_": "en"},
        current_user=DummyUser("en"),
    )
    assert custom_locale_negotiator(req1) == "ko"

    # 2. Cookie takes precedence over user/session
    req2 = DummyRequest(
        cookies={"_LOCALE_": "ko"},
        current_user=DummyUser("en"),
    )
    assert custom_locale_negotiator(req2) == "ko"

    # 3. User profile language takes precedence over fallback
    req3 = DummyRequest(current_user=DummyUser("ko"))
    assert custom_locale_negotiator(req3) == "ko"

    # 4. Fallback returns None for default_locale_name ('en')
    req4 = DummyRequest()
    assert custom_locale_negotiator(req4) is None


def test_translation_multilingual():
    config = testing.setUp(settings={
        "pyramid.default_locale_name": "en",
        "jinja2.i18n.domain": "namifax",
    })
    try:
        config.add_translation_dirs("namifax:locale")
        config.set_locale_negotiator(custom_locale_negotiator)

        # 1. English (Default)
        req_en = testing.DummyRequest()
        loc_en = get_localizer(req_en)
        assert loc_en.translate(_("Inbox")) == "Inbox"
        assert loc_en.translate(_("Send Fax")) == "Send Fax"
        assert loc_en.translate(_("Archive")) == "Archive"

        # 2. Korean
        req_ko = testing.DummyRequest(params={"_LOCALE_": "ko"})
        loc_ko = get_localizer(req_ko)
        assert loc_ko.translate(_("Inbox")) == "받은 팩스함"
        assert loc_ko.translate(_("Send Fax")) == "팩스 보내기"
        assert loc_ko.translate(_("Archive")) == "보관함"

        # 3. Japanese (from legacy ja.php)
        req_ja = testing.DummyRequest(params={"_LOCALE_": "ja"})
        loc_ja = get_localizer(req_ja)
        assert loc_ja.translate(_("Inbox")) == "受信"
        assert loc_ja.translate(_("Send Fax")) == "FAXの送信"
        assert loc_ja.translate(_("Archive")) == "送信履歴"

        # 4. German (from legacy de.php)
        req_de = testing.DummyRequest(params={"_LOCALE_": "de"})
        loc_de = get_localizer(req_de)
        assert loc_de.translate(_("Inbox")) == "Eingang"
        assert loc_de.translate(_("Send Fax")) == "Fax senden"
        assert loc_de.translate(_("Archive")) == "Archiv"

        # 5. French (from legacy fr.php)
        req_fr = testing.DummyRequest(params={"_LOCALE_": "fr"})
        loc_fr = get_localizer(req_fr)
        assert "Réception" in loc_fr.translate(_("Inbox"))
        assert "Archives" in loc_fr.translate(_("Archive"))

    finally:
        testing.tearDown()


def test_i18n_cli_compile():
    # Test namifax i18n compile CLI command
    ret = run_i18n(["compile"])
    assert ret == 0
