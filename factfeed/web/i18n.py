"""Internationalization (i18n) support using Babel."""

from pathlib import Path
from typing import Callable

from babel.support import Translations
from fastapi import Request

SUPPORTED_LOCALES = ["en", "ru"]
DEFAULT_LOCALE = "en"
TRANSLATIONS_DIR = Path(__file__).resolve().parent.parent / "translations"

_translations_cache: dict[str, Translations] = {}


def load_translations(locale: str) -> Translations:
    """Load and cache translations for a specific locale."""
    if locale in _translations_cache:
        return _translations_cache[locale]

    # If locale is English (default), we might not have a translation file if we don't extract it.
    # But for consistency, let's try to load it. NullTranslations fallback handles missing files.
    translations = Translations.load(str(TRANSLATIONS_DIR), [locale])
    _translations_cache[locale] = translations
    return translations


def get_locale(request: Request) -> str:
    """Determine locale from query parameter or Accept-Language header."""
    # 1. Check query param ?lang=xx
    query_lang = request.query_params.get("lang")
    if query_lang in SUPPORTED_LOCALES:
        return query_lang

    # 2. Check header
    # Simple parsing: take the first language code from Accept-Language
    # e.g. "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7" -> "ru"
    accept_language = request.headers.get("Accept-Language")
    if accept_language:
        try:
            # Split by comma, take first, split by semicolon (weight), take first, split by dash, take first
            preferred = accept_language.split(",")[0].split(";")[0].split("-")[0]
            if preferred in SUPPORTED_LOCALES:
                return preferred
        except Exception:
            pass

    return DEFAULT_LOCALE


def get_translator(request: Request) -> Callable[[str], str]:
    """Return a translation function (gettext) bound to the request's locale."""
    locale = get_locale(request)
    translations = load_translations(locale)
    return translations.gettext
