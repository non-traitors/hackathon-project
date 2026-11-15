"""Turn a CheckResult into plain data a frontend can render.

Keeping this in one tested place means every UI shows verdicts, dates, labels and
language settings the same way, and the frontend never has to know the backend's
internal field names.
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

import languages as langs
import pipeline

# Pill styles the frontend can map to colors.
PILL_KIND = {
    "Supported": "supported",
    "Contradicted": "contradicted",
    "Unclear": "unclear",
    "In effect": "in_effect",
    "Proposed only": "proposed",
    "Blocked": "blocked",
}


def _pill(code: str, label: str) -> dict:
    local = langs.verdict_label(code, label)
    # Non-English users see their wording first; the English label stays beside it
    # because the README keeps the official verdict names in English.
    text = label if local == label else f"{local} · {label}"
    return {"label": label, "text": text, "kind": PILL_KIND[label]}


def legend(code: str) -> dict:
    """Pills explaining each label, for the "what each verdict means" strip."""
    return {
        "verdicts": [_pill(code, v) for v in ("Supported", "Contradicted", "Unclear")],
        "rule_statuses": [_pill(code, v) for v in ("In effect", "Proposed only", "Blocked")],
    }


def office_for(school_key: str, config: Optional[dict] = None) -> dict:
    config = config or pipeline.load_config()
    s = config["schools"][school_key]
    return {"name": s["office"], "url": s["office_url"]}


def to_ui(result: pipeline.CheckResult, school_key: str, config: Optional[dict] = None) -> dict:
    """Everything a frontend needs to draw one answer."""
    config = config or pipeline.load_config()
    code = result.language
    pills = [_pill(code, result.verdict)]
    if result.rule_status != "Not applicable":
        pills.append(_pill(code, result.rule_status))

    sources = []
    for s in result.sources:
        sources.append(
            {
                "title": s.title or s.url,
                "url": s.url,
                "domain": urlparse(s.url).hostname or "",
                "category": result.school if s.scope == "school" else "U.S. Government",
                "date": s.date,  # None when the page states no date: never invented
                "date_text": s.date or langs.ui_text(code, "date_unknown"),
                "quote": s.quote,  # always the original English wording
                "quote_translation": s.quote_translation,
            }
        )

    office = office_for(school_key, config)
    return {
        "verdict": result.verdict,
        "pills": pills,
        "headline": result.headline or result.explanation,
        "explanation": result.explanation,
        "applies_to": result.applies_to,
        "exceptions": result.exceptions,
        "sources": sources,
        "clarifying_question": result.clarifying_question,
        "next_step": result.next_step,
        "question_for_office": result.question_for_office,  # English, to send to the office
        "claim_in_english": result.claim_in_english,
        "out_of_scope": result.out_of_scope,
        "show_ask_office": result.verdict == "Unclear",
        "office": office,
        "disclaimer": langs.ui_text(code, "disclaimer").format(office=office["name"]),
        "rtl": langs.is_rtl(code),
        "beta": not langs.is_reviewed(code),
        "beta_text": langs.ui_text(code, "beta"),
        "language": code,
        "cached": bool(result.timing.get("cached")),
    }
