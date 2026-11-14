"""ElevenLabs — read the plan aloud (optional tech challenge).

Not wired in yet. Plan: a "Listen" button on the plan card calls a /speak endpoint that
returns MP3 audio of the deadline + this week's 3 things, in a calm voice.
Enabled with ENABLE_ELEVENLABS=true plus ELEVENLABS_API_KEY.
"""

import os

import config


def is_enabled() -> bool:
    return config.ENABLE_ELEVENLABS and bool(os.getenv("ELEVENLABS_API_KEY"))


def text_to_speech(text: str, voice_id: str | None = None) -> bytes:
    """Return MP3 bytes for `text`.

    TODO: use the `elevenlabs` SDK: ElevenLabs(api_key=...).text_to_speech.convert(
    voice_id=voice_id, text=text, model_id="eleven_multilingual_v2") and join the chunks.
    """
    if not is_enabled():
        raise RuntimeError("ElevenLabs is disabled (set ENABLE_ELEVENLABS=true and ELEVENLABS_API_KEY).")
    raise NotImplementedError("ElevenLabs text-to-speech not implemented yet.")
