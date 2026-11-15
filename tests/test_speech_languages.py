"""ElevenLabs language settings: 繁體中文 must be Cantonese (yue), never Mandarin."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from streamlit.testing.v1 import AppTest

import languages as langs
import pipeline
import speech
import ui_adapter
from pipeline import CheckResult, Source

APP = str(Path(__file__).parent.parent / "app.py")

# What ElevenLabs' own language lists say (checked 2026-11-14):
#   Scribe (speech to text): English eng, Arabic ara, Mandarin zho, Cantonese yue, Russian rus
#   Eleven v3 (text to speech): en, ar, zh, ru, and Cantonese yue (no two-letter code exists)
EXPECTED = {
    "en": {"stt": "eng", "tts": "en"},
    "ar": {"stt": "ara", "tts": "ar"},
    "zh": {"stt": "zho", "tts": "zh"},
    "yue": {"stt": "yue", "tts": "yue"},
    "ru": {"stt": "rus", "tts": "ru"},
}


class _Resp:
    def __init__(self, status=200, content=b"MP3", data=None):
        self.status_code, self.content, self._data = status, content, data

    def json(self):
        if self._data is None:
            raise ValueError("not json")
        return self._data


@pytest.fixture
def posts(monkeypatch):
    """Record requests.post calls; replies come from .replies (a list, last one repeats)."""
    sent = []

    class Box:
        replies = [_Resp()]

    def fake_post(url, headers=None, json=None, timeout=None, files=None, data=None):
        sent.append({"url": url, "json": json, "data": data})
        i = min(len(sent) - 1, len(Box.replies) - 1)
        if isinstance(Box.replies[i], Exception):
            raise Box.replies[i]
        return Box.replies[i]

    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    monkeypatch.delenv("ELEVENLABS_MODEL", raising=False)
    monkeypatch.setattr("requests.post", fake_post)
    speech.clear_cache()
    Box.sent = sent
    Box.replies = [_Resp()]
    return Box


# ------------------------------------------------------------------ registry
def test_registry_codes_match_elevenlabs_language_lists():
    for code, want in EXPECTED.items():
        assert langs.speech_code(code, "stt") == want["stt"], code
        assert langs.speech_code(code, "tts") == want["tts"], code


@pytest.mark.parametrize("name", ["繁體中文", "粵語", "廣東話", "Cantonese", "yue"])
def test_traditional_chinese_is_always_cantonese_never_mandarin(name):
    assert langs.speech_code(name, "stt") == "yue" and langs.speech_code(name, "tts") == "yue"
    assert langs.speech_code(name, "stt") not in ("zho", "cmn", "zh")


def test_mandarin_stays_mandarin():
    assert langs.speech_code("中文", "stt") == "zho" and langs.speech_code("中文", "tts") == "zh"


def test_unknown_language_gets_no_code_so_elevenlabs_auto_detects():
    assert langs.speech_code("Klingon", "stt") is None and langs.speech_code("Klingon", "tts") is None


def test_every_registry_language_has_both_codes():
    for code in langs.load_languages():
        assert langs.speech_code(code, "stt") and langs.speech_code(code, "tts"), code


# --------------------------------------------------------------- text to speech
@pytest.mark.parametrize("label,want", [("繁體中文", "yue"), ("中文", "zh"), ("العربية", "ar"), ("Русский", "ru"), ("English", "en")])
def test_speak_sends_the_language_code(posts, label, want):
    speech.speak("some answer text", language=label)
    sent = posts.sent[0]["json"]
    assert sent["language_code"] == want and sent["model_id"] == "eleven_v3"


def test_speak_without_a_language_sends_no_code(posts):
    speech.speak("some answer text")
    assert "language_code" not in posts.sent[0]["json"]


def test_cantonese_audio_is_not_served_from_a_mandarin_cache_entry(posts):
    speech.speak("same text", language="中文")
    speech.speak("same text", language="繁體中文")
    assert [c["json"]["language_code"] for c in posts.sent] == ["zh", "yue"]
    speech.speak("same text", language="繁體中文")  # now cached
    assert len(posts.sent) == 2


@pytest.mark.parametrize("first", [_Resp(400, content=b""), _Resp(200, content=b""), OSError("down")])
def test_speak_retries_once_without_the_code_if_elevenlabs_refuses_it(posts, first):
    posts.replies = [first, _Resp(content=b"AUDIO")]
    assert speech.speak("text", language="繁體中文") == b"AUDIO"
    assert "language_code" in posts.sent[0]["json"] and "language_code" not in posts.sent[1]["json"]


def test_speak_still_fails_politely_when_both_attempts_fail(posts):
    posts.replies = [_Resp(500, content=b"")]
    with pytest.raises(pipeline.CheckError, match="read this aloud"):
        speech.speak("text", language="繁體中文")
    assert len(posts.sent) == 2


# --------------------------------------------------------------- speech to text
@pytest.mark.parametrize("label,want", [("繁體中文", "yue"), ("中文", "zho"), ("العربية", "ara"), ("Русский", "rus"), ("English", "eng")])
def test_transcribe_sends_the_expected_language(posts, label, want):
    posts.replies = [_Resp(data={"text": "hello"})]
    speech.transcribe(b"RIFFdata", language=label)
    assert posts.sent[0]["data"] == {"model_id": speech.STT_MODEL, "language_code": want}


def test_transcribe_without_a_language_auto_detects(posts):
    posts.replies = [_Resp(data={"text": "hello"})]
    speech.transcribe(b"RIFFdata")
    assert posts.sent[0]["data"] == {"model_id": speech.STT_MODEL}


@pytest.mark.parametrize("first", [_Resp(400, data={}), _Resp(200, data={"text": "  "}), OSError("down")])
def test_transcribe_retries_with_auto_detect_if_the_expected_language_fails(posts, first):
    posts.replies = [first, _Resp(data={"text": "你好"})]
    assert speech.transcribe(b"RIFFdata", language="繁體中文") == "你好"
    assert posts.sent[0]["data"]["language_code"] == "yue" and "language_code" not in posts.sent[1]["data"]


def test_transcribe_gives_up_politely_after_both_attempts(posts):
    posts.replies = [_Resp(200, data={"text": ""})]
    with pytest.raises(pipeline.CheckError, match="type your question"):
        speech.transcribe(b"RIFFdata", language="繁體中文")
    assert len(posts.sent) == 2


# ----------------------------------------------------------- what gets read out
def test_script_reads_the_verdict_word_in_the_answer_language():
    assert speech.script({"verdict": "Contradicted", "verdict_text": "與官方資料不符", "explanation": "最多20小時。"}) == "與官方資料不符. 最多20小時。"
    assert speech.script({"verdict": "Contradicted", "explanation": "No."}) == "Contradicted. No."  # older dicts still work


def test_adapter_provides_the_localized_verdict_word():
    r = CheckResult(verdict="Contradicted", explanation="x", language="yue", school="MSU",
                    sources=[Source(url="https://www.uscis.gov/x", title="t", quote="q", scope="federal")])
    assert ui_adapter.to_ui(r, "msu")["verdict_text"] == "與官方資料不符"
    r.language = "en"
    assert ui_adapter.to_ui(r, "msu")["verdict_text"] == "Contradicted"


# ------------------------------------------------------------ through the app
def _result(language):
    return CheckResult(
        verdict="Contradicted", headline="h", explanation="e", language=language, school="Michigan State University",
        sources=[Source(url="https://studyinthestates.dhs.gov/work", title="Working", quote="you may not work more than 20 hours", scope="federal")],
    )


def _open_app(monkeypatch, picker_label):
    monkeypatch.setattr(pipeline, "warm_pages", lambda *a, **k: 0)
    monkeypatch.setattr(pipeline, "check_claim", lambda claim, school, ctx, lang: _result(langs.resolve_language(lang)))
    monkeypatch.setattr(speech, "available", lambda: True)
    monkeypatch.delenv("USE_AGENT", raising=False)
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.selectbox[1].set_value(picker_label).run()
    return at


@pytest.mark.parametrize("label,want", [("繁體中文", "yue"), ("中文", "zh"), ("Русский", "ru"), ("English", "en")])
def test_listen_button_reads_the_answer_in_the_answer_language(monkeypatch, label, want):
    heard = {}
    monkeypatch.setattr(speech, "speak", lambda text, language=None: heard.update(text=text, language=language) or b"MP3")
    at = _open_app(monkeypatch, label)
    next(b for b in at.button if b.label.startswith("“")).click().run()
    next(b for b in at.button if b.label == langs.ui_text(langs.resolve_language(label), "listen")).click().run()
    assert not at.exception
    assert langs.resolve_language(heard["language"]) == langs.resolve_language(label)
    assert heard["text"].startswith(langs.verdict_label(langs.resolve_language(label), "Contradicted"))


@pytest.mark.parametrize("label,hint", [("繁體中文", "yue"), ("العربية", "ar"), ("Русский", "ru"), ("English", None)])
def test_microphone_expects_the_picked_language_except_english(monkeypatch, label, hint):
    import streamlit as st

    class Recording:
        def getvalue(self):
            return b"RIFFdata"

    mic = {"recording": None}  # nothing recorded until the language has been picked, as in real use
    got = {}
    monkeypatch.setattr(speech, "transcribe", lambda audio, language=None: got.update(language=language) or "question")
    monkeypatch.setattr(st, "audio_input", lambda *a, **k: mic["recording"])
    at = _open_app(monkeypatch, label)
    assert "language" not in got
    mic["recording"] = Recording()
    at.button(key="mic").click().run()  # the recorder opens only when the student asks for it
    assert not at.exception and got["language"] == hint
