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
        question_for_office="",
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


# --- finer routing, fee/rule sources, passage selection, English office question ---
def test_fee_claim_gets_fee_pages_not_the_whole_work_list():
    cfg = pipeline.load_config()
    urls = pipeline.select_seeds("OPT now costs $70,000", "uchicago", cfg)
    assert any(u.endswith("/g-1055") or u.endswith("/i-765") for u in urls)
    assert len(urls) <= pipeline.MAX_DOCS


def test_rule_change_claim_gets_final_rule_pages():
    cfg = pipeline.load_config()
    urls = pipeline.select_seeds("STEM OPT is ending", "msu", cfg)
    assert any("final-rule" in u for u in urls)
    assert any("immigration-updates" in u for u in urls)
    assert any("stem-students-stem-opt" in u for u in urls)


def test_on_campus_claim_stays_small():
    cfg = pipeline.load_config()
    urls = pipeline.select_seeds("F-1 students can work 30 hours per week on campus", "msu", cfg)
    assert len(urls) <= 6, urls


def test_page_cap_still_covers_every_topic_for_unmatched_claims():
    cfg = pipeline.load_config()
    urls = pipeline.select_seeds("something totally unrelated", "uchicago", cfg)
    assert len(urls) == pipeline.MAX_DOCS
    assert any("ssa.gov" in u for u in urls) and any("irs.gov" in u for u in urls)
    assert any("g-1055" in u for u in urls) and any("final-rule" in u for u in urls)


LONG_PAGE = " ".join(
    ["Filler sentence about campus parking and library hours."] * 400
    + ["F-1 students may not work more than 20 hours per week when school is in session."]
    + ["More filler about dining halls and shuttle buses."] * 400
)


def test_passage_selection_keeps_the_answer_bearing_passage():
    view = pipeline.select_passages(LONG_PAGE, "F-1 students can work 30 hours per week on campus", 3000)
    assert "20 hours per week when school is in session" in view
    assert len(view) < len(LONG_PAGE) / 4


def test_short_pages_are_sent_whole():
    assert pipeline.select_passages("Short page.", "anything", 3000) == "Short page."


def test_unmatched_claim_falls_back_to_start_of_page_with_bigger_allowance():
    view = pipeline.select_passages(LONG_PAGE, "claim with no english overlap xyz", 3000)
    assert view.startswith("Filler sentence") and 3000 < len(view) <= 3000 * 2 + 1500


def test_quote_verified_against_full_text_not_the_trimmed_view():
    doc = dict(DOCS[0], text=LONG_PAGE, view="only a trimmed view")
    q = "not work more than 20 hours per week when school is in session"
    out = _out("Contradicted", [_LLMSource(url=doc["url"], quote=q)])
    sources, verdict = validate_output(out, [doc])
    assert len(sources) == 1 and verdict == "Contradicted"


def test_prompt_uses_trimmed_view_when_present():
    doc = dict(DOCS[0], text="FULL TEXT " * 100, view="TRIMMED", scope="federal")
    prompt = pipeline._build_user_prompt("c", {}, "School", [doc], "English")
    assert "TRIMMED" in prompt and "FULL TEXT" not in prompt


def test_question_for_office_is_passed_through_in_english(monkeypatch):
    out = _out("Unclear", [])
    out.question_for_office = "Does the new rule affect my STEM OPT extension?"
    out.next_step = "تواصل مع مكتب الطلاب الدوليين"
    monkeypatch.setattr(pipeline, "retrieve", lambda *a, **k: DOCS)
    monkeypatch.setattr(pipeline, "analyze", lambda *a, **k: out)
    r = check_claim("claim", "msu", {}, "Arabic")
    assert r.question_for_office.startswith("Does the new rule") and r.next_step.startswith("تواصل")


def test_fee_questions_keep_passages_with_dollar_amounts():
    page = " ".join(["Filler about forms and mailing addresses."] * 300
                    + ["The filing fee for Form I-765 is $520 when filed on paper."]
                    + ["More filler about biometrics appointments."] * 300)
    view = pipeline.select_passages(page, "OPT now costs $70,000", 3000, extra={"fee", "filing"}, money=True)
    assert "$520" in view


def test_gemini_client_has_a_request_timeout():
    assert pipeline.REQUEST_TIMEOUT_MS > 0


def test_api_errors_get_actionable_messages():
    class E(Exception):
        def __init__(self, code, msg=""):
            super().__init__(msg)
            self.status_code = code

    assert "usage limit" in pipeline._friendly_api_error(E(402, "credits are depleted"))
    assert "usage limit" in pipeline._friendly_api_error(E(429))
    assert "not set up correctly" in pipeline._friendly_api_error(E(401))
    assert "try again" in pipeline._friendly_api_error(E(500))
    assert "try again" in pipeline._friendly_api_error(ConnectionResetError("reset"))


def test_default_thinking_is_a_valid_level():
    assert pipeline.DEFAULT_THINKING in ("", "minimal", "low", "medium", "high", "xhigh")
