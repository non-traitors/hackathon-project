"""Bridge between the Streamlit interface and the agent.

`check_claim(claim, language, school)` has the same name, argument order and
result shape as the placeholder in app.py, so the interface can swap in the real
backend with one import:

    from backend import check_claim

`stream(...)` gives the same results plus the agent's steps as they happen, for a
live progress display. Results are plain dicts, cached per (text, language,
school) so a Streamlit rerun does not pay for the same check twice.
"""
from __future__ import annotations

import copy
import re
from typing import Iterator
from urllib.parse import urlparse

import agent
import pipeline
from pipeline import CheckError

# Interface label -> the language name the model is asked to answer in.
LANGUAGES = {
    "English": "English",
    "العربية": "Arabic",
    "中文": "Mandarin Chinese",
    "繁體中文": "Cantonese (Traditional Chinese)",
    "Русский": "Russian",
    "O'zbekcha": "Uzbek",
}
HEADLINE_CHARS = 120

_cache: dict[tuple[str, str, str], list[dict]] = {}


def clear_cache() -> None:
    _cache.clear()


def _school_key(school: str) -> str:
    names = pipeline.schools()
    if school in names:
        return school
    for key, name in names.items():
        if name == school:
            return key
    raise CheckError("Please choose a supported school.")


def _headline(explanation: str) -> str:
    first = re.split(r"(?<=[.!?。！？؟])\s+", explanation.strip(), maxsplit=1)[0]
    return first[:HEADLINE_CHARS].strip()


def _source(s: pipeline.Source) -> dict:
    host = (urlparse(s.url).hostname or "").lower()
    return {
        "category": "University" if s.scope == "school" else "U.S. Government",
        "title": s.title or s.url,
        "domain": host[4:] if host.startswith("www.") else host,
        "url": s.url,
        "date": s.date or "",
        "quote": s.quote,
    }


def _to_dict(r: agent.AgentResult) -> dict:
    return {
        "claim": r.claim,
        # One pill: the rule status for rule-change rumors, otherwise the verdict.
        "verdict": r.rule_status if r.rule_status != "Not applicable" else r.verdict,
        "headline": _headline(r.explanation),
        "explanation": r.explanation,
        "sources": [_source(s) for s in r.sources],
        "applies_to": list(r.applies_to),
        "exceptions": list(r.exceptions),
        "clarifying_question": r.clarifying_question or "",
        "next_step": r.next_step,
        "question_for_office": r.question_for_office,
        "checked_at": r.checked_at,
        "trace": [s.model_dump() for s in r.trace],
    }


def stream(text: str, language: str, school: str) -> Iterator[dict]:
    """Yield {"step": {...}} for each agent step, then {"results": [...]}."""
    key = ((text or "").strip(), language, school)
    if key in _cache:
        yield {"results": copy.deepcopy(_cache[key])}
        return
    school_key = _school_key(school)
    for item in agent.run(key[0], school_key, None, LANGUAGES.get(language, "English")):
        if isinstance(item, agent.Step):
            yield {"step": item.model_dump()}
        else:
            _cache[key] = [_to_dict(r) for r in item]
            yield {"results": copy.deepcopy(_cache[key])}


def check_all(text: str, language: str, school: str) -> list[dict]:
    """Every claim found in the text, checked. One dict per claim."""
    results: list[dict] = []
    for item in stream(text, language, school):
        results = item.get("results", results)
    return results


def check_claim(claim: str, language: str, school: str) -> dict:
    """The first (usually only) result, in the shape app.py's placeholder returns."""
    results = check_all(claim, language, school)
    if not results:
        raise CheckError("We couldn't produce a reliable answer. Please try again.")
    return results[0]
