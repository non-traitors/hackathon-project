"""Headless tests of the chat thread in app.py (no network, no API key)."""
import html as _h
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from streamlit.testing.v1 import AppTest

import agent
import backend
import chat
import languages as langs
import pipeline
import speech
import ui_adapter

APP = str(Path(__file__).parent.parent / "app.py")
QUOTE = "up to 20 hours per week while school is in session"


def _facts(asked="How many hours can F-1 students work on campus?", statement="You can work up to 20 hours a week."):
    return chat.Reply(
        kind="facts", asked=asked, language="en", school="Michigan State University",
        checked_at="2026-11-15T12:00:00+00:00",
        facts=[chat.Fact(statement=statement, url="https://oiss.isp.msu.edu/employment", title="Employment",
                         quote=QUOTE, scope="school")],
    )


def _notice(text=None, **kw):
    return chat.Reply(kind="notice", asked="x", language="en", school="Michigan State University",
                      text=text or langs.ui_text("en", "chat_no_facts"), **kw)


def _verdict():
    res = agent.AgentResult(verdict="Contradicted", headline="No: 20 hours.", explanation="Federal rule.",
                            language="en", school="Michigan State University", claim="30 hours",
                            sources=[pipeline.Source(url="https://studyinthestates.dhs.gov/work", title="Working",
                                                     quote="you may not work more than 20 hours per week")])
    return chat.Reply(kind="verdict", asked="30 hours", language="en", school="Michigan State University", results=[res])


def _chat_app(monkeypatch, replies, listen=False):
    """The app in chat mode. `replies` are chat.Reply objects (or exceptions), one per turn."""
    seen = []

    def chat_stream(message, history, language, school):
        seen.append((message, list(history)))
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        yield {"step": {"kind": "read", "label": "Reading 2 official pages", "detail": ["Employment"]}}
        yield {"reply": ui_adapter.chat_to_ui(r, "msu"), "history": chat.remember(history, message, r)}

    monkeypatch.setenv("USE_CHAT", "1")
    monkeypatch.setattr(pipeline, "warm_pages", lambda *a, **k: 0)
    monkeypatch.setattr(pipeline, "check_claim", lambda *a, **k: pytest.fail("chat mode must not use the single check"))
    monkeypatch.setattr(backend, "chat_stream", chat_stream)
    monkeypatch.setattr(speech, "available", lambda: listen)
    monkeypatch.setattr(speech, "speak", lambda text, language=None: seen.append(("spoken", text)) or b"MP3")
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.seen = seen
    return at


def _html(at):
    return " ".join(m.value for m in at.markdown)


def _button(at, label):
    return next(b for b in at.button if b.label == label)


def _first(at, text="how many hours can I work?"):
    at.text_area[0].set_value(text)
    return _button(at, "Check it").click().run()


def _follow(at, text):
    at.text_area[0].set_value(text)
    return _button(at, langs.ui_text("en", "send")).click().run()


def test_question_is_answered_with_a_fact_and_its_quote(monkeypatch):
    at = _first(_chat_app(monkeypatch, [_facts()]))
    html = _html(at)
    assert not at.exception
    assert "You can work up to 20 hours a week." in html and QUOTE in html
    assert langs.ui_text("en", "facts_title") in html
    assert "how many hours can I work?" in html
    assert 'href="https://oiss.isp.msu.edu/employment"' in html


def test_follow_up_is_sent_with_the_earlier_turn_and_both_stay_on_screen(monkeypatch):
    stem = _facts(asked="Can STEM OPT be extended?", statement="STEM OPT can be extended by 24 months.")
    at = _first(_chat_app(monkeypatch, [_facts(), stem]))
    assert at.text_area[0].value == ""  # an empty box for the follow-up
    at = _follow(at, "what about STEM?")
    assert not at.exception
    message, history = at.seen[1]
    assert message == "what about STEM?"
    assert history == [{"student": "how many hours can I work?",
                        "asked": "How many hours can F-1 students work on campus?", "answer": QUOTE}]
    html = _html(at)
    assert html.index("You can work up to 20 hours a week.") < html.index("STEM OPT can be extended by 24 months.")
    assert "what about STEM?" in html
    assert at.text_area[0].value == ""


def test_the_question_as_understood_is_shown_when_it_was_rewritten(monkeypatch):
    stem = _facts(asked="Can STEM OPT be extended?", statement="Yes.")
    at = _follow(_first(_chat_app(monkeypatch, [_facts(), stem])), "what about STEM?")
    assert "Can STEM OPT be extended?" in _html(at)


def test_nothing_confirmed_shows_the_fixed_text_and_the_office_question(monkeypatch):
    at = _first(_chat_app(monkeypatch, [_notice(question_for_office="May I work off campus?")]))
    assert _h.escape(langs.ui_text("en", "chat_no_facts")) in _html(at)
    assert any("May I work off campus?" in c.value for c in at.code)


def test_off_topic_shows_the_fixed_refusal(monkeypatch):
    at = _first(_chat_app(monkeypatch, [_notice(langs.ui_text("en", "out_of_scope"), out_of_scope=True)]), "write a poem")
    assert _h.escape(langs.ui_text("en", "out_of_scope")) in _html(at)
    assert not at.exception


def test_rumor_gets_the_verdict_card_inside_the_thread(monkeypatch):
    at = _first(_chat_app(monkeypatch, [_verdict()]), "they said 30 hours")
    html = _html(at)
    assert "No: 20 hours." in html and "you may not work more than 20 hours per week" in html
    assert "Contradicted" in html


def test_start_over_clears_the_thread(monkeypatch):
    at = _first(_chat_app(monkeypatch, [_facts(), _facts(statement="Second chat answer.")]))
    at = _button(at, langs.ui_text("en", "start_over")).click().run()
    assert "You can work up to 20 hours a week." not in _html(at)
    at = _first(at, "another question")
    assert at.seen[-1] == ("another question", [])  # the old turns are forgotten
    assert "You can work up to 20 hours a week." not in _html(at)


def test_a_failed_turn_is_explained_and_can_be_retried(monkeypatch):
    boom = pipeline.CheckError("The checking service has reached its usage limit. Please try again later.")
    at = _first(_chat_app(monkeypatch, [boom, _facts()]))
    assert not at.exception and any("usage limit" in e.value for e in at.error)
    at = _button(at, langs.ui_text("en", "try_again")).click().run()
    assert "You can work up to 20 hours a week." in _html(at)
    assert [m for m, _ in at.seen] == ["how many hours can I work?"] * 2


def test_listen_reads_the_facts_aloud(monkeypatch):
    at = _first(_chat_app(monkeypatch, [_facts()], listen=True))
    _button(at, langs.ui_text("en", "listen")).click().run()
    assert ("spoken", "You can work up to 20 hours a week.") in at.seen


def test_steps_are_shown_while_it_reads(monkeypatch):
    at = _first(_chat_app(monkeypatch, [_facts()]))
    assert not at.exception  # the step list is drawn during the run and replaced by the answer


# ------------------------------------------------------------ backend and adapter
def test_chat_to_ui_has_what_the_thread_draws():
    ui = ui_adapter.chat_to_ui(_facts(), "msu")
    assert ui["kind"] == "facts" and ui["language"] == "en" and ui["rtl"] is False
    fact = ui["facts"][0]
    assert fact["statement"] == "You can work up to 20 hours a week." and fact["quote"] == QUOTE
    assert fact["domain"] == "oiss.isp.msu.edu" and fact["category"] == "Michigan State University"
    assert fact["date"] is None and fact["date_text"] == langs.ui_text("en", "date_unknown")
    assert ui["office"]["url"]
    v = ui_adapter.chat_to_ui(_verdict(), "msu")
    assert v["results"][0]["verdict"] == "Contradicted" and v["results"][0]["claim"] == "30 hours"


def test_backend_chat_stream_yields_steps_then_the_reply_and_the_new_history(monkeypatch):
    def respond(message, history, school_key, language):
        assert school_key == "msu"
        yield agent.Step(kind="plan", label="Choosing official pages to read")
        yield _facts()

    monkeypatch.setattr(chat, "respond", respond)
    out = list(backend.chat_stream("hours?", [], "English", "Michigan State University"))
    assert out[0]["step"]["kind"] == "plan"
    assert out[1]["reply"]["kind"] == "facts"
    assert out[1]["history"] == [{"student": "hours?", "asked": "How many hours can F-1 students work on campus?",
                                  "answer": QUOTE}]
