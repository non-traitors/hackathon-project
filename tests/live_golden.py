"""Live golden checks against the real official pages and the Gemini API.

Not collected by default (the filename is not test_*.py) and skipped without a
key. Run:  .venv313/bin/python -m pytest tests/live_golden.py -s

Acceptable verdicts were fixed by reading the official pages, not by asking the
model. Each claim below is FALSE or unverifiable as worded, so "Supported" is
never acceptable for any of them.
"""
import os
import sys
import time
from pathlib import Path

import pytest
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

import pipeline  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
    reason="needs GEMINI_API_KEY",
)

# (claim, school, language, acceptable verdicts)
GOLDEN = [
    ("F-1 students can work 30 hours per week on campus.", "msu", "English", {"Contradicted"}),
    ("F-1 students can work 30 hours per week on campus.", "uchicago", "English", {"Contradicted"}),
    ("Every international student can get an SSN without a job.", "uchicago", "English", {"Contradicted"}),
    ("International students never need to file US tax forms.", "msu", "English", {"Contradicted"}),
    ("OPT now costs $70,000", "uchicago", "English", {"Contradicted", "Unclear"}),
    ("STEM OPT is ending", "msu", "English", {"Contradicted", "Unclear"}),
    ("يمكن للطلاب الدوليين العمل 30 ساعة أسبوعيا في الحرم الجامعي", "msu", "Arabic", {"Contradicted", "Unclear"}),
]


@pytest.mark.parametrize("claim,school,language,acceptable", GOLDEN)
def test_golden_claim(claim, school, language, acceptable):
    t = time.time()
    r = pipeline.check_claim(claim, school, {}, language)
    secs = time.time() - t
    print(f"\n[{school}/{language}] {claim[:50]} -> {r.verdict} ({secs:.1f}s, {len(r.sources)} sources)")
    assert r.verdict in acceptable, f"{r.verdict}: {r.explanation}"
    assert r.verdict == "Unclear" or r.sources, "a confident verdict needs a verified citation"
    cfg = pipeline.load_config()
    allowed = cfg["federal"] + cfg["schools"][school]["domains"]
    assert all(pipeline._host_allowed(s.url, allowed) for s in r.sources)
    if r.question_for_office:  # must be English even when the answer is not
        ascii_share = sum(c.isascii() for c in r.question_for_office) / len(r.question_for_office)
        assert ascii_share > 0.9, r.question_for_office


def test_fee_claim_cites_a_fee_page_when_it_is_answerable():
    r = pipeline.check_claim("OPT now costs $70,000", "uchicago", {}, "English")
    cited = [s.url for s in r.sources]
    print("\nfee claim cites:", cited)
    assert r.verdict != "Supported"
    if r.verdict == "Contradicted":
        assert any("uscis.gov" in u for u in cited)


# ---------------------------------------------------------------- agent (agent.py)
import agent  # noqa: E402


@pytest.mark.parametrize("claim,school,language,acceptable", GOLDEN)
def test_golden_claim_agent(claim, school, language, acceptable):
    t = time.time()
    r = agent.check(claim, school, {}, language)[0]
    secs = time.time() - t
    kinds = ">".join(s.kind for s in r.trace)
    print(f"\n[agent {school}/{language}] {claim[:50]} -> {r.verdict} ({secs:.1f}s, {len(r.sources)} sources, {kinds})")
    assert r.verdict in acceptable, f"{r.verdict}: {r.explanation}"
    assert r.verdict == "Unclear" or r.sources, "a confident verdict needs a verified citation"
    cfg = pipeline.load_config()
    allowed = cfg["federal"] + cfg["schools"][school]["domains"]
    assert all(pipeline._host_allowed(s.url, allowed) for s in r.sources)
    assert secs < 2 * agent.TIME_BUDGET, f"too slow: {secs:.1f}s"


def test_agent_splits_a_pasted_message():
    results = agent.check("guys\nOPT now costs $70,000\nand we can work 30 hours on campus now", "msu", {}, "English")
    print("\npasted message ->", [(r.claim, r.verdict) for r in results])
    assert len(results) == 2
    assert all(r.verdict != "Supported" for r in results)
