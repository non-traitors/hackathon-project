"""Headless tests of app.py's interface behavior (no network, no API key)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from streamlit.testing.v1 import AppTest

import backend
import pipeline
import speech
import ui_adapter
from pipeline import CheckResult, Source

APP = str(Path(__file__).parent.parent / "app.py")


def _result(**kw):
    base = dict(
        verdict="Contradicted", headline="No: 20 hours during the semester.", explanation="Federal and MSU rules.",
        sources=[Source(url="https://studyinthestates.dhs.gov/work", title="Working in the United States",
                        quote="you may not work more than 20 hours per week", scope="federal")],
        language="en", school="Michigan State University", claim_in_english="x",
    )
    base.update(kw)
    return CheckResult(**base)


@pytest.fixture
def app(monkeypatch):
    """The app with a fake single-pass check. `app.calls` counts backend calls."""
    calls = []

    def fake(claim, school, context, lang):
        calls.append(claim)
        return _result()

    monkeypatch.setattr(pipeline, "warm_pages", lambda *a, **k: 0)
    monkeypatch.setattr(pipeline, "check_claim", fake)
    monkeypatch.delenv("USE_AGENT", raising=False)
    monkeypatch.setattr(speech, "available", lambda: False)
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.calls = calls
    return at


def _html(at):
    return " ".join(m.value for m in at.markdown)


def _button(at, label):
    return next(b for b in at.button if b.label == label)


def _printed(at):
    return [e.value.strip() for e in list(at.markdown) + list(at.code)]


def test_no_stray_none_is_printed_on_either_screen(app):
    assert "None" not in _printed(app)
    app.button[0].click().run()
    assert not app.exception and "None" not in _printed(app)


def test_answer_comes_before_the_students_own_question(app):
    app.button[0].click().run()
    html = _html(app)
    assert html.index("No: 20 hours during the semester.") < html.index(pipeline_starter())


def pipeline_starter():
    import languages as langs

    return langs.starters("en")[0]


def test_quote_is_shown_before_the_source_details(app):
    app.button[0].click().run()
    html = _html(app)
    assert html.index('class="quote">you may not work') < html.index("Working in the United States")


def test_source_title_is_a_link_to_the_official_page(app):
    app.button[0].click().run()
    assert 'href="https://studyinthestates.dhs.gov/work"' in _html(app)


def test_rerun_on_the_result_screen_does_not_check_again(app, monkeypatch):
    monkeypatch.setattr(speech, "available", lambda: True)
    monkeypatch.setattr(speech, "speak", lambda text: b"MP3")
    app.button[0].click().run()
    assert len(app.calls) == 1
    _button(app, "Listen").click().run()
    assert not app.exception and len(app.calls) == 1


def test_listen_reads_the_verdict_and_explanation(app, monkeypatch):
    said = []
    monkeypatch.setattr(speech, "available", lambda: True)
    monkeypatch.setattr(speech, "speak", lambda text: said.append(text) or b"MP3")
    app.button[0].click().run()
    _button(app, "Listen").click().run()
    assert said == ["Contradicted. Federal and MSU rules."]


def test_listen_failure_shows_a_message_and_keeps_the_answer(app, monkeypatch):
    def down(text):
        raise pipeline.CheckError(speech.FAILED)

    monkeypatch.setattr(speech, "available", lambda: True)
    monkeypatch.setattr(speech, "speak", down)
    app.button[0].click().run()
    _button(app, "Listen").click().run()
    assert not app.exception and any(speech.FAILED in e.value for e in app.error)
    assert "No: 20 hours during the semester." in _html(app)


def test_no_listen_button_without_a_voice_key(app):
    app.button[0].click().run()
    assert all(b.label != "Listen" for b in app.button)


def test_agent_mode_shows_steps_and_one_answer_per_claim(monkeypatch):
    def stream(text, language, school):
        yield {"step": {"kind": "split", "label": "Splitting the message into claims", "detail": ["a", "b"]}}
        yield {"step": {"kind": "read", "label": "Reading 2 official pages", "detail": ["Page one", "Page two"]}}
        first = dict(ui_adapter.to_ui(_result(headline="First answer."), "msu"), claim="a", trace=[])
        second = dict(ui_adapter.to_ui(_result(headline="Second answer.", verdict="Unclear", sources=[]), "msu"),
                      claim="b", trace=[])
        yield {"results": [first, second]}

    monkeypatch.setattr(pipeline, "warm_pages", lambda *a, **k: 0)
    monkeypatch.setattr(pipeline, "check_claim", lambda *a, **k: pytest.fail("agent mode must not use the single pass"))
    monkeypatch.setattr(backend, "stream", stream)
    monkeypatch.setattr(speech, "available", lambda: False)
    monkeypatch.setenv("USE_AGENT", "1")
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.button[0].click().run()
    html = _html(at)
    assert not at.exception
    assert "First answer." in html and "Second answer." in html
    assert html.index("First answer.") < html.index("Second answer.")
    assert "Reading 2 official pages" in html


def test_agent_mode_errors_are_friendly(monkeypatch):
    def stream(text, language, school):
        raise pipeline.CheckError("The checking service has reached its usage limit. Please try again later.")
        yield

    monkeypatch.setattr(pipeline, "warm_pages", lambda *a, **k: 0)
    monkeypatch.setattr(backend, "stream", stream)
    monkeypatch.setattr(speech, "available", lambda: False)
    monkeypatch.setenv("USE_AGENT", "1")
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.button[0].click().run()
    assert not at.exception and any("usage limit" in e.value for e in at.error)
