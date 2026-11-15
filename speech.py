"""Voice in and voice out with ElevenLabs.

    text = speech.transcribe(recording.getvalue())   # the student's spoken question, as text
    audio = speech.speak(speech.script(result))      # MP3 bytes, e.g. for st.audio(audio, format="audio/mp3")

Both models can detect the language themselves, but Cantonese and Mandarin are both
"Chinese" to a detector, so callers should pass `language` (a registry code or a picker
name such as 繁體中文). The registry maps it to ElevenLabs' own codes (languages.yaml):
Cantonese is `yue`, Mandarin is `zho` / `zh`. If ElevenLabs rejects a code, the call is
repeated once without it, which is the old auto-detect behavior. A transcript is plain
text: it goes through the agent's scope gate and quote check like anything typed.

What leaves the machine: the answer text (for speak) and, only when the student
chooses to speak, their recording (for transcribe).
"""
from __future__ import annotations

import os
import re
from typing import Optional

import languages as langs
from pipeline import CheckError

API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice}"
STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
DEFAULT_VOICE = "EXAVITQu4vr4xnSDxMaL"  # "Sarah", an ElevenLabs premade voice; override with ELEVENLABS_VOICE_ID
DEFAULT_MODEL = "eleven_v3"  # covers Cantonese, which eleven_multilingual_v2 does not; override with ELEVENLABS_MODEL
STT_MODEL = "scribe_v3"
MAX_AUDIO_BYTES = 10_000_000  # about a minute or two of speech is far below this
MAX_CHARS = 1200  # characters read per answer; keeps each request small and cheap
TIMEOUT = 30
CACHE_SIZE = 32
FAILED = "We couldn't read this aloud right now. The written answer is unchanged."
NOT_HEARD = "We couldn't make out the recording. Please try again, or type your question."

_cache: dict[tuple, bytes] = {}


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
    # The verdict word is read in the answer language when the adapter provides it.
    verdict = result.get("verdict_text") or result["verdict"]
    return f"{verdict}. {result['explanation']}"


def speak(text: str, language: Optional[str] = None) -> bytes:
    """Return MP3 audio of `text`. Raises CheckError with a message safe to show the student.

    `language` is the language the text is written in; it is sent to ElevenLabs as
    `language_code` (Cantonese is `yue`) so the text is read in that language.
    """
    text = _trim(text or "")
    if not text:
        raise CheckError("There is nothing to read aloud.")
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise CheckError("Read-aloud is not configured (missing ELEVENLABS_API_KEY).")
    voice = os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE
    model = os.environ.get("ELEVENLABS_MODEL") or DEFAULT_MODEL
    lang = langs.speech_code(language, "tts") if language else None
    cache_key = (text, voice, model, lang)
    if cache_key in _cache:
        return _cache[cache_key]
    audio = None
    # With a language code first; if that fails for any reason, once more without it.
    for code in ([lang, None] if lang else [None]):
        body = {"text": text, "model_id": model}
        if code:
            body["language_code"] = code
        try:
            import requests

            r = requests.post(
                API_URL.format(voice=voice),
                headers={"xi-api-key": key, "accept": "audio/mpeg"},
                json=body,
                timeout=TIMEOUT,
            )
        except Exception:  # network
            continue
        if r.status_code == 200 and r.content:  # else: bad key, quota, unknown voice, empty body
            audio = r.content
            break
    if audio is None:
        raise CheckError(FAILED)
    if len(_cache) >= CACHE_SIZE:
        _cache.pop(next(iter(_cache)))
    _cache[cache_key] = audio
    return audio


def transcribe(audio: bytes, filename: str = "question.wav", language: Optional[str] = None) -> str:
    """Return the text of a spoken question. Raises CheckError with a student-safe message.

    `language` is the language the student is expected to speak. It is sent as
    `language_code` (Cantonese is `yue`) so Cantonese is not heard as Mandarin. Without
    it, ElevenLabs detects the language.
    """
    if not audio:
        raise CheckError(NOT_HEARD)
    if len(audio) > MAX_AUDIO_BYTES:
        raise CheckError("That recording is too long. Please record a shorter question.")
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise CheckError("Voice input is not configured (missing ELEVENLABS_API_KEY).")
    lang = langs.speech_code(language, "stt") if language else None
    # With the expected language first; if that fails or hears nothing, once more
    # with auto-detect (the student may have spoken a different language).
    for code in ([lang, None] if lang else [None]):
        data = {"model_id": STT_MODEL}
        if code:
            data["language_code"] = code
        try:
            import requests

            r = requests.post(STT_URL, headers={"xi-api-key": key}, files={"file": (filename, audio)}, data=data, timeout=TIMEOUT)
            text = r.json().get("text", "").strip() if r.status_code == 200 else ""
        except Exception:  # network, or a reply that is not the expected JSON
            text = ""
        if text:
            return text
    raise CheckError(NOT_HEARD)
