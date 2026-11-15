import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import speech
from pipeline import CheckError


class _Resp:
    def __init__(self, status=200, content=b"MP3", data=None):
        self.status_code, self.content, self._data = status, content, data

    def json(self):
        if self._data is None:
            raise ValueError("not json")
        return self._data


@pytest.fixture
def posts(monkeypatch):
    """Record calls to requests.post; reply 200 with fake audio unless a test replaces .reply."""
    sent = []

    class Box:
        reply = _Resp()

    def fake_post(url, headers=None, json=None, timeout=None, files=None, data=None):
        sent.append({"url": url, "headers": headers, "json": json, "timeout": timeout, "files": files, "data": data})
        if isinstance(Box.reply, Exception):
            raise Box.reply
        return Box.reply

    monkeypatch.setenv("ELEVENLABS_API_KEY", "k")
    monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)
    monkeypatch.delenv("ELEVENLABS_MODEL", raising=False)
    monkeypatch.setattr("requests.post", fake_post)
    speech.clear_cache()
    Box.reply = _Resp()
    Box.sent = sent
    return Box


def test_speak_sends_text_to_elevenlabs_and_returns_audio(posts):
    assert speech.speak("No. The limit is 20 hours.") == b"MP3"
    call = posts.sent[0]
    assert call["url"] == f"https://api.elevenlabs.io/v1/text-to-speech/{speech.DEFAULT_VOICE}"
    assert call["headers"]["xi-api-key"] == "k"
    assert call["json"] == {"text": "No. The limit is 20 hours.", "model_id": speech.DEFAULT_MODEL}
    assert call["timeout"] == speech.TIMEOUT


def test_voice_and_model_can_be_overridden(posts, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_VOICE_ID", "v1")
    monkeypatch.setenv("ELEVENLABS_MODEL", "m1")
    speech.speak("hello")
    assert posts.sent[0]["url"].endswith("/v1") and posts.sent[0]["json"]["model_id"] == "m1"


def test_same_text_is_only_paid_for_once(posts):
    speech.speak("hello")
    speech.speak("hello")
    assert len(posts.sent) == 1


def test_long_text_is_cut_at_a_sentence_end(posts):
    text = "This is a sentence. " * 200
    speech.speak(text)
    said = posts.sent[0]["json"]["text"]
    assert len(said) <= speech.MAX_CHARS and said.endswith("sentence.")


def test_missing_key_is_a_friendly_error_and_sends_nothing(posts, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    assert speech.available() is False
    with pytest.raises(CheckError, match="ELEVENLABS_API_KEY"):
        speech.speak("hello")
    assert posts.sent == []


def test_empty_text_is_rejected(posts):
    with pytest.raises(CheckError):
        speech.speak("   ")
    assert posts.sent == []


@pytest.mark.parametrize("reply", [_Resp(401, b"{}"), _Resp(429, b"{}"), _Resp(200, b""), OSError("down")])
def test_failures_are_friendly_and_not_cached(posts, reply):
    posts.reply = reply
    with pytest.raises(CheckError, match="read this aloud"):
        speech.speak("hello")
    posts.reply = _Resp()
    assert speech.speak("hello") == b"MP3"


def test_script_reads_the_verdict_then_the_explanation():
    r = {"in_scope": True, "verdict": "Contradicted", "explanation": "No. The limit is 20 hours."}
    assert speech.script(r) == "Contradicted. No. The limit is 20 hours."


def test_script_for_out_of_scope_is_just_the_reply():
    r = {"in_scope": False, "verdict": "Out of scope", "explanation": "This checker only covers student questions."}
    assert speech.script(r) == "This checker only covers student questions."


# ------------------------------------------------------------- speech to text
def test_defaults_cover_the_languages_the_app_offers():
    """eleven_v3 is the text-to-speech model that includes Uzbek and Cantonese."""
    assert speech.DEFAULT_MODEL == "eleven_v3" and speech.STT_MODEL == "scribe_v3"


def test_transcribe_uploads_the_recording_and_returns_its_text(posts):
    posts.reply = _Resp(data={"text": "  Is OPT cancelled?  ", "language_code": "en"})
    assert speech.transcribe(b"RIFFdata", "question.wav") == "Is OPT cancelled?"
    call = posts.sent[0]
    assert call["url"] == "https://api.elevenlabs.io/v1/speech-to-text"
    assert call["headers"]["xi-api-key"] == "k" and call["data"] == {"model_id": speech.STT_MODEL}
    assert call["files"]["file"][0] == "question.wav" and call["files"]["file"][1] == b"RIFFdata"


def test_transcribe_rejects_empty_and_oversized_audio_without_sending(posts):
    with pytest.raises(CheckError):
        speech.transcribe(b"")
    with pytest.raises(CheckError, match="shorter"):
        speech.transcribe(b"x" * (speech.MAX_AUDIO_BYTES + 1))
    assert posts.sent == []


def test_transcribe_without_a_key_is_a_friendly_error(posts, monkeypatch):
    monkeypatch.delenv("ELEVENLABS_API_KEY")
    with pytest.raises(CheckError, match="ELEVENLABS_API_KEY"):
        speech.transcribe(b"RIFFdata")
    assert posts.sent == []


@pytest.mark.parametrize(
    "reply", [_Resp(401, data={}), _Resp(200), _Resp(200, data={"text": "   "}), _Resp(200, data=["x"]), OSError("down")]
)
def test_transcribe_failures_ask_the_student_to_retry_or_type(posts, reply):
    posts.reply = reply
    with pytest.raises(CheckError, match="type your question"):
        speech.transcribe(b"RIFFdata")
