from typing import Dict, Optional

try:
    from googletrans import Translator
except Exception:  # pragma: no cover
    Translator = None


_translator = Translator() if Translator else None


def translate_text(text: Optional[str], dest: str, src: Optional[str] = None) -> Optional[str]:
    """Safe translation helper with graceful fallback."""
    if text is None or text == "":
        return text
    if dest == src:
        return text
    if _translator is None:
        return text

    try:
        return _translator.translate(text, dest=dest, src=src).text
    except Exception:
        return text


def build_i18n_triplet(text: Optional[str], source_lang: str = "ru") -> Dict[str, Optional[str]]:
    """Build {ru, uk, en} values from source text."""
    source_lang = source_lang if source_lang in {"ru", "uk", "en"} else "auto"
    src = None if source_lang == "auto" else source_lang

    ru = translate_text(text, "ru", src=src)
    uk = translate_text(text, "uk", src=src)
    en = translate_text(text, "en", src=src)
    return {"ru": ru, "uk": uk, "en": en}

