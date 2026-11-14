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


def test_live_check_includes_rule_id_and_does_not_cache_errors(monkeypatch, tmp_path):
    monkeypatch.setattr(live_check, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(live_check.config, "exa_key", lambda: None)
    first = live_check.check_rule(DEADLINE_RULES[0])
    assert first["rule_id"] == DEADLINE_RULES[0]["id"] and first["status"] == "error"

    # Once keys are added, the next request checks again instead of serving a cached error.
    monkeypatch.setattr(live_check.config, "exa_key", lambda: "exa")
    monkeypatch.setattr(live_check.config, "gemini_key", lambda: "gemini")
    monkeypatch.setattr(live_check, "_fetch_page", lambda _url: "page")
    monkeypatch.setattr(live_check, "_ask_gemini", lambda _rule, _page: (True, "3 months"))
    second = live_check.check_rule(DEADLINE_RULES[0])
    assert second["status"] == "verified" and second["rule_id"] == DEADLINE_RULES[0]["id"]


def test_rules_sharing_a_page_fetch_it_once(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(live_check.config, "exa_key", lambda: "exa")
    monkeypatch.setattr(live_check.config, "gemini_key", lambda: "gemini")
    fetches = []

    class FakeExa:
        def __init__(self, api_key):
            pass

        def get_contents(self, urls, text, **kwargs):
            fetches.append(urls)
            return SimpleNamespace(results=[SimpleNamespace(text="Migri page text")])

    import exa_py
    monkeypatch.setattr(exa_py, "Exa", FakeExa)
    monkeypatch.setattr(live_check, "_ask_gemini", lambda _rule, _page: (True, "3 months"))
    statuses = [live_check.check_rule(r)["status"] for r in DEADLINE_RULES]
    assert statuses == ["verified"] * len(DEADLINE_RULES)
    assert len(fetches) == 1


def test_failed_api_check_is_cached_briefly(monkeypatch):
    monkeypatch.setattr(live_check.config, "exa_key", lambda: "exa")
    monkeypatch.setattr(live_check.config, "gemini_key", lambda: "gemini")
    calls = []
    monkeypatch.setattr(live_check, "_fetch_page", lambda _url: calls.append(1) or (_ for _ in ()).throw(RuntimeError("down")))
    assert live_check.check_rule(DEADLINE_RULES[0])["status"] == "error"
    assert live_check.check_rule(DEADLINE_RULES[0])["status"] == "error"
    assert len(calls) == 1  # not retried on every request


def test_context_dev_reads_official_page_fresh_and_caches_it(monkeypatch, tmp_path):
    import httpx
    from integrations import context_dev
    monkeypatch.setattr(live_check, "PAGE_CACHE_PATH", tmp_path / "pages.json")
    monkeypatch.setattr(context_dev.config, "context_key", lambda: "context-key")
    monkeypatch.setattr(live_check.config, "exa_key", lambda: None)
    requests = []

    def fake_post(url, **kwargs):
        requests.append((url, kwargs))
        return httpx.Response(200, json={"markdown": {"requested": True, "success": True, "data": "Official Migri rule text"}},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(context_dev.httpx, "post", fake_post)
    page_url = DEADLINE_RULES[0]["source_url"]
    assert live_check._fetch_page(page_url) == "Official Migri rule text"
    assert live_check._fetch_page(page_url) == "Official Migri rule text"
    assert len(requests) == 1
    assert requests[0][1]["json"]["url"] == page_url
    assert "context-key" in requests[0][1]["headers"]["Authorization"]
    body = requests[0][1]["json"]
    assert body["maxAgeMs"] == 0  # "checked against migri.fi today" means a fresh copy, once a day
    assert body["formats"] == {"markdown": True} and body["sharedParams"] == {"mainContentOnly": True}
    assert body["timeoutOpts"] == {"milliseconds": 30_000, "behavior": "return-partial"}


def test_context_dev_failure_uses_exa(monkeypatch, tmp_path):
    monkeypatch.setattr(live_check, "PAGE_CACHE_PATH", tmp_path / "pages.json")
    monkeypatch.setattr(live_check.config, "context_key", lambda: "context-key")
    monkeypatch.setattr(live_check.config, "exa_key", lambda: "exa-key")
    monkeypatch.setattr(live_check, "_fetch_context_page", lambda _url: (_ for _ in ()).throw(RuntimeError("failed")))
    monkeypatch.setattr(live_check, "_fetch_exa_page", lambda _url, _key: "Exa page")
    assert live_check._fetch_page(DEADLINE_RULES[0]["source_url"]) == "Exa page"


def test_check_says_which_service_read_the_page(monkeypatch, tmp_path):
    import httpx
    from integrations import context_dev
    monkeypatch.setattr(live_check, "CACHE_PATH", tmp_path / "live.json")
    monkeypatch.setattr(live_check, "PAGE_CACHE_PATH", tmp_path / "pages.json")
    monkeypatch.setattr(context_dev.config, "context_key", lambda: "context-key")
    monkeypatch.setattr(live_check.config, "gemini_key", lambda: "gemini")
    monkeypatch.setattr(live_check.config, "exa_key", lambda: None)
    monkeypatch.setattr(context_dev.httpx, "post", lambda url, **kw: httpx.Response(
        200, json={"markdown": {"requested": True, "success": True, "data": "3 months"}}, request=httpx.Request("POST", url)))
    monkeypatch.setattr(live_check, "_ask_gemini", lambda rule, page: (True, "3 months"))
    result = live_check.check_rule(DEADLINE_RULES[0], force=True)
    assert result["status"] == "verified" and result["read_by"] == "context.dev"
