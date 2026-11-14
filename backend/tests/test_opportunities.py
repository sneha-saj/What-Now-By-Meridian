"""Opportunities with Exa and Gemini mocked: every item needs a real Exa row; rules enforced in code."""

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
    "hidden_jobs": [
        {"title": "Rafla opens in Kallio", "url": "https://news.fi/rafla", "published": "2026-10-30", "highlight": "Rafla is hiring 20 cooks", "purpose": "hiring signals"},
        {"title": "Old news", "url": "https://news.fi/old", "published": "2026-06-01", "highlight": "Expanding", "purpose": "hiring signals"},
    ],
    "events": [{"title": "Restaurant job fair", "url": "https://fair.fi", "published": None, "highlight": "26 Nov", "purpose": "events"}],
    "support:language_courses": [{"title": "Finnish for jobseekers", "url": "https://www.hel.fi/finnish", "published": "2026-09-01", "highlight": "Free for unemployed", "purpose": "support"}],
    "perks:certificate": [{"title": "Job search certificate", "url": "https://tyomarkkinatori.fi/cert", "published": None, "highlight": "Download it", "purpose": "perks"}],
    "perks:discounts": [{"title": "Swimming halls", "url": "https://www.hel.fi/swim", "published": None, "highlight": "50% off", "purpose": "perks"}],
    "perks:incentives": [{"title": "Helsinki benefit", "url": "https://www.hel.fi/benefit", "published": None, "highlight": "3 months unemployed", "purpose": "perks"}],
}

NOTES = {
    "hidden_jobs": [{"row_id": "R1", "company": "Rafla", "signal": "Opening in Kallio", "why_it_fits": "Needs cooks"},
                    {"row_id": "R2", "company": "Old Oy", "signal": "Expanding", "why_it_fits": "x"},
                    {"row_id": "R99", "company": "Invented Oy", "signal": "x", "why_it_fits": "x"}],
    "support": [{"row_id": "R4", "name": "Finnish course", "what_it_is": "Free course", "why_it_may_apply": "may apply", "plausible": True},
                {"row_id": "R4", "name": "Not for you", "what_it_is": "x", "why_it_may_apply": "x", "plausible": False}],
    "events": [{"row_id": "R3", "name": "Job fair", "date": "2026-11-26", "place": "Helsinki", "why_relevant": "Restaurants recruit"},
               {"row_id": "R3", "name": "Far away fair", "date": "2027-03-01", "why_relevant": "x"},
               {"row_id": "R3", "name": "No date", "date": None, "why_relevant": "x"}],
    "certificate": {"row_id": "R5", "how_to_get": "Download it from your account"},
    "discounts": [{"row_id": "R6", "name": "Swimming", "discount": "50% off", "proof_needed": "Certificate"},
                  {"row_id": "R99", "name": "Invented", "discount": "free", "proof_needed": "x"}],
    "incentives": [{"row_id": "R7", "name": "Helsinki benefit", "what_it_is": "Pays employers", "conditions_plain": "You must be unemployed for 3 months",
                    "may_apply": True, "caveat": ""}],
}


@pytest.fixture
def mocked(monkeypatch):
    monkeypatch.setattr(opps.exa_search, "search_opportunities", lambda *a: {k: [dict(r) for r in v] for k, v in RAW.items()})
    monkeypatch.setattr(opps.gemini, "write_opportunities", lambda *a: NOTES)
    people = [{"name": "Aino", "role": "Chef", "company": "Rafla", "profile_url": "https://linkedin.com/in/aino", "highlight": ""}]
    calls = {}
    monkeypatch.setattr(opps.exa_search, "search_people", lambda companies, *a, **k: calls.setdefault("top", companies) and people)
    monkeypatch.setattr(opps.gemini, "write_contact_drafts", lambda facts, contacts, incentive: calls.setdefault("incentive", incentive) and
                        {"drafts": [{"id": "P1", "why_this_person": "Head chef at Rafla", "message": "Hi Aino, congrats on Kallio! [Your name]"}]})
    return calls


def test_every_item_is_sourced_and_rules_are_enforced(mocked):
    out = opps.build(FACTS, 3, TODAY)
    assert [h.company for h in out.hidden_jobs] == ["Rafla"]  # old signal and invented row dropped
    assert out.hidden_jobs[0].signal_date == "2026-10-30" and out.hidden_jobs[0].source_url == "https://news.fi/rafla"
    assert [s.name for s in out.support] == ["Finnish course"] and out.support[0].eligibility_note == "May apply, check the conditions."
    assert [e.name for e in out.events] == ["Job fair"]  # outside 30 days and undated events dropped
    perks = out.perks_and_support
    assert perks.certificate.source_url == "https://tyomarkkinatori.fi/cert"
    assert [d.discount for d in perks.discounts] == ["50% off"]  # invented discount dropped
    assert "may not work in time" in perks.incentives[0].caveat  # 3 months unemployed vs a 3-month deadline
    assert out.people[0].draft.startswith("Hi Aino") and out.people[0].profile_url.startswith("https://linkedin")
    assert mocked["top"] == [{"name": "Rafla", "signal": "Opening in Kallio"}]
    assert mocked["incentive"] == "Helsinki benefit"  # draft may mention the incentive
    assert out.mock is False


def test_no_exa_means_no_invented_opportunities(monkeypatch):
    monkeypatch.setattr(opps.exa_search, "search_opportunities", lambda *a: None)
    monkeypatch.setattr(opps.gemini, "write_opportunities", lambda *a: pytest.fail("Gemini called without data"))
    out = opps.build(FACTS, 3, TODAY)
    assert out.mock is True and not out.hidden_jobs and not out.events and out.perks_and_support.certificate is None


def test_long_drafts_fall_back_to_template(mocked, monkeypatch):
    monkeypatch.setattr(opps.gemini, "write_contact_drafts", lambda *a: {"drafts": [{"id": "P1", "why_this_person": "x", "message": "word " * 90}]})
    out = opps.build(FACTS, 3, TODAY)
    assert len(out.people[0].draft.split()) <= 80 and "Rafla" in out.people[0].draft


def test_opportunity_searches_are_limited_and_scoped(monkeypatch):
    calls = []

    class FakeExa:
        def search(self, q, **kw):
            calls.append((q, kw))
            return SimpleNamespace(results=[SimpleNamespace(title="t", url="https://www.hel.fi/x", highlights=["h"], published_date=None)])

    monkeypatch.setattr(exa_search, "_get_client", lambda: FakeExa())
    from countries.finland import PERK_QUERIES, SUPPORT_TYPES
    out = exa_search.search_opportunities("cook", "Helsinki", "2026-11-14", ["hel.fi"], SUPPORT_TYPES, PERK_QUERIES)
    assert len(calls) == 2 + len(SUPPORT_TYPES) + len(PERK_QUERIES) <= 9
    assert all(kw["num_results"] <= 8 for _, kw in calls)
    hidden = [kw for q, kw in calls if "start_published_date" in kw]
    assert hidden and hidden[0]["start_published_date"] == "2026-09-15"  # last 60 days
    scoped = [kw for q, kw in calls if "include_domains" in kw]
    assert len(scoped) == len(SUPPORT_TYPES) + len(PERK_QUERIES) and all("hel.fi" in kw["include_domains"] for kw in scoped)
    assert set(out) >= {"hidden_jobs", "events", "perks:certificate"}
    exa_search.search_opportunities("cook", "Helsinki", "2026-11-14", ["hel.fi"], SUPPORT_TYPES, PERK_QUERIES)
    assert len(calls) == 9  # second time from cache
