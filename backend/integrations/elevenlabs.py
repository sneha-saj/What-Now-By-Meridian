"""ElevenLabs: voice typing (speech to text) and "Listen" (text to speech), called with plain HTTP.

- Voice typing: the browser records a short clip, the backend sends it to POST /v1/speech-to-text (model
  `scribe_v3`) and returns the `text`. The clip is not stored by us. ElevenLabs' zero-retention mode is
  enterprise-only, so the app tells people their recording goes to ElevenLabs.
- Listen: POST /v1/text-to-speech/{voice_id} (model `eleven_flash_v2_5`, multilingual and fast). The MP3 for a
  given text is cached on disk for 7 days, so the same step is only paid for once.

The key (ELEVENLABS_API_KEY) stays on the backend. Without it, `available()` is False and the app hides the
buttons. On a rate limit or quota error ElevenLabs is paused like the other services; no retries.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path

import httpx

import config
import limits

log = logging.getLogger(__name__)

API = "https://api.elevenlabs.io/v1"
SERVICE = "ElevenLabs"
STT_MODEL = os.getenv("ELEVENLABS_STT_MODEL", "scribe_v3")
TTS_MODEL = os.getenv("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5")
VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")  # the voice in ElevenLabs' docs examples
OUTPUT_FORMAT = "mp3_44100_64"
MAX_AUDIO_BYTES = 5 * 1024 * 1024  # a minute of browser speech is well under 1 MB
MAX_TTS_CHARS = 1500
CACHE_DIR = Path(__file__).resolve().parent.parent / ".tts_cache"
CACHE_SECONDS = 7 * 24 * 3600


class VoiceError(RuntimeError):
    pass


def available() -> bool:
    return bool(config.elevenlabs_key()) and not limits.paused(SERVICE)


def _check(r: httpx.Response) -> None:
    if r.status_code == 429:
        raise VoiceError("429 rate limit")
    if r.status_code in (401, 402) and "quota" in r.text.lower():
        raise VoiceError(f"{r.status_code} quota exceeded")
    if r.status_code >= 400:
        raise VoiceError(f"HTTP {r.status_code}")


def transcribe(audio: bytes, content_type: str = "audio/webm") -> str | None:
    """Text of a short recording, or None if ElevenLabs is unavailable or failed."""
    if not available() or not audio or len(audio) > MAX_AUDIO_BYTES:
        return None
    ext = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/mpeg": "mp3", "audio/wav": "wav"}.get(
        content_type.split(";")[0].strip(), "webm")
    try:
        r = httpx.post(f"{API}/speech-to-text", headers={"xi-api-key": config.elevenlabs_key()},
                       data={"model_id": STT_MODEL}, files={"file": (f"speech.{ext}", audio, content_type)}, timeout=60)
        _check(r)
        text = (r.json().get("text") or "").strip()
    except Exception as e:  # noqa: BLE001
        if not limits.note_failure(SERVICE, e):
            log.warning("ElevenLabs speech-to-text failed: %s", e if isinstance(e, VoiceError) else type(e).__name__)
        return None
    return text or None


def _cache_path(text: str) -> Path:
    key = hashlib.sha256(f"{TTS_MODEL}|{VOICE_ID}|{OUTPUT_FORMAT}|{text}".encode()).hexdigest()
    return CACHE_DIR / f"{key}.mp3"


def speak(text: str) -> bytes | None:
    """MP3 of `text` (cached 7 days), or None if ElevenLabs is unavailable or failed."""
    text = " ".join((text or "").split())[:MAX_TTS_CHARS]
    if not text:
        return None
    path = _cache_path(text)
    try:
        if path.exists() and time.time() - path.stat().st_mtime < CACHE_SECONDS:
            return path.read_bytes()
    except OSError:
        pass
    if not available():
        return None
    try:
        r = httpx.post(f"{API}/text-to-speech/{VOICE_ID}", params={"output_format": OUTPUT_FORMAT},
                       headers={"xi-api-key": config.elevenlabs_key(), "Content-Type": "application/json"},
                       json={"text": text, "model_id": TTS_MODEL}, timeout=60)
        _check(r)
        audio = r.content
    except Exception as e:  # noqa: BLE001
        if not limits.note_failure(SERVICE, e):
            log.warning("ElevenLabs text-to-speech failed: %s", e if isinstance(e, VoiceError) else type(e).__name__)
        return None
    if not audio:
        return None
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        path.write_bytes(audio)
    except OSError as e:
        log.warning("Could not cache speech audio: %s", e)
    return audio
