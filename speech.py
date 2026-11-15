"""Voice in and voice out with ElevenLabs.

    text = speech.transcribe(recording.getvalue())   # the student's spoken question, as text
    audio = speech.speak(speech.script(result))      # MP3 bytes, e.g. for st.audio(audio, format="audio/mp3")

Both models detect the language themselves, so the same calls work for English,
Arabic, Chinese, Russian or Uzbek. A transcript is plain text: it goes through the
agent's scope gate and quote check like anything typed.

What leaves the machine: the answer text (for speak) and, only when the student
chooses to speak, their recording (for transcribe).
"""
from __future__ import annotations

import os
import re

from pipeline import CheckError

API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}"
STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
DEFAULT_VOICE = "EXAVITQu4vr4xnSDxMaL"  # "Sarah", an ElevenLabs premade voice; override with ELEVENLABS_VOICE_ID
DEFAULT_MODEL = "eleven_v3"  # 70+ languages incl. Uzbek and Cantonese; override with ELEVENLABS_MODEL
STT_MODEL = "scribe_v3"
MAX_AUDIO_BYTES = 10_000_000  # about a minute or two of speech is far below this
MAX_CHARS = 1200  # characters read per answer; keeps each request small and cheap
TIMEOUT = 30
CACHE_SIZE = 32
FAILED = "We couldn't read this aloud right now. The written answer is unchanged."
NOT_HEARD = "We couldn't make out the recording. Please try again, or type your question."

_cache: dict[tuple[str, str, str], bytes] = {}


def clear_cache() -> None:
    _cache.clear()


def available() -> bool:
    """True when a key is configured, so the interface can hide the Listen button otherwise."""
    return bool(os.environ.get("ELEVENLABS_API_KEY"))


def _trim(text: str) -> str:
    """Collapse whitespace and cut to MAX_CHARS, at the end of a sentence when there is one."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= MAX_CHARS:
        return text
    cut = text[:MAX_CHARS]
    ends = [m.end() for m in re.finditer(r"[.!?。！？؟]", cut)]
    return cut[: ends[-1]] if ends else cut


def script(result: dict) -> str:
    """What to read for one result dict from ui_adapter.to_ui: the verdict, then the explanation."""
    if result.get("out_of_scope"):
        return result["explanation"]
    return f"{result['verdict']}. {result['explanation']}"


def speak(text: str) -> bytes:
    """Return MP3 audio of `text`. Raises CheckError with a message safe to show the student."""
    text = _trim(text or "")
    if not text:
        raise CheckError("There is nothing to read aloud.")
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise CheckError("Read-aloud is not configured (missing ELEVENLABS_API_KEY).")
    voice = os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE
    model = os.environ.get("ELEVENLABS_MODEL") or DEFAULT_MODEL
    cache_key = (text, voice, model)
    if cache_key in _cache:
        return _cache[cache_key]
    try:
        import requests

        r = requests.post(
            API_URL.format(voice=voice),
            headers={"xi-api-key": key, "accept": "audio/mpeg"},
            json={"text": text, "model_id": model},
            timeout=TIMEOUT,
        )
    except Exception as e:  # network
        raise CheckError(FAILED) from e
    if r.status_code != 200 or not r.content:  # bad key, quota, unknown voice, empty body
        raise CheckError(FAILED)
    if len(_cache) >= CACHE_SIZE:
        _cache.pop(next(iter(_cache)))
    _cache[cache_key] = r.content
    return r.content


def transcribe(audio: bytes, filename: str = "question.wav") -> str:
    """Return the text of a spoken question. Raises CheckError with a student-safe message."""
    if not audio:
        raise CheckError(NOT_HEARD)
    if len(audio) > MAX_AUDIO_BYTES:
        raise CheckError("That recording is too long. Please record a shorter question.")
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise CheckError("Voice input is not configured (missing ELEVENLABS_API_KEY).")
    try:
        import requests

        r = requests.post(
            STT_URL,
            headers={"xi-api-key": key},
            files={"file": (filename, audio)},
            data={"model_id": STT_MODEL},
            timeout=TIMEOUT,
        )
        text = r.json().get("text", "").strip() if r.status_code == 200 else ""
    except Exception as e:  # network, or a reply that is not the expected JSON
        raise CheckError(NOT_HEARD) from e
    if not text:
        raise CheckError(NOT_HEARD)
    return text
