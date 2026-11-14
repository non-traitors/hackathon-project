import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import pipeline
from pipeline import CheckError, _LLMOutput, _LLMSource, _host_allowed, check_claim, validate_output

DOCS = [
    {
        "url": "https://studyinthestates.dhs.gov/work",
        "title": "Working in the U.S.",
        "text": "F-1 students may work on campus up to 20 hours per week while school is in session.",
        "date": None,
        "scope": "federal",
    }
]


def _out(verdict, sources):
    return _LLMOutput(
        verdict=verdict,
        rule_status="Not applicable",
        explanation="x",
        applies_to=[],
        exceptions=[],
        sources=sources,
        clarifying_question=None,
        next_step="",
    )


def test_valid_citation_kept():
    out = _out("Contradicted", [_LLMSource(url=DOCS[0]["url"], quote="up to 20 hours per week")])
    sources, verdict = validate_output(out, DOCS)
    assert verdict == "Contradicted" and len(sources) == 1 and sources[0].date is None


def test_invented_url_dropped_and_verdict_downgraded():
    out = _out("Supported", [_LLMSource(url="https://example.com/fake", quote="anything")])
    sources, verdict = validate_output(out, DOCS)
    assert sources == [] and verdict == "Unclear"


def test_fabricated_quote_dropped():
    out = _out("Supported", [_LLMSource(url=DOCS[0]["url"], quote="30 hours per week")])
    sources, verdict = validate_output(out, DOCS)
    assert sources == [] and verdict == "Unclear"


def test_unclear_without_sources_stays_unclear():
    sources, verdict = validate_output(_out("Unclear", []), DOCS)
    assert verdict == "Unclear"


def test_host_allowlist():
    assert _host_allowed("https://www.irs.gov/x", ["irs.gov"])
    assert not _host_allowed("https://irs.gov.evil.com/x", ["irs.gov"])
    assert not _host_allowed("https://notirs.gov/x", ["irs.gov"])


def test_empty_and_long_claims_rejected():
    with pytest.raises(CheckError):
        check_claim("   ", "msu")
    with pytest.raises(CheckError):
        check_claim("x" * 10_000, "msu")


def test_unsupported_school_rejected():
    with pytest.raises(CheckError):
        check_claim("F-1 students can work", "waterloo")


def test_missing_keys_give_friendly_error(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    with pytest.raises(CheckError, match="EXA_API_KEY"):
        check_claim("F-1 students can work", "msu")


def test_rule_status_dropped_without_verified_citation(monkeypatch):
    out = _out("Supported", [_LLMSource(url="https://example.com/fake", quote="x")])
    out.rule_status = "Blocked"
    monkeypatch.setattr(pipeline, "search", lambda *a, **k: DOCS)
    monkeypatch.setattr(pipeline, "analyze", lambda *a, **k: out)
    r = check_claim("OPT is cancelled", "msu")
    assert r.rule_status == "Not applicable" and r.verdict == "Unclear"


def test_rule_status_kept_with_verified_citation(monkeypatch):
    out = _out("Contradicted", [_LLMSource(url=DOCS[0]["url"], quote="up to 20 hours per week")])
    out.rule_status = "In effect"
    monkeypatch.setattr(pipeline, "search", lambda *a, **k: DOCS)
    monkeypatch.setattr(pipeline, "analyze", lambda *a, **k: out)
    r = check_claim("30 hours", "msu")
    assert r.rule_status == "In effect"


def test_no_results_is_unclear_not_error(monkeypatch):
    monkeypatch.setattr(pipeline, "search", lambda *a, **k: [])
    r = check_claim("some claim", "uchicago")
    assert r.verdict == "Unclear" and r.sources == [] and r.school == "University of Chicago"
