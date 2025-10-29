"""Utility helpers for translating user input to English.

The crawler relies primarily on English-language metadata.
These helpers translate French (or any other language) terms to English
whenever possible, but gracefully fall back to the original text when the
translation service or dependency is unavailable.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Iterable, Set

from activity_logger import log_event, log_exception

try:
    from deep_translator import GoogleTranslator  # type: ignore
except Exception:  # pragma: no cover - optional dependency failures are tolerated
    GoogleTranslator = None  # type: ignore

_TRANSLATOR = None
_TRANSLATOR_FAILED = False


def _get_translator() -> GoogleTranslator | None:
    global _TRANSLATOR, _TRANSLATOR_FAILED
    if _TRANSLATOR_FAILED:
        return None
    if _TRANSLATOR is None:
        if GoogleTranslator is None:
            _TRANSLATOR_FAILED = True
            log_event("TRANSLATION_DISABLED", "Bibliothèque deep_translator indisponible")
            return None
        try:
            _TRANSLATOR = GoogleTranslator(source="auto", target="en")
            log_event("TRANSLATION_READY", "Service de traduction initialisé")
        except Exception as exc:
            _TRANSLATOR_FAILED = True
            _TRANSLATOR = None
            log_exception("TRANSLATION_ERROR", "Initialisation du traducteur impossible", exc)
            return None
    return _TRANSLATOR


@lru_cache(maxsize=512)
def translate_to_english(text: str) -> str:
    """Translate ``text`` to English when possible.

    The function caches successful translations to avoid hammering the
    upstream service. In the event of an error, the original text is
    returned unchanged so the caller can continue operating.
    """

    if not text or not text.strip():
        return text

    translator = _get_translator()
    if translator is None:
        return text

    try:
        translated = translator.translate(text)
    except Exception as exc:
        log_exception("TRANSLATION_ERROR", "Échec de la traduction", exc, text=text)
        return text

    if not translated:
        return text

    cleaned_original = text.strip()
    cleaned_translated = translated.strip()
    if cleaned_translated and cleaned_translated.lower() != cleaned_original.lower():
        log_event(
            "TRANSLATION",
            "Texte traduit en anglais",
            original=cleaned_original,
            translated=cleaned_translated,
        )
    return cleaned_translated or text


def build_text_variants(text: str) -> Iterable[str]:
    """Return an ordered set of original + translated variants for ``text``."""

    variants = []
    cleaned = text.strip()
    if cleaned:
        variants.append(cleaned)
    translated = translate_to_english(cleaned)
    if translated and translated.lower() != cleaned.lower():
        variants.append(translated)
    # Preserve order but drop duplicates
    seen: Set[str] = set()
    ordered = []
    for value in variants:
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        ordered.append(value)
    return ordered
