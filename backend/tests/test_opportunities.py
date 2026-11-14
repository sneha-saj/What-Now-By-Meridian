"""Perks and support with Exa and Gemini mocked: every item needs a real Exa row; rules enforced in code."""

from datetime import date
from types import SimpleNamespace

import pytest

import opportunities as opps
from models import Facts
from services import exa_search

TODAY = date(2026, 11, 14)
FACTS = Facts(citizenship_group="other", permit_type="work_based", years_on_work_permit=1,
              job_end_date=date(2026, 11, 1), city="Helsinki", field="cook")

RAW = {
    "perks:certificate": [{"title": "Job search certificate", "url": "https://tyomarkkinatori.fi/cert", "published": "2026-10-01", "highlight": "Download it", "purpose": "perks"}],
    "perks:discounts": [{"title": "Swimming halls", "url": "https://www.hel.fi/swim", "published": "2026-09-01", "highlight": "50% off", "purpose": "perks"}],
    "perks:incentives": [{"title": "Helsinki benefit", "url": "https://www.hel.fi/benefit", "published": None, "highlight": "3 months unemployed", "purpose": "perks"}],
}

NOTES = {
    "certificate": {"row_id": "R1", "how_to_get": "Download it from your account"},
    "discounts": [{"row_id": "R2", "name": "Swimming", "discount": "50% off", "proof_needed": "Certificate"},
                  {"row_id": "R99", "name": "Invented", "discount": "free", "proof_needed": "x"}],
    "incentives": [{"row_id": "R3", "name": "Helsinki benefit", "what_it_is": "Pays employers", "conditions_plain": "You must be unemployed for 3 months",
                    "may_apply": True, "caveat": ""}],
}


@pytest.fixture
def mocked(monkeypatch):
    monkeypatch.setattr(opps.exa_search, "search_opportunities", lambda *a: {k: [dict(r) for r in v] for k, v in RAW.items()})
    monkeypatch.setattr(opps.gemini, "write_opportunities", lambda *a: NOTES)


def test_only_perks_and_support_every_item_sourced_and_rules_enforced(mocked):
    out = opps.build(FACTS, 3, TODAY)
    assert set(out.model_dump()) == {"perks_and_support", "counts", "mock", "demo"}
    perks = out.perks_and_support
    assert perks.certificate.source_url == "https://tyomarkkinatori.fi/cert" and perks.certificate.source_date == "2026-10-01"
    assert [d.discount for d in perks.discounts] == ["50% off"]  # invented discount dropped
    assert perks.discounts[0].source_date == "2026-09-01"
    assert "may not work in time" in perks.incentives[0].caveat  # 3 months unemployed vs a 3-month deadline
    assert out.mock is False


def test_incentive_without_conflict_keeps_may_apply_caveat(mocked):
    out = opps.build(FACTS, 6, TODAY)
    assert out.perks_and_support.incentives[0].caveat == opps.MAY_APPLY


def test_no_exa_means_no_invented_opportunities(monkeypatch):
    monkeypatch.setattr(opps.exa_search, "search_opportunities", lambda *a: None)
    monkeypatch.setattr(opps.gemini, "write_opportunities", lambda *a: pytest.fail("Gemini called without data"))
    out = opps.build(FACTS, 3, TODAY)
    assert out.mock is True and out.perks_and_support.certificate is None and out.counts.total == 0


def test_opportunity_searches_are_limited_and_scoped(monkeypatch, tmp_path):
    calls = []

    class FakeExa:
        def search(self, q, **kw):
            calls.append((q, kw))
            return SimpleNamespace(results=[SimpleNamespace(title="t", url="https://www.hel.fi/x", highlights=["h"], published_date=None)])

    monkeypatch.setattr(exa_search, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(exa_search, "_get_client", lambda: FakeExa())
    from countries.finland import PERK_TOPICS
    PERK_QUERIES = {t: PERK_TOPICS[t]["query"] for t in ("certificate", "discounts", "incentives")}
    out = exa_search.search_opportunities("cook", "Helsinki", "2026-11-14", ["hel.fi"], PERK_QUERIES)
    assert len(calls) == len(PERK_QUERIES) == 3
    assert all(kw["num_results"] <= 5 for _, kw in calls)
    assert all("hel.fi" in kw["include_domains"] and "migri.fi" in kw["include_domains"] for _, kw in calls)
    assert set(out) == {"perks:certificate", "perks:discounts", "perks:incentives"}
    exa_search.search_opportunities("cook", "Helsinki", "2026-11-14", ["hel.fi"], PERK_QUERIES)
    assert len(calls) == 3  # second time from cache


# ---------- which topics (plain rules) ----------

def _ids(**facts):
    return [t.id for t in opps.perk_topics(Facts(**facts))]


def test_always_the_certificate_discounts_and_incentives_first():
    assert _ids()[:3] == ["certificate", "discounts", "incentives"]


def test_fund_members_get_fund_help_and_others_get_kela():
    assert "fund_support" in _ids(unemployment_fund="yes") and "kela_extra" not in _ids(unemployment_fund="yes")
    assert "kela_extra" in _ids(unemployment_fund="no") and "fund_support" not in _ids(unemployment_fund="no")
    assert {"fund_support", "kela_extra"} <= set(_ids(unemployment_fund="not_sure"))


def test_language_courses_for_work_permits_and_travel_only_with_a_city():
    work = dict(citizenship_group="other", permit_type="work_based", unemployment_fund="yes")
    assert "language_courses" in _ids(**work) and "travel_discount" not in _ids(**work)
    assert "travel_discount" not in _ids(**work, city="Espoo")  # capped at 5: fund and courses come first
    assert "travel_discount" in _ids(citizenship_group="other", permit_type="permanent", unemployment_fund="yes", city="Espoo")
    assert "language_courses" not in _ids(citizenship_group="other", permit_type="permanent", unemployment_fund="yes")


def test_at_most_five_topics_each_with_a_reason():
    topics = opps.perk_topics(Facts(citizenship_group="other", permit_type="work_based", unemployment_fund="not_sure",
                                    city="Espoo"))
    assert len(topics) == 5 and all(t.reason and t.label for t in topics)


def test_extra_topics_are_searched_and_shown_with_their_sources(monkeypatch):
    seen = {}
    raw = {**{k: [dict(r) for r in v] for k, v in RAW.items()},
           "perks:kela_extra": [{"title": "Housing allowance", "url": "https://www.kela.fi/housing", "published": "2026-08-01",
                                 "highlight": "General housing allowance", "purpose": "perks"}]}
    monkeypatch.setattr(opps.exa_search, "search_opportunities",
                        lambda field, city, today, domains, queries: seen.setdefault("q", queries) and raw)
    monkeypatch.setattr(opps.gemini, "write_opportunities", lambda *a: {**NOTES, "support": [
        {"row_id": "R4", "name": "General housing allowance", "what_it_is": "Help with rent", "how_to_get": "Apply in OmaKela"},
        {"row_id": "R99", "name": "Invented", "what_it_is": "x"}]})
    out = opps.build(Facts(**{**FACTS.model_dump(), "unemployment_fund": "no"}), 3, TODAY)
    assert "kela_extra" in seen["q"] and "fund_support" not in seen["q"]
    assert [s.name for s in out.perks_and_support.support] == ["General housing allowance"]
    assert out.perks_and_support.support[0].source_url == "https://www.kela.fi/housing"
    assert [t.id for t in out.perks_and_support.topics][:4] == ["certificate", "discounts", "incentives", "kela_extra"]
