"""Tests never call real Gemini, Exa or Context.dev, and never touch the real cache files.

FORCE_MOCKS makes config return no API keys, so no real client can be created. Tests that need a
"live" path monkeypatch the client or service functions explicitly.
"""

import os

os.environ["FORCE_MOCKS"] = "true"
os.environ.pop("USE_MOCK", None)

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_caches_and_limits(monkeypatch, tmp_path):
    import limits
    import live_check
    import sources_log
    from integrations import context_dev
    from services import exa_search, gemini

    monkeypatch.setattr(exa_search, "CACHE_PATH", tmp_path / "exa.json")
    monkeypatch.setattr(gemini, "CACHE_PATH", tmp_path / "gemini.json")
    monkeypatch.setattr(live_check, "CACHE_PATH", tmp_path / "live.json")
    monkeypatch.setattr(live_check, "PAGE_CACHE_PATH", tmp_path / "pages.json")
    monkeypatch.setattr(sources_log, "PATH", tmp_path / "sources.json")
    monkeypatch.setattr(context_dev, "CACHE_PATH", tmp_path / "context_dev.json")
    limits.reset()
    yield
    limits.reset()
