from datetime import datetime, timezone

import live_check
from countries.finland import DEADLINE_RULES


def test_live_check_uses_exa_content_and_gemini_result(monkeypatch, tmp_path):
    monkeypatch.setattr(live_check, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(live_check.config, "exa_key", lambda: "exa")
    monkeypatch.setattr(live_check.config, "gemini_key", lambda: "gemini")
    monkeypatch.setattr(live_check, "_fetch_page", lambda _url: "official Migri page text")
    monkeypatch.setattr(live_check, "_ask_gemini", lambda _rule, page: ("official" in page, "3 or 6 months"))
    result = live_check.check_rule(DEADLINE_RULES[0])
    assert result["status"] == "verified"
    assert result["evidence_snippet"] == "3 or 6 months"
    assert datetime.fromisoformat(result["checked_at"]).tzinfo == timezone.utc
    assert live_check.check_rule(DEADLINE_RULES[0])["status"] == "verified"


def test_live_check_mismatch_and_errors_are_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(live_check, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(live_check.config, "exa_key", lambda: "exa")
    monkeypatch.setattr(live_check.config, "gemini_key", lambda: "gemini")
    monkeypatch.setattr(live_check, "_fetch_page", lambda _url: "page")
    monkeypatch.setattr(live_check, "_ask_gemini", lambda _rule, _page: (False, "Rule differs"))
    assert live_check.check_rule(DEADLINE_RULES[0])["status"] == "mismatch"
    monkeypatch.setattr(live_check, "_fetch_page", lambda _url: (_ for _ in ()).throw(RuntimeError("offline")))
    assert live_check.check_rule(DEADLINE_RULES[1], force=True)["status"] == "error"
