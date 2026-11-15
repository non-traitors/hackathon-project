"""Run the agent for a frontend.

`check_claim(claim, language, school)` has the same name and arguments as the
function in app.py, and returns the same dict (built by ui_adapter.to_ui) with
two extra keys: `claim`, the claim this result answers, and `trace`, the agent's
steps. To put the agent behind the interface, app.py swaps its body for:

    return backend.check_claim(claim, language, school)

`stream(...)` yields each step as it happens, then the results, for a live
progress display. A pasted message can hold several claims; `check_all` returns
one dict per claim.
"""
from __future__ import annotations

import copy
import time
from typing import Iterator

import agent
import chat
import pipeline
import ui_adapter
from pipeline import CheckError

CACHE_SIZE = 64

# Only answers backed by verified sources are cached. An Unclear caused by a
# network blip, a usage limit, or a misjudged out-of-scope must not stick.
_cache: dict[tuple[str, str, str], tuple[float, list[dict]]] = {}


def clear_cache() -> None:
    _cache.clear()


def _school_key(school: str) -> str:
    """Accept a school key ("msu") or the name shown in the picker."""
    names = pipeline.schools()
    if school in names:
        return school
    for key, name in names.items():
        if name == school:
            return key
    raise CheckError("Please choose a supported school.")


def stream(text: str, language: str, school: str) -> Iterator[dict]:
    """Yield {"step": {...}} for each agent step, then {"results": [...]}."""
    key = ((text or "").strip(), language, school)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < pipeline.CACHE_TTL:
        yield {"results": copy.deepcopy(hit[1])}
        return
    school_key = _school_key(school)
    config = pipeline.load_config()
    for item in agent.run(key[0], school_key, None, language):
        if isinstance(item, agent.Step):
            yield {"step": item.model_dump()}
            continue
        results = [
            dict(ui_adapter.to_ui(r, school_key, config), claim=r.claim, trace=[s.model_dump() for s in r.trace])
            for r in item
        ]
        if all(r["sources"] for r in results):
            if len(_cache) >= CACHE_SIZE:
                _cache.pop(next(iter(_cache)))
            _cache[key] = (time.time(), copy.deepcopy(results))
        yield {"results": results}


def check_all(text: str, language: str, school: str) -> list[dict]:
    """Every claim found in the text, checked. One dict per claim."""
    results: list[dict] = []
    for item in stream(text, language, school):
        results = item.get("results", results)
    return results


def check_claim(claim: str, language: str, school: str) -> dict:
    """The first (usually only) result, in the shape app.py draws."""
    return check_all(claim, language, school)[0]


def chat_stream(message: str, history: list[dict], language: str, school: str) -> Iterator[dict]:
    """One chat turn. Yield {"step": {...}} for each step, then {"reply": {...}, "history": [...]}.

    `history` is what the last turn returned (start with an empty list). It holds only the
    student's words and verified quotes, and the caller keeps it; nothing is stored here.
    """
    school_key = _school_key(school)
    config = pipeline.load_config()
    for item in chat.respond(message, history, school_key, language):
        if isinstance(item, agent.Step):
            yield {"step": item.model_dump()}
        else:
            yield {"reply": ui_adapter.chat_to_ui(item, school_key, config),
                   "history": chat.remember(history, message, item)}
