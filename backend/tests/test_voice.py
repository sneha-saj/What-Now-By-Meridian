"""ElevenLabs voice typing and Listen. httpx is faked: no live calls."""

import os

os.environ["FORCE_MOCKS"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import limits  # noqa: E402
import main  # noqa: E402
from integrations import elevenlabs  # noqa: E402

client = TestClient(main.app)


class Resp:
    def __init__(self, status=200, body=None, content=b"", text=""):
        self.status_code, self._body, self.content, self.text = status, body or {}, content, text

    def json(self):
        return self._body


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setattr(elevenlabs.config, "elevenlabs_key", lambda: "xi-test")


def test_without_a_key_the_voice_buttons_are_hidden_and_nothing_is_called(monkeypatch):
    monkeypatch.setattr(elevenlabs.httpx, "post", lambda *a, **k: pytest.fail("called without a key"))
    assert client.get("/health").json()["voice"] is False
    assert client.post("/voice/transcribe", content=b"abc", headers={"content-type": "audio/webm"}).status_code == 503
    assert client.post("/voice/speak", json={"text": "Step 1"}).status_code == 503


def test_voice_typing_sends_the_clip_and_returns_text(monkeypatch, key):
    sent = {}

    def post(url, headers, data, files, timeout):
        sent.update(url=url, headers=headers, data=data, files=files)
        return Resp(body={"text": " I was laid off in Espoo. "})
    monkeypatch.setattr(elevenlabs.httpx, "post", post)
    r = client.post("/voice/transcribe", content=b"fake-webm", headers={"content-type": "audio/webm;codecs=opus"})
    assert r.json() == {"text": "I was laid off in Espoo."}
    assert sent["url"].endswith("/v1/speech-to-text") and sent["headers"] == {"xi-api-key": "xi-test"}
    assert sent["data"] == {"model_id": "scribe_v3"} and sent["files"]["file"][0] == "speech.webm"


def test_too_long_or_empty_recordings_are_refused(monkeypatch, key):
    monkeypatch.setattr(elevenlabs.httpx, "post", lambda *a, **k: pytest.fail("should not be sent"))
    assert client.post("/voice/transcribe", content=b"", headers={"content-type": "audio/webm"}).status_code == 422
    big = b"x" * (elevenlabs.MAX_AUDIO_BYTES + 1)
    assert client.post("/voice/transcribe", content=big, headers={"content-type": "audio/webm"}).status_code == 413


def test_listen_returns_mp3_and_caches_it(monkeypatch, key):
    calls = []

    def post(url, params, headers, json, timeout):
        calls.append((url, params, json))
        return Resp(content=b"ID3mp3")
    monkeypatch.setattr(elevenlabs.httpx, "post", post)
    for _ in range(2):
        r = client.post("/voice/speak", json={"text": "Step 1. Register as a jobseeker."})
        assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3mp3"
    assert len(calls) == 1  # second time from the cache
    url, params, body = calls[0]
    assert url.endswith(f"/v1/text-to-speech/{elevenlabs.VOICE_ID}") and body["model_id"] == "eleven_flash_v2_5"


def test_rate_limit_pauses_voice_without_retrying(monkeypatch, key):
    calls = []
    monkeypatch.setattr(elevenlabs.httpx, "post", lambda *a, **k: calls.append(1) or Resp(status=429))
    assert client.post("/voice/speak", json={"text": "a"}).status_code == 503
    assert limits.paused("ElevenLabs") and client.post("/voice/speak", json={"text": "b"}).status_code == 503
    assert len(calls) == 1
