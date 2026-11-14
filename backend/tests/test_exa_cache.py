from types import SimpleNamespace

from services import exa_search


class FakeExa:
    def __init__(self):
        self.calls = 0

    def search(self, *_args, **_kwargs):
        self.calls += 1
        result = SimpleNamespace(title="Migri", url="https://migri.fi/en/end-of-employment", highlights=["Official guidance"])
        return SimpleNamespace(results=[result])


def test_official_search_results_are_cached_to_file(monkeypatch, tmp_path):
    monkeypatch.setattr(exa_search, "CACHE_PATH", tmp_path / "exa-cache.json")
    client = FakeExa()
    monkeypatch.setattr(exa_search, "_get_client", lambda: client)
    queries = ["permit after job loss"]

    first = exa_search.search_official(queries)
    second = exa_search.search_official(queries)

    assert first == second
    assert client.calls == 1
    assert (tmp_path / "exa-cache.json").exists()


def test_expired_cache_entries_are_ignored(monkeypatch, tmp_path):
    monkeypatch.setattr(exa_search, "CACHE_PATH", tmp_path / "exa-cache.json")
    key = exa_search._cache_key("official", {"queries": ["q"], "per_query": 3})
    exa_search.CACHE_PATH.write_text('{"' + key + '": {"expires_at": "2000-01-01T00:00:00+00:00", "value": [{"old": true}]}}')
    assert exa_search._cache_read(key) is None
