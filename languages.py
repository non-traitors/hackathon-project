"""Language registry loader (data lives in languages.yaml).

Everything language-specific is read from the registry, so the backend and the
UI can't disagree about which languages exist or how they are written.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

LANGUAGES_PATH = Path(__file__).parent / "languages.yaml"
DEFAULT_CODE = "en"

_loaded: Optional[dict] = None


_starters: Optional[dict] = None


def _read(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_languages(path: Path = LANGUAGES_PATH) -> dict:
    global _loaded
    if path != LANGUAGES_PATH:
        return _read(path)["languages"]
    if _loaded is None:
        _loaded = _read(path)["languages"]
    return _loaded


def starters(code: str) -> list[str]:
    """Example claims in the language, falling back to English."""
    global _starters
    if _starters is None:
        _starters = _read(LANGUAGES_PATH).get("starters", {})
    return _starters.get(code) or _starters.get(DEFAULT_CODE, [])


def language_choices() -> dict[str, str]:
    """code -> display name, in registry order."""
    return {code: lang["display"] for code, lang in load_languages().items()}


def resolve_language(value: Optional[str], strict: bool = False) -> str:
    """Return a registry code for a code, display name, alias, or model name.

    An empty value means "no choice made" and gives English. An unknown name gives
    English too, unless strict=True, which raises ValueError so a caller can tell the
    user instead of silently answering in the wrong language.
    """
    langs = load_languages()
    if not value or not value.strip():
        return DEFAULT_CODE
    v = value.strip().lower()
    for code, lang in langs.items():
        names = [code, lang["display"], lang["model_name"], *lang.get("aliases", [])]
        if v in (str(n).lower() for n in names):
            return code
    if strict:
        raise ValueError(f"unsupported language: {value!r}")
    return DEFAULT_CODE


def model_language(value: Optional[str]) -> str:
    return load_languages()[resolve_language(value)]["model_name"]


def ui_text(code: str, key: str) -> str:
    """A UI string in the language, falling back to English if it is missing."""
    langs = load_languages()
    return langs.get(code, {}).get("ui", {}).get(key) or langs[DEFAULT_CODE]["ui"][key]


def verdict_label(code: str, label: str) -> str:
    langs = load_languages()
    return langs.get(code, {}).get("verdicts", {}).get(label) or langs[DEFAULT_CODE]["verdicts"].get(label, label)


def is_rtl(code: str) -> bool:
    return bool(load_languages().get(code, {}).get("rtl"))


def is_reviewed(code: str) -> bool:
    return bool(load_languages().get(code, {}).get("reviewed"))


def glossary_block(code: str) -> str:
    """Prompt lines fixing the wording of key terms, or '' for English."""
    g = load_languages().get(code, {}).get("glossary") or {}
    return "\n".join(f"- {term}: {gloss}" for term, gloss in g.items())


# General "work" words route to every work-related topic, as English "work" does.
KEYWORD_ALIASES = {"oncampus": ("work",), "opt": ("work",)}


def topic_keywords(topic: str) -> list[str]:
    """Routing keywords for a topic across every non-English language."""
    out: list[str] = []
    for lang in load_languages().values():
        kws = lang.get("keywords") or {}
        for name in (topic, *KEYWORD_ALIASES.get(topic, ())):
            out += [str(k) for k in kws.get(name, [])]
    return out


def speech_code(value: Optional[str], kind: str) -> Optional[str]:
    """ElevenLabs language code for a language: kind is "stt" (speech to text) or "tts".

    `value` may be a registry code or any name the picker uses (e.g. 繁體中文 gives yue,
    Cantonese). An unknown name gives None, so the caller lets ElevenLabs auto-detect
    rather than guessing a wrong language.
    """
    try:
        code = resolve_language(value, strict=True)
    except ValueError:
        return None
    return (load_languages()[code].get("speech") or {}).get(kind)
