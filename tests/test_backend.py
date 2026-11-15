import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import agent
import backend
import pipeline
import ui_adapter


def _result(**kw):
    base = dict(
        verdict="Contradicted",
        headline="No, the limit is 20 hours.",
        explanation="No. The limit is 20 hours. Breaks differ.",
        claim="c",
        school="Michigan State University",
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


def test_check_claim_returns_the_shared_ui_shape_plus_claim_and_trace(fake_run):
    r = backend.check_claim("c", "English", "Michigan State University")
    assert fake_run == [("c", "msu", "English")]
    expected = ui_adapter.to_ui(_result(), "msu")
    assert {k: r[k] for k in expected} == expected
    assert set(r) - set(expected) == {"claim", "trace"}
    assert r["claim"] == "c"
    assert r["trace"] == [{"kind": "plan", "label": "Choosing official pages to read", "detail": []}]
    assert r["pills"][0]["label"] == "Contradicted" and r["headline"] == "No, the limit is 20 hours."


def test_school_key_is_accepted_and_unknown_school_is_friendly(fake_run):
    backend.check_claim("c", "English", "uchicago")
    assert fake_run[-1][1] == "uchicago"
    with pytest.raises(pipeline.CheckError, match="supported school"):
        backend.check_claim("c2", "English", "University of Waterloo")


def test_out_of_scope_result_is_flagged(monkeypatch, fake_run):
    off = _result(verdict="Unclear", out_of_scope=True, sources=[])
    monkeypatch.setattr(agent, "run", lambda *a, **k: iter([[off]]))
    assert backend.check_claim("write me a script", "English", "msu")["out_of_scope"] is True


def test_repeat_check_is_cached_and_returns_a_fresh_copy(fake_run):
    first = backend.check_claim("c", "English", "msu")
    first["sources"].clear()
    second = backend.check_claim("c", "English", "msu")
    assert len(fake_run) == 1 and len(second["sources"]) == 2


def test_answers_without_sources_are_not_cached(monkeypatch, fake_run):
    """An Unclear from a network blip, or a misjudged out-of-scope, must not stick."""
    runs = []

    def run(*a, **k):
        runs.append(1)
        yield [_result(verdict="Unclear", sources=[])]

    monkeypatch.setattr(agent, "run", run)
    backend.check_claim("c", "English", "msu")
    backend.check_claim("c", "English", "msu")
    assert len(runs) == 2


def test_cache_is_bounded(fake_run):
    for i in range(backend.CACHE_SIZE + 5):
        backend.check_claim(f"claim {i}", "English", "msu")
    assert len(backend._cache) == backend.CACHE_SIZE


def test_stream_yields_steps_then_results_and_fills_the_cache(fake_run):
    out = list(backend.stream("c", "English", "msu"))
    assert out[0] == {"step": {"kind": "plan", "label": "Choosing official pages to read", "detail": []}}
    assert list(out[-1]) == ["results"] and out[-1]["results"][0]["claim"] == "c"
    backend.check_claim("c", "English", "msu")
    assert len(fake_run) == 1


def test_pasted_message_gives_one_dict_per_claim(monkeypatch, fake_run):
    monkeypatch.setattr(agent, "run", lambda *a, **k: iter([[_result(claim="a"), _result(claim="b")]]))
    assert [r["claim"] for r in backend.check_all("a\nb", "English", "msu")] == ["a", "b"]
