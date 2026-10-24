import ctypes

from .lang_en import EN

LANGUAGES = {"cs": "Čeština", "en": "English"}
_CZECH_LIKE = {0x05, 0x1B}
_language = "cs"


def system_language() -> str:
    try:
        primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
    except (AttributeError, OSError):
        return "en"
    return "cs" if primary in _CZECH_LIKE else "en"


def set_language(code: str) -> None:
    global _language
    _language = code if code in LANGUAGES else system_language()


def language() -> str:
    return _language


def tr(text: str, **values) -> str:
    if _language == "en":
        text = EN.get(text, text)
    return text.format(**values) if values else text


def tr_count(count: int, forms: str) -> str:
    words = tr(forms).split("|")
    if _language == "cs":
        index = 0 if count == 1 else 1 if 2 <= count <= 4 else 2
    else:
        index = 0 if count == 1 else 1
    return f"{count} {words[min(index, len(words) - 1)]}"
