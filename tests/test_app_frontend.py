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


def _starter(at):
    """The first example claim on the home screen."""
    return next(b for b in at.button if b.label.startswith("“"))


def _printed(at):
    return [e.value.strip() for e in list(at.markdown) + list(at.code)]


def test_no_stray_none_is_printed_on_either_screen(app):
    assert "None" not in _printed(app)
    _starter(app).click().run()
    assert not app.exception and "None" not in _printed(app)


def test_answer_comes_before_the_students_own_question(app):
    _starter(app).click().run()
    html = _html(app)
    assert html.index("No: 20 hours during the semester.") < html.index(pipeline_starter())


def pipeline_starter():
    import languages as langs

    return langs.starters("en")[0]


def test_quote_is_shown_before_the_source_details(app):
    _starter(app).click().run()
    html = _html(app)
    assert html.index('class="quote">you may not work') < html.index("Working in the United States")


def test_source_title_is_a_link_to_the_official_page(app):
    _starter(app).click().run()
    assert 'href="https://studyinthestates.dhs.gov/work"' in _html(app)


def test_rerun_on_the_result_screen_does_not_check_again(app, monkeypatch):
    monkeypatch.setattr(speech, "available", lambda: True)
    monkeypatch.setattr(speech, "speak", lambda text, language=None: b"MP3")
    _starter(app).click().run()
    assert len(app.calls) == 1
    _button(app, "Listen").click().run()
    assert not app.exception and len(app.calls) == 1


def test_listen_reads_the_verdict_and_explanation(app, monkeypatch):
    said = []
    monkeypatch.setattr(speech, "available", lambda: True)
    monkeypatch.setattr(speech, "speak", lambda text, language=None: said.append(text) or b"MP3")
    _starter(app).click().run()
    _button(app, "Listen").click().run()
    assert said == ["Contradicted. Federal and MSU rules."]


def test_listen_failure_shows_a_message_and_keeps_the_answer(app, monkeypatch):
    def down(text, language=None):
        raise pipeline.CheckError(speech.FAILED)

    monkeypatch.setattr(speech, "available", lambda: True)
    monkeypatch.setattr(speech, "speak", down)
    _starter(app).click().run()
    _button(app, "Listen").click().run()
    assert not app.exception and any(speech.FAILED in e.value for e in app.error)
    assert "No: 20 hours during the semester." in _html(app)


def test_no_listen_button_without_a_voice_key(app):
    _starter(app).click().run()
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
    _starter(at).click().run()
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
    _starter(at).click().run()
    assert not at.exception and any("usage limit" in e.value for e in at.error)


# ----------------------------------------------- accessibility and feedback
def test_home_has_a_page_heading_and_real_labels(app):
    import languages as langs

    assert "<h1" in _html(app)
    assert app.text_area[0].label == langs.ui_text("en", "paste_label")
    assert {b.label for b in app.selectbox} == {langs.ui_text("en", "language_label"), langs.ui_text("en", "school_label")}


def test_answer_is_a_heading_announced_when_it_arrives(app):
    _starter(app).click().run()
    html = _html(app)
    assert 'role="status"' in html and '<h1 class="answer">No: 20 hours during the semester.' in html


def test_quote_is_marked_as_english_inside_any_language(app):
    _starter(app).click().run()
    assert '<div class="qwrap" lang="en">' in _html(app)


def test_source_link_says_it_opens_a_new_tab(app):
    import languages as langs

    _starter(app).click().run()
    assert langs.ui_text("en", "new_tab") in _html(app)


def test_answer_carries_a_stone_in_the_verdict_color(app):
    assert 'class="stone"' in _html(app)  # the mark on the home screen
    _starter(app).click().run()
    assert 'class="stone contradicted"' in _html(app)


def test_answer_says_when_it_was_checked(monkeypatch, app):
    monkeypatch.setattr(pipeline, "check_claim", lambda *a: _result(checked_at="2026-11-14T23:41:07+00:00"))
    _starter(app).click().run()
    assert "Checked 2026-11-14 23:41 UTC" in _html(app)


def test_checking_nothing_asks_for_a_claim_instead_of_doing_nothing(app):
    import languages as langs

    _button(app, "Check it").click().run()
    assert not app.exception and app.calls == []
    assert any(langs.ui_text("en", "empty_claim") in w.value for w in app.warning)


def test_error_offers_try_again_and_trying_again_checks_again(monkeypatch):
    calls = []

    def flaky(claim, school, context, lang):
        calls.append(claim)
        if len(calls) == 1:
            raise pipeline.CheckError("The checking service has reached its usage limit. Please try again later.")
        return _result()

    monkeypatch.setattr(pipeline, "warm_pages", lambda *a, **k: 0)
    monkeypatch.setattr(pipeline, "check_claim", flaky)
    monkeypatch.setattr(speech, "available", lambda: False)
    monkeypatch.delenv("USE_AGENT", raising=False)
    at = AppTest.from_file(APP, default_timeout=30).run()
    _starter(at).click().run()
    assert any("usage limit" in e.value for e in at.error)
    _button(at, "Try again").click().run()
    assert not at.exception and len(calls) == 2 and "No: 20 hours during the semester." in _html(at)


def test_spoken_question_is_shown_for_correction_before_any_check(monkeypatch):
    import streamlit as st

    import languages as langs

    class Recording:
        def getvalue(self):
            return b"RIFFdata"

    calls = []
    monkeypatch.setattr(pipeline, "warm_pages", lambda *a, **k: 0)
    monkeypatch.setattr(pipeline, "check_claim", lambda *a: calls.append(a) or _result())
    monkeypatch.setattr(speech, "available", lambda: True)
    monkeypatch.setattr(speech, "transcribe", lambda audio, language=None: "Is OPT cancelled")
    monkeypatch.setattr(st, "audio_input", lambda *a, **k: Recording())
    monkeypatch.delenv("USE_AGENT", raising=False)
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert at.text_area[0].value == ""  # nothing is recorded until the microphone is pressed
    at.button(key="mic").click().run()
    assert not at.exception and calls == []
    assert at.text_area[0].value == "Is OPT cancelled"
    assert langs.ui_text("en", "we_heard") in _html(at)
    _button(at, "Check it").click().run()
    assert [c[0] for c in calls] == ["Is OPT cancelled"]


def test_unheard_recording_shows_the_message_and_keeps_the_home_screen(monkeypatch):
    import streamlit as st

    import languages as langs

    class Recording:
        def getvalue(self):
            return b"RIFFdata"

    def unheard(audio, language=None):
        raise pipeline.CheckError(speech.NOT_HEARD)

    monkeypatch.setattr(pipeline, "warm_pages", lambda *a, **k: 0)
    monkeypatch.setattr(speech, "available", lambda: True)
    monkeypatch.setattr(speech, "transcribe", unheard)
    monkeypatch.setattr(st, "audio_input", lambda *a, **k: Recording())
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.button(key="mic").click().run()
    assert not at.exception and [e.value for e in at.error] == [langs.ui_text("en", "not_heard")]
    assert len(at.button) >= 6  # starters and Check it are still there


# ------------------------------------------------------- matches the Figma design
def test_home_leads_with_the_stone_the_question_and_the_tagline(app):
    import html as htmllib

    import languages as langs

    page = _html(app)
    title = htmllib.escape(langs.ui_text("en", "app_title"))
    assert f'<h1 class="title">{title}</h1>' in page and langs.ui_text("en", "tagline") in page
    assert page.index('class="stone"') < page.index(title)


def test_check_button_comes_before_the_examples(app):
    labels = [b.label for b in app.button]
    assert labels.index("Check it") < labels.index(_starter(app).label)


def test_no_microphone_without_a_voice_key(app):
    assert all(b.key != "mic" for b in app.button)


# ------------------------------------------------------------- the voice recorder
def _how(code):
    """The recorder's instructions as they appear in the page."""
    import html as htmllib

    import languages as langs

    return htmllib.escape(langs.ui_text(code, "speak_how"))


def _voice_app(monkeypatch, recording=b"RIFFdata", transcribe=lambda audio, language=None: "Is OPT cancelled"):
    """The app with a voice key. `at.recorder` lists every time the recorder was drawn."""
    import streamlit as st

    class Recording:
        def getvalue(self):
            return recording

    drawn = []
    monkeypatch.setattr(pipeline, "warm_pages", lambda *a, **k: 0)
    monkeypatch.setattr(pipeline, "check_claim", lambda *a: _result())
    monkeypatch.setattr(speech, "available", lambda: True)
    monkeypatch.setattr(speech, "transcribe", transcribe)
    monkeypatch.setattr(st, "audio_input", lambda *a, **k: drawn.append(a) or (Recording() if recording else None))
    monkeypatch.delenv("USE_AGENT", raising=False)
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.recorder = drawn
    return at


def test_open_recorder_says_how_to_use_it_and_where_the_recording_goes(monkeypatch):
    import languages as langs

    at = _voice_app(monkeypatch, recording=None)
    how = _how("en")
    assert "ElevenLabs" in how and how not in _html(at)
    at.button(key="mic").click().run()
    page = _html(at)
    assert how in page and page.index(how) < page.index("Nothing you type is saved")
    assert at.button(key="mic").label == langs.ui_text("en", "speak_close")
    at.button(key="mic").click().run()  # the same button puts the recorder away
    drawn = len(at.recorder)
    at.run()
    assert len(at.recorder) == drawn and at.button(key="mic").label == langs.ui_text("en", "speak_label")


def test_recorder_closes_once_the_transcript_is_in_the_box(monkeypatch):
    import languages as langs

    at = _voice_app(monkeypatch)
    at.button(key="mic").click().run()
    assert at.text_area[0].value == "Is OPT cancelled"
    assert len(at.recorder) == 1 and _how("en") not in _html(at)


def test_spoken_words_are_added_to_what_was_already_typed(monkeypatch):
    at = _voice_app(monkeypatch, recording=None)
    at.text_area[0].set_value("My friend said this:").run()
    monkeypatch.setattr(speech, "transcribe", lambda audio, language=None: "OPT is cancelled")
    import streamlit as st

    class Recording:
        def getvalue(self):
            return b"RIFFdata"

    monkeypatch.setattr(st, "audio_input", lambda *a, **k: Recording())
    at.button(key="mic").click().run()
    assert at.text_area[0].value == "My friend said this: OPT is cancelled"


def test_writing_down_a_recording_does_not_claim_to_read_official_sources(monkeypatch):
    import contextlib

    import streamlit as st

    import languages as langs

    shown = []

    @contextlib.contextmanager
    def spinner(text, **kw):
        shown.append(text)
        yield

    monkeypatch.setattr(st, "spinner", spinner)
    at = _voice_app(monkeypatch)
    at.button(key="mic").click().run()
    assert shown == [langs.ui_text("en", "transcribing")]


def test_unheard_recording_is_explained_in_the_chosen_language(monkeypatch):
    import languages as langs

    def unheard(audio, language=None):
        raise pipeline.CheckError(speech.NOT_HEARD)

    at = _voice_app(monkeypatch, transcribe=unheard)
    at.selectbox[1].set_value("Русский").run()
    at.button(key="mic").click().run()
    assert [e.value for e in at.error] == [langs.ui_text("ru", "not_heard")]
    assert _how("ru") in _html(at)  # the recorder stays open for another try
