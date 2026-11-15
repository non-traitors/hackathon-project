"""Headless tests of app.py wired to the backend (no network, no API key)."""
import html as htmllib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from streamlit.testing.v1 import AppTest

import languages as langs
import pipeline
import ui_adapter
from pipeline import CheckResult, Source

APP = str(Path(__file__).parent.parent / "app.py")
FRONTEND_LABELS = ["English", "العربية", "中文", "繁體中文", "Русский"]  # as shown in the picker


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr(pipeline, "warm_pages", lambda *a, **k: 0)


def _source(**kw):
    base = dict(url="https://oiss.isp.msu.edu/students/current-students/employment", title="MSU employment",
                quote="Maximum 20 hours per week", scope="school", date=None)
    base.update(kw)
    return Source(**base)


def _result(**kw):
    base = dict(verdict="Contradicted", headline="No: 20 hours during the semester.", explanation="Federal and MSU rules.",
                sources=[_source()], language="en", school="Michigan State University", claim_in_english="x")
    base.update(kw)
    return CheckResult(**base)


def _open(monkeypatch, result=None, seen=None, language=None):
    def fake(claim, school, context, lang):
        if seen is not None:
            seen.update(claim=claim, school=school, language=lang)
        if isinstance(result, Exception):
            raise result
        return result or _result()

    monkeypatch.setattr(pipeline, "check_claim", fake)
    at = AppTest.from_file(APP, default_timeout=30).run()
    if language:
        _language(at).set_value(language).run()
    return at


def _html(at):
    return " ".join(m.value for m in at.markdown)


def _language(at):
    return next(b for b in at.selectbox if "English" in b.options)


def _school(at):
    return next(b for b in at.selectbox if "English" not in b.options)


def _starters(at):
    """The example claims: the buttons whose label is a quoted claim."""
    return [b for b in at.button if b.label.startswith("“")]


def esc(text):
    """The app HTML-escapes text (apostrophes become &#x27;), so compare against that."""
    return htmllib.escape(text)


def _check_first_starter(at):
    _starters(at)[0].click().run()
    return at


def test_language_picker_lists_exactly_the_five_languages_in_the_frontends_wording():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert _language(at).options == FRONTEND_LABELS == list(langs.language_choices().values())


@pytest.mark.parametrize("label", FRONTEND_LABELS)
def test_home_renders_in_each_language_with_its_own_text_and_starters(label):
    at = AppTest.from_file(APP, default_timeout=30).run()
    _language(at).set_value(label).run()
    code = langs.resolve_language(label, strict=True)
    assert not at.exception
    html = _html(at)
    assert esc(langs.ui_text(code, "app_title")) in html and langs.ui_text(code, "starters_label") in html
    assert [b.label.strip("“”") for b in _starters(at)] == langs.starters(code)
    assert (langs.ui_text(code, "beta") in html) == (not langs.is_reviewed(code))


def test_backend_receives_school_key_and_the_label_the_user_picked(monkeypatch):
    seen = {}
    at = _open(monkeypatch, seen=seen, language="繁體中文")
    _check_first_starter(at)
    assert not at.exception
    assert seen["school"] == "msu" and seen["language"] == "繁體中文"
    assert seen["claim"] == langs.starters("yue")[0]


def test_other_school_is_passed_as_its_key(monkeypatch):
    seen = {}
    at = _open(monkeypatch, seen=seen)
    _school(at).set_value("University of Chicago").run()
    _check_first_starter(at)
    assert seen["school"] == "uchicago"


def test_contradicted_answer_gets_its_own_pill_not_a_grey_unclear_one(monkeypatch):
    at = _check_first_starter(_open(monkeypatch))
    html = _html(at)
    assert "No: 20 hours during the semester." in html
    assert "#FBE4E2" in html and ">Contradicted<" in html   # red Contradicted pill
    assert ">Unclear<" in html                                # appears only in the legend
    assert langs.ui_text("en", "legend_title") in html


def test_source_without_a_date_does_not_crash_and_says_so(monkeypatch):
    at = _check_first_starter(_open(monkeypatch, _result(sources=[_source(date=None)])))
    assert not at.exception
    assert "Date not shown" in _html(at)


def test_source_with_a_date_is_labelled_last_updated(monkeypatch):
    at = _check_first_starter(_open(monkeypatch, _result(sources=[_source(date="2026-01-05")])))
    assert "Last updated: 2026-01-05" in _html(at)


def test_quote_stays_english_and_translation_follows(monkeypatch):
    r = _result(language="ar", sources=[_source(quote_translation="الحد الأقصى 20 ساعة")])
    at = _check_first_starter(_open(monkeypatch, r, language="العربية"))
    html = _html(at)
    assert 'class="quote">Maximum 20 hours per week' in html and 'class="tr">الحد الأقصى 20 ساعة' in html


def test_arabic_is_right_to_left_on_both_screens(monkeypatch):
    at = _open(monkeypatch, _result(language="ar"), language="العربية")
    assert "direction:rtl" in _html(at)
    assert "direction:rtl" in _html(_check_first_starter(at))


def test_english_is_not_right_to_left(monkeypatch):
    assert "direction:rtl" not in _html(_check_first_starter(_open(monkeypatch)))


def test_claim_restatement_shown_only_for_non_english(monkeypatch):
    r = _result(language="zh", claim_in_english="Students can work 30 hours.")
    html = _html(_check_first_starter(_open(monkeypatch, r, language="中文")))
    assert langs.ui_text("zh", "we_checked") in html and "Students can work 30 hours." in html
    assert langs.ui_text("en", "we_checked") not in _html(_check_first_starter(_open(monkeypatch, _result(claim_in_english="Students can work 30 hours."))))


def test_unclear_answer_offers_the_office_and_the_english_question(monkeypatch):
    r = _result(verdict="Unclear", sources=[], question_for_office="What is the current OPT filing fee?",
                next_step="Ask the office.", headline="We can't confirm this.")
    at = _check_first_starter(_open(monkeypatch, r))
    html = _html(at)
    assert esc(langs.ui_text("en", "unclear_title")) in html and "Ask the office." in html
    assert any("What is the current OPT filing fee?" in c.value for c in at.code)
    assert esc(langs.ui_text("en", "legend_title")) not in html  # the legend only shows for firm answers


def test_out_of_scope_answer_has_no_sources_or_unclear_box(monkeypatch):
    msg = langs.ui_text("en", "out_of_scope")
    r = _result(verdict="Unclear", sources=[], out_of_scope=True, headline=msg, explanation=msg)
    html = _html(_check_first_starter(_open(monkeypatch, r)))
    assert esc(msg) in html and esc(langs.ui_text("en", "unclear_title")) not in html and 'class="card"' not in html


def test_rule_status_adds_a_second_pill_and_the_rule_legend(monkeypatch):
    html = _html(_check_first_starter(_open(monkeypatch, _result(rule_status="In effect"))))
    assert ">In effect<" in html and langs.ui_text("en", "legend_note") in html


def test_no_rule_status_means_no_rule_legend(monkeypatch):
    html = _html(_check_first_starter(_open(monkeypatch, _result(rule_status="Not applicable"))))
    assert langs.ui_text("en", "legend_note") not in html and ">Proposed only<" not in html


def test_backend_errors_become_a_friendly_message_not_a_traceback(monkeypatch):
    err = pipeline.CheckError("The checking service has reached its usage limit. Please try again later.")
    at = _check_first_starter(_open(monkeypatch, err))
    assert not at.exception
    assert any("usage limit" in e.value for e in at.error)


def test_disclaimer_names_the_chosen_schools_office_from_sources_yaml(monkeypatch):
    html = _html(_check_first_starter(_open(monkeypatch)))
    office = pipeline.load_config()["schools"]["msu"]["office"]
    assert f"Not legal advice. Confirm with {office}." in html


def test_app_does_not_hardcode_school_offices_or_verdict_text():
    src = Path(APP).read_text()
    assert "OISS" not in src and "internationalaffairs" not in src
    assert "mock_check" not in src and "Yes, eligible students can apply" not in src


def test_legend_helper_returns_three_verdicts_and_three_rule_statuses():
    leg = ui_adapter.legend("ar")
    assert [p["label"] for p in leg["verdicts"]] == ["Supported", "Contradicted", "Unclear"]
    assert [p["label"] for p in leg["rule_statuses"]] == ["In effect", "Proposed only", "Blocked"]
    assert leg["verdicts"][1]["text"] == "يتعارض مع المصادر · Contradicted"
