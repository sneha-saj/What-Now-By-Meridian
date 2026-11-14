"""API tests with Exa and Gemini mocked (no network, no keys)."""

import os

os.environ["FORCE_MOCKS"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)

VERIFIED = {"status": "verified", "checked_at": "2026-11-14T10:00:00+00:00", "evidence_snippet": "3 months"}
ERROR = {"status": "error", "checked_at": "2026-11-14T10:00:00+00:00", "evidence_snippet": "Unavailable"}
WORK_FACTS = {"citizenship_group": "other", "permit_type": "work_based", "years_on_work_permit": "under_2",
              "job_end_date": "2026-11-01", "field": "nurse", "city": "Espoo"}

EXA_SOURCES = [
    {"topic": "register_jobseeker", "title": "Register as a jobseeker", "url": "https://tyomarkkinatori.fi/en/register",
     "highlight": "Register as a jobseeker no later than your first day of unemployment."},
    {"topic": "unemployment_benefits", "title": "Kela unemployment", "url": "https://www.kela.fi/unemployment",
     "highlight": "Labour market subsidy may be paid to jobseekers."},
    {"topic": "alternative_permits", "title": "Migri permits", "url": "https://migri.fi/en/permits",
     "highlight": "You may apply for a residence permit to look for work after graduating."},
]

GEMINI_PLAN = {
    "this_week": [
        {"title": "Register", "why": "It keeps benefits open.", "how": ["Open Työmarkkinatori", "Register"], "source_ids": ["S1"]},
        {"title": "Apply for support", "why": "Income matters.", "how": ["Apply on Kela"], "source_ids": ["S2"]},
        {"title": "Check permits", "why": "Know your options.", "how": ["Read Migri"], "source_ids": ["S3", "S99"]},
    ],
    "timeline": [{"week": "Week 1", "steps": ["Register"], "source_ids": ["S1"]},
                 {"week": "Week 2", "steps": ["Unsourced step"], "source_ids": []}],
    "plan_b": [{"option": "Job-seeker permit", "why": "If you graduated here.", "latest_start_date": "2027-01-15",
                "source_ids": ["S3"]}],
}


@pytest.fixture
def verified(monkeypatch):
    monkeypatch.setattr(main, "get_live_check", lambda rule_id: {"rule_id": rule_id, **VERIFIED})


@pytest.fixture
def live_services(monkeypatch):
    """Exa and Gemini return good data."""
    monkeypatch.setattr(main.gemini, "available", lambda: True)
    monkeypatch.setattr(main.exa_search, "search_plan_sources", lambda topics: [dict(s) for s in EXA_SOURCES])
    monkeypatch.setattr(main.gemini, "write_plan", lambda *a: GEMINI_PLAN)


# ---------- /intake ----------

def test_intake_uses_gemini_and_asks_only_whats_missing(monkeypatch):
    monkeypatch.setattr(main.gemini, "extract_facts", lambda text, today: {
        "job_was_in_finland": True, "citizenship_group": "other", "citizenship_country": "India",
        "permit_type": "work_based", "years_on_work_permit": None, "job_end_date": "2026-11-13",
        "city": "Helsinki", "field": "nurse", "studied_in_finland": None, "family_in_finland": None})
    body = client.post("/intake", json={"text": "I'm a nurse from India, lost my job yesterday"}).json()
    assert body["mock"] is False
    assert body["facts"]["citizenship_country"] == "India"
    assert [q["id"] for q in body["missing_questions"]] == ["years_on_work_permit"]
    assert {"value": "not_sure", "label": "Not sure"} in body["missing_questions"][0]["options"]


def test_intake_answers_override_extracted_facts(monkeypatch):
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {"permit_type": "student"})
    body = client.post("/intake", json={"text": "lost my job", "answers": {
        "permit_type": "work_based", "citizenship_group": "other", "years_on_work_permit": "over_2",
        "job_end_date": "2026-11-01"}}).json()
    assert body["facts"]["permit_type"] == "work_based"
    assert body["missing_questions"] == []


def test_intake_asks_at_most_three_questions_with_options(monkeypatch):
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {})
    qs = client.post("/intake", json={"text": "I lost my job"}).json()["missing_questions"]
    assert [q["id"] for q in qs] == ["citizenship_group", "permit_type", "job_end_date"]
    assert all(q["options"] and all({"value", "label"} <= o.keys() for o in q["options"]) for q in qs)
    text = " ".join(q["question"].lower() for q in qs)
    assert "number" not in text and "passport" not in text


def test_intake_eu_citizen_needs_no_questions(monkeypatch):
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {"citizenship_group": "eu_eea"})
    assert client.post("/intake", json={"text": "I'm from Germany"}).json()["missing_questions"] == []


def test_intake_job_outside_finland_is_out_of_scope(monkeypatch):
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {"job_was_in_finland": False})
    body = client.post("/intake", json={"text": "I lost my job in Sweden"}).json()
    assert body["out_of_scope"] is True
    assert body["message"] and body["link"].startswith("https://www.infofinland.fi/")
    assert "facts" not in body


def test_intake_falls_back_to_keyword_mock_when_gemini_fails(monkeypatch):
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: None)
    body = client.post("/intake", json={"text": "I lost my job yesterday, I'm on a work permit from India"}).json()
    assert body["mock"] is True
    assert body["facts"]["citizenship_group"] == "other"
    assert body["facts"]["permit_type"] == "work_based"


# ---------- /plan ----------

def test_plan_with_exa_and_gemini(verified, live_services):
    body = client.post("/plan", json={"facts": WORK_FACTS}).json()
    assert body["mock"] is False
    d = body["deadline"]
    assert d["status"] == "ok" and d["verified"] is True
    assert d["deadline_date"] == "2027-02-01" and d["months"] == 3
    assert len(body["this_week"]) == 3
    for action in body["this_week"]:
        assert action["why"] and action["how"] and action["sources"]
        assert all(s["highlight"] for s in action["sources"])
    # Unknown source ids are dropped, and so are timeline steps without any source.
    assert [s["url"] for s in body["this_week"][2]["sources"]] == ["https://migri.fi/en/permits"]
    assert [w["week"] for w in body["timeline"]] == ["Week 1"]
    assert body["plan_b"][0]["latest_start_date"] == "2027-01-15"
    assert "not legal advice" in body["disclaimer"]


def test_plan_hides_date_and_warns_when_rule_not_verified(monkeypatch, live_services):
    monkeypatch.setattr(main, "get_live_check", lambda rule_id: {"rule_id": rule_id, **ERROR})
    d = client.post("/plan", json={"facts": WORK_FACTS}).json()["deadline"]
    assert d["deadline_date"] is None and d["days_left"] is None
    assert d["verified"] is False
    assert d["warning"] == "This rule may have changed. Please check Migri."
    assert d["warning_link"].startswith("https://migri.fi/")
    assert "2027" not in d["explanation"]


def test_plan_not_sure_years_shows_both_possible_dates(verified, live_services):
    facts = {**WORK_FACTS, "years_on_work_permit": "not_sure"}
    d = client.post("/plan", json={"facts": facts}).json()["deadline"]
    assert d["status"] == "unclear"
    assert [(p["months"], p["deadline_date"]) for p in d["possible_dates"]] == [(3, "2027-02-01"), (6, "2027-05-01")]


def test_plan_falls_back_when_an_action_has_no_real_source(verified, monkeypatch, live_services):
    bad = {**GEMINI_PLAN, "this_week": [*GEMINI_PLAN["this_week"][:2], {**GEMINI_PLAN["this_week"][2], "source_ids": ["S99"]}]}
    monkeypatch.setattr(main.gemini, "write_plan", lambda *a: bad)
    body = client.post("/plan", json={"facts": WORK_FACTS}).json()
    assert body["mock"] is True
    assert len(body["this_week"]) == 3 and all(a["sources"] for a in body["this_week"])


def test_plan_without_exa_uses_mock_plan(verified, monkeypatch):
    monkeypatch.setattr(main.gemini, "available", lambda: True)
    monkeypatch.setattr(main.exa_search, "search_plan_sources", lambda topics: None)
    monkeypatch.setattr(main.gemini, "write_plan", lambda *a: pytest.fail("Gemini called without sources"))
    body = client.post("/plan", json={"facts": WORK_FACTS}).json()
    assert body["mock"] is True
    assert len(body["this_week"]) == 3 and body["timeline"] and body["plan_b"]
    assert all(s["url"] for part in ("this_week", "timeline", "plan_b") for item in body[part] for s in item["sources"])


def test_plan_skips_exa_when_gemini_unavailable(verified, monkeypatch):
    monkeypatch.setattr(main.gemini, "available", lambda: False)
    monkeypatch.setattr(main.exa_search, "search_plan_sources", lambda topics: pytest.fail("Exa called without Gemini"))
    assert client.post("/plan", json={"facts": WORK_FACTS}).json()["mock"] is True


def test_plan_needs_info_without_permit(verified):
    d = client.post("/plan", json={"facts": {}}).json()["deadline"]
    assert d["status"] == "needs_info"
    assert d["missing"] == ["citizenship_group", "permit_type", "job_end_date"]


# ---------- other endpoints ----------

def test_rules_endpoint_includes_country_config(monkeypatch):
    monkeypatch.setattr(main, "check_all_rules", lambda: [{"id": "r", "live_check": {"status": "error"}}])
    body = client.get("/rules").json()
    assert body["rules"][0]["live_check"]["status"] == "error"
    assert "migri.fi" in body["trusted_domains"]


def test_referrals_have_drafted_messages_and_sources():
    body = client.post("/referrals", json={"facts": {"field": "data analyst", "city": "Espoo"}}).json()
    assert body["referrals"]
    assert all(r["message"] and r["source"]["url"] for r in body["referrals"])


def test_use_mock_returns_saved_examples_without_external_calls(monkeypatch):
    monkeypatch.setattr(main.config, "USE_MOCK", True)
    monkeypatch.setattr(main, "get_live_check", lambda rule_id: {"rule_id": rule_id, **ERROR})

    def unexpected(*_args, **_kwargs):
        raise AssertionError("External service called while USE_MOCK is enabled")

    for name in ("extract_facts", "write_plan", "draft_messages"):
        monkeypatch.setattr(main.gemini, name, unexpected)
    for name in ("search_plan_sources", "search_referrals"):
        monkeypatch.setattr(main.exa_search, name, unexpected)

    intake_body = client.post("/intake", json={"text": "ignored in saved example mode"}).json()
    assert intake_body["mock"] is True
    assert intake_body["facts"]["field"] == "software developer"

    plan_body = client.post("/plan", json={"facts": intake_body["facts"]}).json()
    assert plan_body["mock"] is True
    assert len(plan_body["this_week"]) == 3
    referrals_body = client.post("/referrals", json={"facts": intake_body["facts"]}).json()
    assert referrals_body["mock"] is True
    assert len(referrals_body["referrals"]) == 2
