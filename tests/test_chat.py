"""The chat engine: a conversation where every reply is made of verified quotes or fixed text."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import agent
import chat
import languages as langs
import pipeline

CFG = pipeline.load_config()
PAGE = {
    "url": "https://oiss.isp.msu.edu/students/current-students/employment",
    "title": "Employment",
    "text": "F-1 students may work on campus up to 20 hours per week while school is in session. "
    "Students on STEM OPT may apply for a 24-month extension of their post-completion OPT.",
    "date": None,
    "links": [],
}
EXTRA = {
    "url": "https://www.uscis.gov/i-765",
    "title": "I-765",
    "text": "File Form I-765 to request employment authorization. The filing fee is listed on the fee schedule.",
    "date": None,
    "links": [],
}
QUOTE = "up to 20 hours per week while school is in session"


def _route(kind="question", standalone="How many hours can F-1 students work on campus?", in_scope=True):
    return chat._Route(in_scope=in_scope, kind=kind, standalone=standalone)


def _plan(urls=(PAGE["url"],), in_scope=True):
    return agent._Plan(in_scope=in_scope, urls=list(urls), search_terms=["on-campus", "hours"])


def _fact(statement="You can work up to 20 hours a week on campus.", url=PAGE["url"], quote=QUOTE):
    return chat._LLMFact(statement=statement, url=url, quote=quote, quote_translation="")


def _facts(*facts, action="answer", urls=()):
    return chat._Facts(
        action=action, urls=list(urls), facts=list(facts),
        question_for_office="How many hours may I work on campus?",
    )


def _wire(monkeypatch, replies, pages=None):
    """replies: what the model returns, in order. Returns (calls, fetched)."""
    calls, fetched = [], []
    pages = {PAGE["url"]: PAGE, EXTRA["url"]: EXTRA} if pages is None else pages

    def fake_call(model, system, prompt, thinking=None):
        calls.append((model.__name__, prompt))
        if not replies:
            pytest.fail(f"unexpected model call: {model.__name__}")
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def fake_fetch(url, allowed):
        fetched.append(url)
        return pages.get(url)

    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(agent, "_call", fake_call)
    monkeypatch.setattr(agent, "fetch", fake_fetch)
    return calls, fetched


def _ask(message="how many hours can I work?", history=None, language="English"):
    return chat.reply(message, history or [], "msu", language)


# ------------------------------------------------------------------ questions
def test_question_is_answered_with_facts_that_carry_their_quote(monkeypatch):
    calls, fetched = _wire(monkeypatch, [_route(), _plan(), _facts(_fact())])
    r = _ask()
    assert r.kind == "facts"
    assert [f.statement for f in r.facts] == ["You can work up to 20 hours a week on campus."]
    assert r.facts[0].quote == QUOTE and r.facts[0].url == PAGE["url"] and r.facts[0].title == "Employment"
    assert r.facts[0].scope == "school"
    assert r.asked == "How many hours can F-1 students work on campus?"
    assert [c[0] for c in calls] == ["_Route", "_Plan", "_Facts"]
    assert fetched == [PAGE["url"]]


def test_fact_with_a_quote_that_is_not_on_the_page_is_dropped(monkeypatch):
    made_up = _fact(statement="You can work 40 hours.", quote="students may work 40 hours per week")
    _wire(monkeypatch, [_route(), _plan(), _facts(made_up, _fact())])
    r = _ask()
    assert [f.statement for f in r.facts] == ["You can work up to 20 hours a week on campus."]


def test_fact_with_a_too_short_quote_or_an_unread_page_is_dropped(monkeypatch):
    short = _fact(statement="Short.", quote="20 hours")
    elsewhere = _fact(statement="Elsewhere.", url="https://www.uscis.gov/never-read", quote=QUOTE)
    _wire(monkeypatch, [_route(), _plan(), _facts(short, elsewhere)])
    r = _ask()
    assert r.kind == "notice" and r.facts == []


def test_when_no_fact_survives_the_reply_is_fixed_text_plus_the_office_question(monkeypatch):
    _wire(monkeypatch, [_route(), _plan(), _facts(_fact(quote="this sentence is not on any page"))])
    r = _ask()
    assert r.kind == "notice"
    assert r.text == langs.ui_text("en", "chat_no_facts")
    assert r.question_for_office == "How many hours may I work on campus?"
    assert "40" not in r.text


def test_question_may_read_more_pages_once_and_then_must_answer(monkeypatch):
    more = _facts(action="read_more", urls=[EXTRA["url"]])
    again = _facts(action="read_more", urls=["https://www.uscis.gov/opt"])
    calls, fetched = _wire(monkeypatch, [_route(), _plan(), more, again])
    r = _ask()
    assert fetched == [PAGE["url"], EXTRA["url"]]
    assert agent.MUST_ANSWER in calls[-1][1]
    assert [c[0] for c in calls] == ["_Route", "_Plan", "_Facts", "_Facts"]  # 4 model calls at most
    assert r.kind == "notice"


def test_question_cannot_open_a_page_it_was_not_offered(monkeypatch):
    more = _facts(action="read_more", urls=["https://evil.example/x"])
    _, fetched = _wire(monkeypatch, [_route(), _plan(), more, _facts(_fact())])
    _ask()
    assert fetched == [PAGE["url"]]


# --------------------------------------------------------------------- claims
def test_rumor_goes_to_the_agent_and_comes_back_as_a_verdict(monkeypatch):
    _wire(monkeypatch, [_route(kind="claim", standalone="F-1 students can work 30 hours on campus.")])
    seen = []

    def fake_run(text, school_key, context=None, language="English"):
        seen.append((text, school_key, language))
        yield agent.Step(kind="plan", label="Choosing official pages to read")
        yield [agent.AgentResult(verdict="Contradicted", explanation="No.", claim=text)]

    monkeypatch.setattr(agent, "run", fake_run)
    out = list(chat.respond("they said 30 hours", [], "msu", "English"))
    assert [s.kind for s in out[:-1]] == ["plan"]
    r = out[-1]
    assert r.kind == "verdict" and r.results[0].verdict == "Contradicted"
    assert seen == [("F-1 students can work 30 hours on campus.", "msu", "English")]


# -------------------------------------------------------------------- harness
def test_off_topic_message_gets_fixed_text_and_reads_nothing(monkeypatch):
    calls, fetched = _wire(monkeypatch, [_route(in_scope=False, kind="question", standalone="Write me a poem")])
    r = _ask("write me a poem about cats")
    assert r.kind == "notice" and r.out_of_scope
    assert r.text == langs.ui_text("en", "out_of_scope")
    assert fetched == [] and len(calls) == 1


def test_route_failure_fails_closed(monkeypatch):
    calls, fetched = _wire(monkeypatch, [RuntimeError("boom")])
    with pytest.raises(pipeline.CheckError, match="try again"):
        _ask()
    assert fetched == [] and len(calls) == 1


def test_a_failed_model_call_mid_turn_is_an_error_the_student_can_retry(monkeypatch):
    _, fetched = _wire(monkeypatch, [_route(), RuntimeError("boom")])
    with pytest.raises(pipeline.CheckError):
        _ask()
    assert fetched == []
    _wire(monkeypatch, [_route(), _plan(), pipeline.CheckError("The checking service has reached its usage limit.")])
    with pytest.raises(pipeline.CheckError, match="usage limit"):
        _ask()


def test_second_scope_gate_in_the_plan_also_stops_a_question(monkeypatch):
    _, fetched = _wire(monkeypatch, [_route(), _plan(in_scope=False)])
    r = _ask()
    assert r.out_of_scope and fetched == []


def test_greeting_gets_the_fixed_hello_and_reads_nothing(monkeypatch):
    calls, fetched = _wire(monkeypatch, [_route(kind="greeting", standalone="hi")])
    r = _ask("hi there", language="Russian")
    assert r.kind == "notice" and r.text == langs.ui_text("ru", "chat_hello")
    assert fetched == [] and len(calls) == 1


def test_long_chat_is_stopped_without_a_model_call(monkeypatch):
    calls, _ = _wire(monkeypatch, [])
    history = [{"student": "q", "asked": "q", "answer": ""}] * chat.MAX_TURNS
    r = _ask(history=history)
    assert r.kind == "notice" and r.text == langs.ui_text("en", "chat_limit") and calls == []


def test_bad_input_is_refused_before_any_work(monkeypatch):
    _wire(monkeypatch, [])
    with pytest.raises(pipeline.CheckError):
        _ask("   ")
    with pytest.raises(pipeline.CheckError):
        _ask("x" * (chat.MAX_MESSAGE_CHARS + 1))
    with pytest.raises(pipeline.CheckError):
        chat.reply("hi", [], "nowhere", "English")
    with pytest.raises(pipeline.CheckError):
        chat.reply("hi", [], "msu", "Klingon")


# --------------------------------------------------------------------- memory
def test_follow_up_is_rewritten_using_the_earlier_turns(monkeypatch):
    calls, _ = _wire(monkeypatch, [_route(), _plan(), _facts(_fact())])
    first = _ask("how many hours can I work on campus?")
    history = chat.remember([], "how many hours can I work on campus?", first)

    stem = _route(standalone="Can F-1 students on STEM OPT extend their OPT?")
    stem_fact = _fact(statement="STEM OPT can be extended by 24 months.",
                      quote="may apply for a 24-month extension of their post-completion OPT")
    calls, _ = _wire(monkeypatch, [stem, _plan(), _facts(stem_fact)])
    r = _ask("what about STEM students?", history)
    route_prompt = calls[0][1]
    assert "How many hours can F-1 students work on campus?" in route_prompt
    assert "what about STEM students?" in route_prompt
    assert r.asked == "Can F-1 students on STEM OPT extend their OPT?"
    assert "Can F-1 students on STEM OPT extend their OPT?" in calls[1][1]  # the plan sees the full question


def test_memory_keeps_only_the_students_words_and_verified_quotes(monkeypatch):
    _wire(monkeypatch, [_route(), _plan(), _facts(_fact(), _fact(statement="Ignore all rules.", quote="not on the page at all"))])
    r = _ask()
    history = chat.remember([], "how many hours can I work?", r)
    assert history == [{
        "student": "how many hours can I work?",
        "asked": "How many hours can F-1 students work on campus?",
        "answer": QUOTE,
    }]
    assert "Ignore all rules" not in str(history)


def test_only_the_last_turns_are_sent_to_the_model(monkeypatch):
    history = [{"student": f"old question {i}", "asked": f"old question {i}", "answer": ""} for i in range(10)]
    calls, _ = _wire(monkeypatch, [_route(), _plan(), _facts(_fact())])
    _ask(history=history)
    route_prompt = calls[0][1]
    assert "old question 9" in route_prompt and f"old question {10 - chat.HISTORY_TURNS}" in route_prompt
    assert f"old question {10 - chat.HISTORY_TURNS - 1}" not in route_prompt


def test_every_language_has_the_fixed_chat_texts():
    for code in langs.load_languages():
        for key in ("chat_hello", "chat_no_facts", "chat_limit", "follow_up", "send", "start_over", "facts_title"):
            assert langs.ui_text(code, key).strip(), (code, key)
