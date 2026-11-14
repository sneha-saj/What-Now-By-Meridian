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
    topics = exa_search.plan_topics("nurse", [{"id": "job_seeker_graduate", "query": "permit after graduation"}])
    results = exa_search.search_plan_sources(topics)

    assert [t for t, _ in topics] == ["register_jobseeker", "unemployment_benefits", "labour_shortage", "plan_b:job_seeker_graduate"]
    assert "nurse" in dict(topics)["labour_shortage"]
    assert len(client.kwargs) == 4
    for kw in client.kwargs:
        assert kw["include_domains"] == ["migri.fi", "kela.fi", "infofinland.fi", "tyomarkkinatori.fi"]
        assert kw["contents"] == {"highlights": True}
        assert "June 2025" in kw["objective"]
    # Pages without a highlight are dropped; duplicates across topics are kept once.
    assert results == [{"topic": "register_jobseeker", "title": "Kela", "url": "https://www.kela.fi/a",
                        "highlight": "Labour market subsidy", "published": None}]


def test_plan_search_returns_none_when_exa_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(exa_search, "CACHE_PATH", tmp_path / "exa-cache.json")

    class Broken:
        def search(self, *a, **k):
            raise RuntimeError("offline")

    monkeypatch.setattr(exa_search, "_get_client", lambda: Broken())
    assert exa_search.search_plan_sources([("t", "q")]) is None


class PeopleExa:
    def __init__(self):
        self.calls = []

    def search(self, query, **kwargs):
        self.calls.append((query, kwargs))
        if kwargs.get("category") == "people":
            return SimpleNamespace(results=[SimpleNamespace(title="Aino Virtanen - Head Chef - Rafla Oy | LinkedIn",
                                                            url="https://linkedin.com/in/aino", highlights=["12 cooks"])])
        return SimpleNamespace(results=[SimpleNamespace(title=f"Co {i}", url=f"https://c{i}.fi", highlights=["h"])
                                        for i in range(10)])


def test_referral_searches_limit_results_and_use_categories(monkeypatch, tmp_path):
    monkeypatch.setattr(exa_search, "CACHE_PATH", tmp_path / "exa-cache.json")
    client = PeopleExa()
    monkeypatch.setattr(exa_search, "_get_client", lambda: client)

    companies = exa_search.search_companies("cook", "Helsinki")
    assert len(companies) == 8
    company_calls = [c for c in client.calls if c[1].get("category") == "company"]
    assert len(company_calls) == 1 and company_calls[0][1]["num_results"] == 8

    people = exa_search.search_people(companies, "cook", "Helsinki")
    people_calls = [c for c in client.calls if c[1].get("category") == "people"]
    assert len(people_calls) == 3  # top 3 companies only
    assert all(c[1]["num_results"] == 1 for c in people_calls)
    assert people[0] == {"name": "Aino Virtanen", "role": "Head Chef", "company": "Co 0",
                         "profile_url": "https://linkedin.com/in/aino", "highlight": "12 cooks"}

    communities = exa_search.search_communities("cook", "Helsinki", "2026-11-14")
    assert {g["kind"] for g in communities} == {"professional_group", "union"}
    assert len(client.calls) == 2 + 3 + 2  # max 7 searches per /referrals request


def test_companies_with_hiring_evidence_rank_first(monkeypatch, tmp_path):
    monkeypatch.setattr(exa_search, "CACHE_PATH", tmp_path / "exa-cache.json")

    class HiringExa:
        def search(self, query, **kw):
            if kw.get("category") == "company":
                return SimpleNamespace(results=[
                    SimpleNamespace(title="Quiet Oy", url="https://quiet.fi/", highlights=[]),
                    SimpleNamespace(title="Posts Oy", url="https://www.posts.fi/", highlights=[]),
                    SimpleNamespace(title="Careers Oy", url="https://careers-oy.fi/careers", highlights=[])])
            return SimpleNamespace(results=[SimpleNamespace(title="Cook", url="https://posts.fi/jobs/cook-123", highlights=[])])

    monkeypatch.setattr(exa_search, "_get_client", lambda: HiringExa())
    out = exa_search.search_companies("cook", "Helsinki")
    assert [c["name"] for c in out] == ["Posts Oy", "Careers Oy", "Quiet Oy"]
    assert out[0]["hiring_evidence"] == "https://posts.fi/jobs/cook-123"
    assert out[1]["hiring_evidence"] == "https://careers-oy.fi/careers"
    assert out[2]["hiring_evidence"] is None


def test_searches_report_live_activity(monkeypatch, tmp_path):
    import activity
    monkeypatch.setattr(exa_search, "CACHE_PATH", tmp_path / "exa-cache.json")
    monkeypatch.setattr(exa_search, "_get_client", lambda: RecordingExa())
    events = []
    activity.set_emitter(events.append)
    try:
        exa_search.search_plan_sources(exa_search.plan_topics(None, []))
        exa_search.search_plan_sources(exa_search.plan_topics(None, []))  # second time: from cache
    finally:
        activity.set_emitter(None)
    searching = [e for e in events if e["status"] == "searching"]
    found = [e for e in events if e["status"] == "found"]
    assert len(searching) == len(found) == 3
    assert {e["purpose"] for e in searching} == {"registering as a jobseeker", "unemployment benefits", "labour-shortage sectors"}
    assert searching[0]["domains"] == ["migri.fi", "kela.fi", "infofinland.fi", "tyomarkkinatori.fi"]
    assert found[0]["results"][0]["url"] == "https://www.kela.fi/a"
    assert events[-1]["status"] == "cached"


def test_plan_queries_use_city_region_and_field():
    topics = dict(exa_search.plan_topics("cook", [], "Helsinki"))
    assert "Helsinki" in topics["register_jobseeker"]
    assert "Uusimaa" in topics["labour_shortage"] and "cook" in topics["labour_shortage"]
