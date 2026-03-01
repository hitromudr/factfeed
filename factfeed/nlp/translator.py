import asyncio
from typing import List

from deep_translator import GoogleTranslator


def get_translator_instance(target: str = "ru") -> GoogleTranslator:
    """Get a fresh translator instance for the target language to avoid thread-safety issues."""
    return GoogleTranslator(source="auto", target=target)


# Simple in-memory cache: {(text, target): translated_text}
_translation_cache = {}


async def translate_text(text: str, target: str) -> str:
    """Translate a single text string asynchronously."""
    if not text or target == "en":
        return text

    cache_key = (text, target)
    if cache_key in _translation_cache:
        return _translation_cache[cache_key]

    translator = get_translator_instance(target)
    try:
        loop = asyncio.get_running_loop()
        # deep-translator is synchronous, run in thread pool
        translated = await loop.run_in_executor(None, translator.translate, text)
        if translated:
            _translation_cache[cache_key] = translated
        return translated
    except Exception:
        # Fallback to original text on failure
        return text


async def translate_batch(texts: List[str], target: str) -> List[str]:
    """Translate a list of strings concurrently."""
    if not texts or target == "en":
        return texts

    translator = get_translator_instance(target)
    try:
        loop = asyncio.get_running_loop()
        # GoogleTranslator.translate_batch is more efficient if supported,
        # but let's stick to concurrent single calls or batch if library supports it well.
        # deep-translator supports translate_batch.
        translated = await loop.run_in_executor(None, translator.translate_batch, texts)
        return translated
    except Exception:
        return texts
