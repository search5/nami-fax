"""NamiFAX Internationalization (i18n) and Localization (l10n) module.

Standardized on the official `pyramid.i18n` package API:
https://docs.pylonsproject.org/projects/pyramid/en/2.1-branch/narr/i18n.html
"""

from __future__ import annotations

from typing import Any

# Re-export core pyramid.i18n interfaces as the single standard
from pyramid.i18n import (
    TranslationString,
    TranslationStringFactory,
    default_locale_negotiator,
    get_localizer,
    make_localizer,
    negotiate_locale_name,
)

__all__ = [
    "_",
    "TranslationString",
    "TranslationStringFactory",
    "get_localizer",
    "make_localizer",
    "negotiate_locale_name",
    "default_locale_negotiator",
    "custom_locale_negotiator",
    "SUPPORTED_LOCALES",
    "DEFAULT_DOMAIN",
]

DEFAULT_DOMAIN = "namifax"

# Standard translation string factory using pyramid.i18n.TranslationStringFactory
_ = TranslationStringFactory(DEFAULT_DOMAIN)

# Supported language codes (English primary, plus Korean and all 22 legacy AvantFAX languages)
SUPPORTED_LOCALES = (
    "en", "ko", "ja", "de", "fr", "es", "it",
    "zh_CN", "zh_TW", "ru", "nl", "pt_BR", "pt_PT",
    "pl", "ar", "tr", "sv", "no", "hu", "el", "cs", "ro", "bg", "sr"
)

# Legacy language code alias normalizer
LEGACY_LOCALE_ALIASES = {
    "zh": "zh_CN",
    "zh-cn": "zh_CN",
    "zh-tw": "zh_TW",
    "pt-br": "pt_BR",
    "pt-pt": "pt_PT",
    "cz": "cs",
    "rs": "sr",
}


def normalize_locale(code: str | None) -> str | None:
    """Normalize input locale code against standard list and legacy aliases."""
    if not code:
        return None
    c = code.strip().replace("-", "_")
    if code in LEGACY_LOCALE_ALIASES:
        return LEGACY_LOCALE_ALIASES[code]
    if c in LEGACY_LOCALE_ALIASES:
        return LEGACY_LOCALE_ALIASES[c]
    for loc in SUPPORTED_LOCALES:
        if loc.lower() == code.lower() or loc.lower() == c.lower():
            return loc
    return None


def custom_locale_negotiator(request: Any) -> str | None:
    """Custom locale negotiator following Pyramid 2.1 specification.

    Inspects the request to determine the appropriate locale name:
    1. Explicit query parameter `_LOCALE_` or `lang`
    2. Cookie `_LOCALE_`
    3. User profile setting `current_user.language`
    4. Session attribute `session['language']`
    5. Returns None to let Pyramid fallback to `pyramid.default_locale_name` (default: 'en')
    """
    # 1. Query parameter (_LOCALE_ or lang)
    if hasattr(request, "params"):
        param_lang = normalize_locale(request.params.get("_LOCALE_") or request.params.get("lang"))
        if param_lang:
            return param_lang

    # 2. Cookie (_LOCALE_)
    if hasattr(request, "cookies"):
        cookie_lang = normalize_locale(request.cookies.get("_LOCALE_"))
        if cookie_lang:
            return cookie_lang

    # 3. Authenticated user preference
    user = getattr(request, "current_user", None)
    if user:
        user_lang = normalize_locale(getattr(user, "language", None))
        if user_lang:
            return user_lang

    # 4. Session preference
    session = getattr(request, "session", None)
    if session and hasattr(session, "get"):
        session_lang = normalize_locale(session.get("language"))
        if session_lang:
            return session_lang

    # 5. Return None to let Pyramid use pyramid.default_locale_name
    return None
