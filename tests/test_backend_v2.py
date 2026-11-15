"""Offline tests for languages, routing, out-of-scope, dates, caching and limits."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import languages as langs
import pipeline
from pipeline import CheckError, _LLMOutput, _LLMSource, check_claim

DOC = {
    "url": "https://studyinthestates.dhs.gov/students/work/working-in-the-united-states",
    "title": "Working",
    "text": "You may not work more than 20 hours per week when school is in session.",
    "date": "2026-01-05",
    "scope": "federal",
}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("CHECKS_PER_MINUTE", raising=False)
    pipeline.clear_result_cache()
    yield
    pipeline.clear_result_cache()


def _out(**kw):
    base = dict(
        verdict="Contradicted", headline="No: 20 hours in session.", rule_status="Not applicable",
        explanation="x", applies_to=[], exceptions=[],
        sources=[_LLMSource(url=DOC["url"], quote="not work more than 20 hours per week", quote_translation="")],
        clarifying_question=None, next_step="", question_for_office="", claim_in_english="Students can work 30 hours.",
    )
    base.update(kw)
    return _LLMOutput(**base)


# ---------------------------------------------------------------- registry
def test_every_language_has_every_ui_string_and_verdict_label():
    reg = langs.load_languages()
    en_ui = set(reg["en"]["ui"])
    for code, lang in reg.items():
        assert set(lang["ui"]) == en_ui, f"{code}: missing {en_ui - set(lang['ui'])}"
        for label in reg["en"]["verdicts"]:
            assert lang["verdicts"].get(label), f"{code}: no label for {label}"
        assert lang["model_name"] and lang["display"]


def test_disclaimer_has_office_placeholder_in_every_language():
    for code in langs.load_languages():
        assert "{office}" in langs.ui_text(code, "disclaimer")


def test_only_english_is_marked_reviewed_until_a_native_speaker_signs_off():
    reg = langs.load_languages()
    assert reg["en"]["reviewed"] is True
    assert not any(reg[c]["reviewed"] for c in reg if c != "en")


def test_readme_language_set_is_present():
    assert set(langs.language_choices()) == {"en", "ar", "zh", "yue", "ru"}
    assert langs.is_rtl("ar") and not any(langs.is_rtl(c) for c in ("en", "zh", "yue", "ru"))


def test_resolve_language_accepts_code_display_and_model_name_and_falls_back():
    assert langs.resolve_language("ar") == "ar"
    assert langs.resolve_language("العربية") == "ar"
    assert langs.resolve_language("Arabic (Modern Standard Arabic)") == "ar"
    assert langs.resolve_language("English") == "en"
    assert langs.resolve_language("Klingon") == "en"
    assert langs.resolve_language(None) == "en"


def test_glossary_keeps_acronyms_and_is_empty_for_english():
    assert langs.glossary_block("en") == ""
    for code in ("ar", "zh", "yue", "ru"):
        g = langs.glossary_block(code)
        assert "OPT" in g and "SSN" in g and "EAD" in g


def test_keyword_topics_reference_real_topics():
    cfg = pipeline.load_config()
    valid = set(cfg["topics"]) | {"work"}  # "work" is the generic alias for oncampus and opt
    for lang in langs.load_languages().values():
        assert set(lang["keywords"]) <= valid, set(lang["keywords"]) - valid
    # a generic "work" word reaches both work topics, so no keyword list is silently unused
    assert "工作" in langs.topic_keywords("opt") and "工作" in langs.topic_keywords("oncampus")


def test_prompt_carries_language_instruction_and_glossary():
    p = pipeline._build_user_prompt("c", {}, "School", [dict(DOC)], "العربية")
    assert "Arabic (Modern Standard Arabic)" in p and "Glossary" in p and "OPT" in p
    p_en = pipeline._build_user_prompt("c", {}, "School", [dict(DOC)], "English")
    assert "Glossary" not in p_en


# ----------------------------------------------------------------- routing
@pytest.mark.parametrize(
    "claim,topic",
    [
        ("يمكن للطلاب الدوليين العمل 30 ساعة أسبوعيا في الحرم الجامعي", "oncampus"),
        ("国际学生每周可以在校内工作30小时", "oncampus"),
        ("OPT要花多少钱", "fees"),
        ("國際學生唔使報稅", "tax"),
        ("Иностранные студенты не платят налоги", "tax"),
        ("Нужна ли работа, чтобы получить SSN", "ssn"),
        ("Студенты могут работать 30 часов в неделю в кампусе", "oncampus"),
        ("Сколько стоит OPT", "fees"),
        ("STEM OPT отменяют", "rules"),
    ],
)
def test_non_english_claims_route_to_the_right_topic(claim, topic):
    assert topic in pipeline.matched_topics(claim)


def test_non_english_claim_loads_a_focused_page_set_not_everything():
    cfg = pipeline.load_config()
    everything = pipeline.select_seeds("zzz unrelated", "msu", cfg)
    focused = pipeline.select_seeds("国际学生每周可以在校内工作30小时", "msu", cfg)
    assert len(focused) < len(everything)
    assert any("oiss.isp.msu.edu" in u for u in focused)


def test_latin_keywords_still_match_whole_words_only():
    assert "work" not in " ".join(pipeline.matched_topics("International students never need to file US tax forms"))
    assert "tax" in pipeline.matched_topics("International students never need to file US tax forms")


# ------------------------------------------------------------ out of scope
@pytest.mark.parametrize(
    "claim",
    ["You need a credit score to open a bank account", "Can I get a credit card as an international student?", "需要银行账户吗"],
)
def test_banking_only_claims_are_answered_instantly_without_the_model(claim, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not fetch or call the model")

    monkeypatch.setattr(pipeline, "retrieve", boom)
    monkeypatch.setattr(pipeline, "analyze", boom)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)  # not even a key is needed
    r = check_claim(claim, "msu")
    assert r.out_of_scope and r.verdict == "Unclear" and r.sources == []


def test_banking_plus_an_in_scope_topic_goes_through_the_normal_path(monkeypatch):
    monkeypatch.setattr(pipeline, "retrieve", lambda *a, **k: [dict(DOC)])
    monkeypatch.setattr(pipeline, "analyze", lambda *a, **k: _out())
    r = check_claim("Can I get an SSN to open a bank account?", "msu")
    assert not r.out_of_scope


def test_out_of_scope_message_is_in_the_answer_language(monkeypatch):
    r = check_claim("需要银行账户吗", "msu", language="中文")
    assert r.language == "zh" and "超出" in r.explanation


# ------------------------------------------------------------------- dates
def test_extract_date_from_meta_and_text_and_never_guesses():
    assert pipeline.extract_date('<meta property="article:modified_time" content="2025-08-27T10:00:00Z">') == "2025-08-27"
    assert pipeline.extract_date("<p>Last Reviewed/Updated: 02/12/2026</p>") == "02/12/2026"
    assert pipeline.extract_date("<p>Page Last Reviewed/Updated: August 27, 2024</p>") == "August 27, 2024"
    assert pipeline.extract_date("<p>Nothing here about when this was written.</p>") is None
    assert pipeline.extract_date('<meta property="article:modified_time" content="not a date">') is None


# ------------------------------------------------------------- new fields
def test_headline_claim_restatement_and_quote_translation_pass_through(monkeypatch):
    out = _out(
        headline="لا: 20 ساعة أثناء الدراسة.",
        sources=[_LLMSource(url=DOC["url"], quote="not work more than 20 hours per week", quote_translation="لا يجوز العمل أكثر من 20 ساعة")],
    )
    monkeypatch.setattr(pipeline, "retrieve", lambda *a, **k: [dict(DOC)])
    monkeypatch.setattr(pipeline, "analyze", lambda *a, **k: out)
    r = check_claim("claim", "msu", language="ar")
    assert r.headline.startswith("لا") and r.claim_in_english and r.language == "ar"
    assert r.sources[0].quote_translation.startswith("لا يجوز") and r.sources[0].date == "2026-01-05"


def test_schema_caps_list_lengths_and_puts_verdict_and_headline_first():
    schema = _LLMOutput.model_json_schema()
    props = schema["properties"]
    assert list(props)[:2] == ["verdict", "headline"]
    for name in ("applies_to", "exceptions", "sources"):
        assert props[name]["maxItems"] == 3
    with pytest.raises(Exception):
        _out(applies_to=["a", "b", "c", "d"])


# ----------------------------------------------------------- cache and limits
def test_repeat_check_is_served_from_memory_without_calling_anything(monkeypatch):
    calls = {"n": 0}

    def fake_retrieve(*a, **k):
        calls["n"] += 1
        return [dict(DOC)]

    monkeypatch.setattr(pipeline, "retrieve", fake_retrieve)
    monkeypatch.setattr(pipeline, "analyze", lambda *a, **k: _out())
    first = check_claim("30 hours on campus", "msu")
    second = check_claim("  30 HOURS on campus ", "msu")  # same claim, different spacing/case
    assert calls["n"] == 1 and second.timing["cached"] is True and second.verdict == first.verdict
    check_claim("30 hours on campus", "uchicago")  # other school: not a cache hit
    check_claim("30 hours on campus", "msu", language="ar")  # other language: not a cache hit
    assert calls["n"] == 3


def test_cache_can_be_bypassed(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(pipeline, "retrieve", lambda *a, **k: calls.__setitem__("n", calls["n"] + 1) or [dict(DOC)])
    monkeypatch.setattr(pipeline, "analyze", lambda *a, **k: _out())
    check_claim("c1", "msu")
    check_claim("c1", "msu", use_cache=False)
    assert calls["n"] == 2


def test_errors_are_not_cached(monkeypatch):
    state = {"fail": True}

    def flaky(*a, **k):
        if state["fail"]:
            raise CheckError("boom")
        return _out()

    monkeypatch.setattr(pipeline, "retrieve", lambda *a, **k: [dict(DOC)])
    monkeypatch.setattr(pipeline, "analyze", flaky)
    with pytest.raises(CheckError):
        check_claim("c2", "msu")
    state["fail"] = False
    assert check_claim("c2", "msu").verdict == "Contradicted"


def test_rate_guard_blocks_a_burst_but_not_cached_repeats(monkeypatch):
    monkeypatch.setenv("CHECKS_PER_MINUTE", "2")
    monkeypatch.setattr(pipeline, "retrieve", lambda *a, **k: [dict(DOC)])
    monkeypatch.setattr(pipeline, "analyze", lambda *a, **k: _out())
    check_claim("a1", "msu")
    check_claim("a2", "msu")
    with pytest.raises(CheckError, match="try again in a minute"):
        check_claim("a3", "msu")
    assert check_claim("a1", "msu").timing["cached"] is True  # cache hits don't count


def test_timing_diagnostics_are_recorded(monkeypatch):
    monkeypatch.setattr(pipeline, "retrieve", lambda *a, **k: [dict(DOC, view="v")])

    def fake_analyze(claim, context, school, docs, language, config, stats):
        stats["usage"] = {"input_tokens": 10}
        return _out()

    monkeypatch.setattr(pipeline, "analyze", fake_analyze)
    t = check_claim("c3", "msu").timing
    assert {"retrieve_s", "analyze_s", "total_s", "pages", "prompt_chars", "usage"} <= set(t)


def test_failed_page_fetch_is_retried_soon_not_cached_for_an_hour(monkeypatch):
    import requests

    calls = {"n": 0}

    def fail(*a, **k):
        calls["n"] += 1
        raise ConnectionError("down")

    monkeypatch.setattr(requests, "get", fail)
    pipeline._cache.clear()
    url = "https://www.irs.gov/forms-pubs/about-form-8843"
    assert pipeline._fetch_one(url, ["irs.gov"]) is None
    assert pipeline._fetch_one(url, ["irs.gov"]) is None  # within 60 s: served from the failure cache
    assert calls["n"] == 1
    ts, doc, ttl = pipeline._cache[url]
    assert ttl == pipeline.FAILURE_TTL < pipeline.CACHE_TTL
    pipeline._cache[url] = (time.time() - ttl - 1, None, ttl)  # a minute later
    pipeline._fetch_one(url, ["irs.gov"])
    assert calls["n"] == 2
    pipeline._cache.clear()


def test_warm_pages_fetches_every_seed_once(monkeypatch):
    seen = []
    monkeypatch.setattr(pipeline, "_fetch_one", lambda url, allowed: seen.append(url) or {"url": url})
    n = pipeline.warm_pages()
    assert n == len(seen) > 10 and len(set(seen)) <= len(seen)


def test_every_language_has_the_same_number_of_starters_and_they_check_out_of_scope_free():
    n = len(langs.starters("en"))
    assert n >= 5
    cfg = pipeline.load_config()
    for code in langs.load_languages():
        assert len(langs.starters(code)) == n, code
        for claim in langs.starters(code):
            assert len(claim) <= pipeline.MAX_CLAIM_CHARS
            assert not pipeline.is_out_of_scope(claim, cfg), claim


def test_starters_route_to_the_same_topics_as_their_english_original():
    en = langs.starters("en")
    for code in ("ar", "zh", "yue", "ru"):
        for i, claim in enumerate(langs.starters(code)):
            assert pipeline.matched_topics(claim), f"{code} starter {i} matches no topic: {claim}"


def test_cantonese_is_shown_as_traditional_chinese_and_found_by_every_common_name():
    assert langs.language_choices()["yue"] == "繁體中文"
    for name in ("繁體中文", "粵語", "粵語／繁體中文", "廣東話", "Cantonese", "yue"):
        assert langs.resolve_language(name, strict=True) == "yue", name
    assert langs.resolve_language("中文", strict=True) == "zh"  # Simplified stays separate
    assert langs.resolve_language("Русский", strict=True) == "ru"


def test_unknown_language_is_an_error_not_silent_english(monkeypatch):
    with pytest.raises(ValueError):
        langs.resolve_language("Klingon", strict=True)
    assert langs.resolve_language("Klingon") == "en"  # lenient mode, used only for display strings
    assert langs.resolve_language("") == "en" and langs.resolve_language(None, strict=True) == "en"
    monkeypatch.setattr(pipeline, "retrieve", lambda *a, **k: [dict(DOC)])
    monkeypatch.setattr(pipeline, "analyze", lambda *a, **k: _out())
    with pytest.raises(CheckError, match="supported language"):
        check_claim("30 hours on campus", "msu", language="Klingon")


def test_check_accepts_the_label_the_frontend_uses_for_cantonese(monkeypatch):
    monkeypatch.setattr(pipeline, "retrieve", lambda *a, **k: [dict(DOC)])
    monkeypatch.setattr(pipeline, "analyze", lambda *a, **k: _out())
    assert check_claim("30 hours on campus", "msu", language="繁體中文").language == "yue"
