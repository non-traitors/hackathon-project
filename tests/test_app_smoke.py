"""Headless smoke tests of app_prototype.py (no network, no API key)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from streamlit.testing.v1 import AppTest

import languages as langs
import pipeline
from pipeline import CheckResult, Source

APP = str(Path(__file__).parent.parent / "app_prototype.py")


@pytest.fixture(autouse=True)
def _no_page_downloads(monkeypatch):
    monkeypatch.setattr(pipeline, "warm_pages", lambda *a, **k: 0)


def _run():
    return AppTest.from_file(APP, default_timeout=30).run()


@pytest.mark.parametrize("code", list(langs.language_choices()))
def test_renders_in_every_language_with_its_own_strings(code):
    at = _run()
    at.selectbox[0].set_value(code).run()
    assert not at.exception
    assert at.title[0].value == langs.ui_text(code, "app_title")
    assert [b.label for b in at.button[:5]] == langs.starters(code)
    beta_shown = any(i.value == langs.ui_text(code, "beta") for i in at.info)
    assert beta_shown == (not langs.is_reviewed(code))


def test_click_through_shows_headline_pills_sources_and_english_office_question(monkeypatch):
    fake = CheckResult(
        verdict="Unclear", headline="لا يمكن تأكيد ذلك من المصادر.", explanation="شرح قصير.",
        rule_status="Not applicable", language="ar", school="Michigan State University",
        sources=[Source(url="https://www.uscis.gov/g-1055", title="Fee schedule", quote="Varies",
                        quote_translation="يختلف", date=None, scope="federal")],
        next_step="اسأل المكتب", question_for_office="What is the current OPT filing fee?",
        claim_in_english="OPT now costs $70,000", checked_at="2026-11-14T00:00:00+00:00",
    )
    seen = {}

    def fake_check(claim, school, context, language):
        seen.update(claim=claim, school=school, language=language)
        return fake

    monkeypatch.setattr(pipeline, "check_claim", fake_check)
    at = _run()
    at.selectbox[0].set_value("ar").run()
    at.text_area[0].set_value("OPT يكلف 70,000 دولار").run()
    at.button[-1].click().run()
    assert not at.exception and seen["language"] == "ar" and seen["school"] == "msu"
    html = " ".join(m.value for m in at.markdown)
    assert "لا يمكن تأكيد ذلك من المصادر." in html
    assert "غير واضح · Unclear" in html            # localized label beside the English one
    assert 'dir="rtl"' in html and "التاريخ غير معروض" in html
    assert any("What is the current OPT filing fee?" in c.value for c in at.code)  # office question stays English


def test_backend_errors_show_a_friendly_message_not_a_traceback(monkeypatch):
    def boom(*a, **k):
        raise pipeline.CheckError("The checking service has reached its usage limit. Please try again later.")

    monkeypatch.setattr(pipeline, "check_claim", boom)
    at = _run()
    at.text_area[0].set_value("anything").run()
    at.button[-1].click().run()
    assert not at.exception
    assert any("usage limit" in e.value for e in at.error)
