import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import agent
import backend
import pipeline


def _result(**kw):
    base = dict(
        verdict="Contradicted",
        explanation="No. The limit is 20 hours. Breaks differ.",
        claim="c",
        sources=[
            pipeline.Source(url="https://www.uscis.gov/i-765", title="I-765", quote="q", scope="federal"),
            pipeline.Source(
                url="https://oiss.isp.msu.edu/x", title="OISS", quote="q2", scope="school", date="2026-01-02"
            ),
        ],
        trace=[agent.Step(kind="plan", label="Choosing official pages to read")],
    )
    return agent.AgentResult(**{**base, **kw})


@pytest.fixture
def fake_run(monkeypatch):
    seen = []

    def run(text, school_key, context=None, language="English"):
        seen.append((text, school_key, language))
        yield agent.Step(kind="plan", label="Choosing official pages to read")
        yield [_result()]

    monkeypatch.setattr(agent, "run", run)
    backend.clear_cache()
    return seen


def test_check_claim_matches_frontend_shape(fake_run):
    r = backend.check_claim("c", "العربية", "Michigan State University")
    assert fake_run == [("c", "msu", "Arabic")]
    assert r["verdict"] == "Contradicted" and r["headline"] == "No."
    assert r["sources"][0] == {
        "category": "U.S. Government",
        "title": "I-765",
        "domain": "uscis.gov",
        "url": "https://www.uscis.gov/i-765",
        "date": "",
        "quote": "q",
    }
    assert r["sources"][1]["category"] == "University" and r["sources"][1]["date"] == "2026-01-02"
    assert r["trace"] == [{"kind": "plan", "label": "Choosing official pages to read", "detail": []}]
    assert set(r) == {
        "claim", "verdict", "headline", "explanation", "sources", "applies_to", "exceptions",
        "clarifying_question", "next_step", "question_for_office", "checked_at", "trace",
    }


def test_rule_status_wins_the_pill(monkeypatch, fake_run):
    monkeypatch.setattr(agent, "run", lambda *a, **k: iter([[_result(rule_status="Proposed only")]]))
    assert backend.check_claim("c", "English", "msu")["verdict"] == "Proposed only"


def test_unknown_school_is_friendly_and_unknown_language_is_english(fake_run):
    with pytest.raises(pipeline.CheckError, match="supported school"):
        backend.check_claim("c", "English", "University of Waterloo")
    backend.check_claim("c2", "Klingon", "University of Chicago")
    assert fake_run[-1] == ("c2", "uchicago", "English")


def test_repeat_check_is_cached_and_returns_a_fresh_copy(fake_run):
    first = backend.check_claim("c", "English", "msu")
    first["sources"].clear()
    second = backend.check_claim("c", "English", "msu")
    assert len(fake_run) == 1 and len(second["sources"]) == 2


def test_stream_yields_steps_then_results(fake_run):
    out = list(backend.stream("c", "English", "msu"))
    assert out[0] == {"step": {"kind": "plan", "label": "Choosing official pages to read", "detail": []}}
    assert list(out[-1]) == ["results"] and out[-1]["results"][0]["claim"] == "c"


def test_stream_fills_the_cache(fake_run):
    list(backend.stream("c", "English", "msu"))
    backend.check_claim("c", "English", "msu")
    assert len(fake_run) == 1


def test_long_first_sentence_headline_is_cut(monkeypatch, fake_run):
    monkeypatch.setattr(agent, "run", lambda *a, **k: iter([[_result(explanation="word " * 60)]]))
    assert len(backend.check_claim("c", "English", "msu")["headline"]) <= 120
