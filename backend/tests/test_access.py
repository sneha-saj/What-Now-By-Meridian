"""Access codes: only requests with a valid code may use the paid APIs; everyone else gets free demo mode."""

import json
import os

os.environ["FORCE_MOCKS"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


@pytest.fixture
def codes(monkeypatch):
    monkeypatch.setattr(main.config, "ACCESS_CODES", ["judge-123"])
    monkeypatch.setenv("FORCE_MOCKS", "false")  # so the code, not the test setup, decides


def test_without_access_codes_everyone_is_live(monkeypatch):
    monkeypatch.setattr(main.config, "ACCESS_CODES", [])
    assert client.get("/health").json()["live"] is True


def test_demo_without_a_code_live_with_the_right_one(codes):
    assert client.get("/health").json()["live"] is False
    assert client.get("/health", headers={"X-Access-Code": "nope"}).json()["live"] is False
    h = client.get("/health", headers={"X-Access-Code": "judge-123"}).json()
    assert h["live"] is True and h["access_codes"] is True


def test_no_paid_keys_without_a_code(codes, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    seen = {}
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: seen.setdefault("key", main.config.gemini_key()) and None)
    client.post("/chat", json={"messages": [{"role": "user", "text": "I was laid off"}]})
    assert seen["key"] is None  # demo: the key is hidden, so nothing paid is called
    seen.clear()
    client.post("/chat", json={"messages": [{"role": "user", "text": "I was laid off"}]}, headers={"X-Access-Code": "judge-123"})
    assert seen["key"] == "g"


def test_the_setting_reaches_the_streaming_worker_thread(codes, monkeypatch):
    seen = []
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: seen.append(main.config.live()) or None)
    for headers in ({}, {"X-Access-Code": "judge-123"}):
        with client.stream("POST", "/chat/stream", json={"messages": [{"role": "user", "text": "I was laid off"}]},
                           headers=headers) as r:
            events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
        assert events[-1]["type"] == "result"
    assert seen == [False, True]
