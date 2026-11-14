"""End-to-end API tests in mock mode (no network, no keys)."""

import os

os.environ["FORCE_MOCKS"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

client = TestClient(app)


def test_intake_asks_missing_questions():
    r = client.post("/intake", json={"text": "I lost my job yesterday, I'm on a work permit from India"})
    body = r.json()
    assert r.status_code == 200
    assert body["mock"] is True
    assert body["facts"]["citizenship"] == "non_eu"
    assert body["facts"]["permit_type"] == "work"
    assert [q["field"] for q in body["questions"]] == ["over_two_years_on_work_permit"]


def test_plan_returns_deadline_and_three_cited_steps(monkeypatch):
    import main
    monkeypatch.setattr(main, "get_live_check", lambda _id: {"status": "verified", "checked_at": "2026-11-14T10:00:00+00:00", "evidence_snippet": "3 months"})
    facts = {"citizenship": "non_eu", "permit_type": "work", "job_end_date": "2026-11-01",
             "over_two_years_on_work_permit": False}
    body = client.post("/plan", json={"facts": facts}).json()
    assert body["deadline"]["status"] == "ok"
    assert body["deadline"]["deadline"] == "2027-02-01"
    assert len(body["this_week"]) == 3
    assert all(step["sources"] for step in body["this_week"])
    assert body["deadline"]["live_check"]["status"] == "verified"


def test_plan_hides_date_when_live_check_is_not_verified(monkeypatch):
    import main
    monkeypatch.setattr(main, "get_live_check", lambda _id: {"status": "error", "checked_at": "2026-11-14T10:00:00+00:00", "evidence_snippet": "Unavailable"})
    facts = {"citizenship": "non_eu", "permit_type": "work", "job_end_date": "2026-11-01", "over_two_years_on_work_permit": False}
    response = client.post("/plan", json={"facts": facts})
    assert response.status_code == 200
    assert response.json()["deadline"]["deadline"] is None
    assert response.json()["deadline"]["warning"] == "This rule may have changed. Please check Migri."


def test_rules_endpoint_includes_country_config(monkeypatch):
    import main
    monkeypatch.setattr(main, "check_all_rules", lambda: [{"id": "r", "live_check": {"status": "error"}}])
    body = client.get("/rules").json()
    assert body["rules"][0]["live_check"]["status"] == "error"
    assert "migri.fi" in body["trusted_domains"]


def test_referrals_have_drafted_messages_and_sources():
    body = client.post("/referrals", json={"facts": {"occupation": "data analyst", "city": "Espoo"}}).json()
    assert body["referrals"]
    assert all(r["message"] and r["source"]["url"] for r in body["referrals"])
