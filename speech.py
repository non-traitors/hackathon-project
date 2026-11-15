"""Read an answer aloud with ElevenLabs text to speech.

    audio = speech.speak(speech.script(result))   # MP3 bytes, e.g. for st.audio(audio, format="audio/mp3")

The default model is multilingual and detects the language from the text, so the
same call works for an English, Arabic, Chinese or Russian explanation. Only the
answer text is sent to ElevenLabs, never the student's own message.
"""
from __future__ import annotations

import os
import re

from pipeline import CheckError

API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}"
DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"  # "Rachel", an ElevenLabs premade voice; override with ELEVENLABS_VOICE_ID
DEFAULT_MODEL = "eleven_multilingual_v2"  # override with ELEVENLABS_MODEL
MAX_CHARS = 1200  # characters read per answer; keeps each request small and cheap
TIMEOUT = 30
CACHE_SIZE = 32
FAILED = "We couldn't read this aloud right now. The written answer is unchanged."

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
    """What to read for one result from backend.check_claim: the verdict, then the explanation."""
    if not result.get("in_scope", True):
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
