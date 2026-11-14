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


@pytest.fixture(autouse=True)
def _fake_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")  # never used: analyze() is mocked


def test_empty_and_long_claims_rejected():
    with pytest.raises(CheckError):
        check_claim("   ", "msu")
    with pytest.raises(CheckError):
        check_claim("x" * 10_000, "msu")


def test_unsupported_school_rejected():
    with pytest.raises(CheckError):
        check_claim("F-1 students can work", "waterloo")


def test_missing_key_gives_friendly_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(CheckError, match="GEMINI_API_KEY"):
        check_claim("F-1 students can work", "msu")


def test_rule_status_dropped_without_verified_citation(monkeypatch):
    out = _out("Supported", [_LLMSource(url="https://example.com/fake", quote="x")])
    out.rule_status = "Blocked"
    monkeypatch.setattr(pipeline, "retrieve", lambda *a, **k: DOCS)
    monkeypatch.setattr(pipeline, "analyze", lambda *a, **k: out)
    r = check_claim("OPT is cancelled", "msu")
    assert r.rule_status == "Not applicable" and r.verdict == "Unclear"


def test_rule_status_kept_with_verified_citation(monkeypatch):
    out = _out("Contradicted", [_LLMSource(url=DOCS[0]["url"], quote="up to 20 hours per week")])
    out.rule_status = "In effect"
    monkeypatch.setattr(pipeline, "retrieve", lambda *a, **k: DOCS)
    monkeypatch.setattr(pipeline, "analyze", lambda *a, **k: out)
    r = check_claim("30 hours", "msu")
    assert r.rule_status == "In effect"


def test_no_readable_sources_is_unclear_not_error(monkeypatch):
    monkeypatch.setattr(pipeline, "retrieve", lambda *a, **k: [])
    r = check_claim("some claim", "uchicago")
    assert r.verdict == "Unclear" and r.sources == [] and r.school == "University of Chicago"


# --- curated sources and retrieval (offline) ---
def test_seed_hosts_are_allowlisted():
    cfg = pipeline.load_config()
    for key, school in cfg["schools"].items():
        allowed = cfg["federal"] + school["domains"]
        seeds = [u for topic in cfg["seeds"]["federal"].values() for u in topic]
        seeds += [u for topic in school.get("seeds", {}).values() for u in topic]
        bad = [u for u in seeds if not _host_allowed(u, allowed)]
        assert not bad, f"{key}: seeds off the allowlist: {bad}"


def test_school_seed_lists_stay_within_the_model_page_limit():
    cfg = pipeline.load_config()
    for key in cfg["schools"]:
        assert len(pipeline.select_seeds("tax work ssn", key, cfg)) <= pipeline.MAX_DOCS


def test_select_seeds_routes_by_topic_and_keeps_school_scoped():
    cfg = pipeline.load_config()
    msu = pipeline.select_seeds("Every student can get an SSN without a job", "msu", cfg)
    assert any("ssa.gov" in u for u in msu)
    uc = pipeline.select_seeds("International students never need to file tax forms", "uchicago", cfg)
    assert any("irs.gov" in u for u in uc) and not any("msu.edu" in u for u in uc)
    work_uc = pipeline.select_seeds("OPT now costs $70,000", "uchicago", cfg)
    assert any("internationalaffairs.uchicago.edu" in u for u in work_uc)
    assert not any("oiss.isp.msu.edu" in u for u in work_uc)


def test_unmatched_claim_uses_every_topic():
    cfg = pipeline.load_config()
    urls = pipeline.select_seeds("something totally unrelated", "msu", cfg)
    assert any("irs.gov" in u for u in urls) and any("ssa.gov" in u for u in urls)


def test_html_to_text_drops_scripts_and_nav():
    title, text = pipeline.html_to_text(
        "<html><head><title>Work</title><script>evil()</script></head>"
        "<body><nav>Menu</nav><p>Up to 20 hours   per week.</p></body></html>"
    )
    assert title == "Work" and text == "Up to 20 hours per week." and "evil" not in text


def test_retrieve_skips_unreadable_pages_and_labels_scope(monkeypatch):
    def fake_fetch(url, allowed):
        if "ssa.gov" in url:
            return None  # e.g. blocked or 404
        return {"url": url, "title": "t", "text": "x", "date": None}

    monkeypatch.setattr(pipeline, "_fetch_one", fake_fetch)
    docs = pipeline.retrieve("OPT and SSN", "msu")
    assert docs and not any("ssa.gov" in d["url"] for d in docs)
    scopes = {d["scope"] for d in docs}
    assert scopes == {"school", "federal"}


def test_quote_must_come_from_fetched_text_not_model_memory():
    out = _out("Supported", [_LLMSource(url=DOCS[0]["url"], quote="up to 20 hours per week")])
    sources, verdict = validate_output(out, [dict(DOCS[0], text="Totally different page text.")])
    assert sources == [] and verdict == "Unclear"


def test_topic_keywords_match_whole_words_only():
    cfg = pipeline.load_config()
    urls = pipeline.select_seeds("International students never need to file US tax forms", "msu", cfg)
    # "intern" must not match "international": only tax pages (plus MSU's tax page)
    assert all("irs.gov" in u or "oiss.isp.msu.edu/resources/taxes" in u for u in urls)
    assert any("irs.gov" in u for u in urls)
