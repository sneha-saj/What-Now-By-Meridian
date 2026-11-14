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


class RecordingExa:
    def __init__(self):
        self.kwargs = []

    def search(self, query, **kwargs):
        self.kwargs.append(kwargs)
        return SimpleNamespace(results=[
            SimpleNamespace(title="Kela", url="https://www.kela.fi/a", highlights=["Labour market subsidy"]),
            SimpleNamespace(title="No highlight", url="https://www.kela.fi/b", highlights=[]),
        ])


def test_plan_search_uses_trusted_domains_and_highlights(monkeypatch, tmp_path):
    monkeypatch.setattr(exa_search, "CACHE_PATH", tmp_path / "exa-cache.json")
    client = RecordingExa()
    monkeypatch.setattr(exa_search, "_get_client", lambda: client)
    topics = exa_search.plan_topics("nurse", studied_in_finland=True, family_in_finland=None)
    results = exa_search.search_plan_sources(topics)

    assert [t for t, _ in topics] == ["register_jobseeker", "unemployment_benefits", "alternative_permits", "labour_shortage"]
    assert "after graduating" in dict(topics)["alternative_permits"]
    assert "nurse" in dict(topics)["labour_shortage"]
    assert len(client.kwargs) == 4
    for kw in client.kwargs:
        assert kw["include_domains"] == ["migri.fi", "kela.fi", "infofinland.fi", "tyomarkkinatori.fi"]
        assert kw["contents"] == {"highlights": True}
        assert "June 2025" in kw["objective"]
    # Pages without a highlight are dropped; duplicates across topics are kept once.
    assert results == [{"topic": "register_jobseeker", "title": "Kela", "url": "https://www.kela.fi/a",
                        "highlight": "Labour market subsidy"}]


def test_plan_search_returns_none_when_exa_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(exa_search, "CACHE_PATH", tmp_path / "exa-cache.json")

    class Broken:
        def search(self, *a, **k):
            raise RuntimeError("offline")

    monkeypatch.setattr(exa_search, "_get_client", lambda: Broken())
    assert exa_search.search_plan_sources([("t", "q")]) is None
