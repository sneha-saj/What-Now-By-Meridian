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
    "plan_b": [{"candidate_id": "new_employer", "why": "Apply with a job offer.", "source_ids": ["S3"]},
               {"candidate_id": "made_up_option", "why": "Not in our list.", "source_ids": ["S3"]},
               {"candidate_id": "entrepreneur", "why": "No source given.", "source_ids": []}],
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
    # Plan B: only listed candidates with a real source; the date comes from the rules engine, not Gemini.
    assert [p["id"] for p in body["plan_b"]] == ["new_employer"]
    assert body["plan_b"][0]["who_it_fits"] and body["plan_b"][0]["latest_start_date"] == "2027-02-01"
    assert "not legal advice" in body["disclaimer"]


def test_plan_keeps_date_and_warns_when_rule_text_differs(monkeypatch, live_services):
    monkeypatch.setattr(main, "get_live_check", lambda rule_id: {"rule_id": rule_id, **ERROR, "status": "mismatch"})
    d = client.post("/plan", json={"facts": WORK_FACTS}).json()["deadline"]
    assert d["deadline_date"] == "2027-02-01"
    assert d["verified"] is False and d["check_status"] == "mismatch"
    assert d["warning"] == "This rule may have changed. Please check Migri."
    assert d["warning_link"].startswith("https://migri.fi/")


def test_plan_check_error_is_neutral_not_alarming(monkeypatch, live_services):
    monkeypatch.setattr(main, "get_live_check", lambda rule_id: {"rule_id": rule_id, **ERROR})
    d = client.post("/plan", json={"facts": WORK_FACTS}).json()["deadline"]
    assert d["deadline_date"] == "2027-02-01" and d["check_status"] == "error"
    assert d["warning"].startswith("Couldn't check") and "may have changed" not in d["warning"]


def test_plan_b_when_no_permit_risk(verified):
    body = client.post("/plan", json={"facts": {"citizenship_group": "eu_eea"}}).json()
    assert body["plan_b"] == [] and "doesn't depend on this job" in body["plan_b_note"]


def test_mock_plan_b_is_specific_to_facts(verified):
    facts = {**WORK_FACTS, "studied_in_finland": True, "family_in_finland": True}
    ids = [p["id"] for p in client.post("/plan", json={"facts": facts}).json()["plan_b"]]
    assert ids == ["new_employer", "job_seeker_graduate", "family", "entrepreneur"]


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


COMPANIES = [{"name": f"Restaurant {i} Oy", "url": f"https://r{i}.fi", "highlight": f"Hiring cooks {i}",
              "hiring_evidence": "https://r1.fi/careers" if i == 1 else None} for i in range(1, 5)]
PEOPLE = [{"name": "Aino Virtanen", "role": "Head Chef", "company": "Restaurant 1 Oy",
           "profile_url": "https://linkedin.com/in/aino", "highlight": "Leads a team of 12 cooks"}]
GROUPS = [{"name": "Helsinki Chefs Meetup", "url": "https://meetup.com/x", "kind": "professional_group", "highlight": "Next meetup 2026-11-20"},
          {"name": "PAM union", "url": "https://pam.fi", "kind": "union", "highlight": "Career coaching for members"}]


@pytest.fixture
def referral_exa(monkeypatch):
    calls = {}
    monkeypatch.setattr(main.exa_search, "search_companies", lambda field, city: calls.setdefault("companies", (field, city)) and [dict(c) for c in COMPANIES])
    monkeypatch.setattr(main.exa_search, "search_people", lambda companies, field, city: [dict(p) for p in PEOPLE])
    monkeypatch.setattr(main.exa_search, "search_communities", lambda field, city, today: [dict(g) for g in GROUPS])
    return calls


def test_referrals_with_exa_and_gemini(monkeypatch, referral_exa):
    monkeypatch.setattr(main.gemini, "write_referral_notes", lambda *a: {
        "companies": [{"id": "C1", "why_relevant": "Hires cooks in Helsinki."}],
        "communities": [{"id": "G1", "type": "event", "date_if_event": "2026-11-20"},
                        {"id": "G2", "type": "union", "date_if_event": "2026-11-21"}],
        "drafts": [{"id": "P1", "why_this_person": "Leads the kitchen.",
                    "message": "Hi Aino, I read that you lead a team of 12 cooks. Could we talk? [Your name]"}]})
    body = client.post("/referrals", json={"facts": {"field": "restaurant worker", "city": "Helsinki"}}).json()
    assert referral_exa["companies"] == ("restaurant worker", "Helsinki")
    assert body["mock"] is False
    assert body["companies"][0]["why_relevant"] == "Hires cooks in Helsinki."
    assert body["companies"][0]["hiring_now"] is True and body["companies"][0]["hiring_evidence"] == "https://r1.fi/careers"
    assert body["companies"][1]["hiring_now"] is False
    assert body["companies"][1]["why_relevant"] == "Came up in a search for restaurant worker employers near Helsinki."  # never raw page text
    assert body["contacts"][0] == {"name": "Aino Virtanen", "role": "Head Chef", "company": "Restaurant 1 Oy",
                                   "why_this_person": "Leads the kitchen.", "profile_url": "https://linkedin.com/in/aino"}
    assert "12 cooks" in body["drafts"][0]["message"]
    assert body["communities"][0] == {"name": "Helsinki Chefs Meetup", "type": "event", "date_if_event": "2026-11-20",
                                      "url": "https://meetup.com/x", "published": None}
    assert body["communities"][1]["date_if_event"] is None  # dates only for events


def test_referral_drafts_over_80_words_fall_back_to_template(monkeypatch, referral_exa):
    long = " ".join(["word"] * 81)
    monkeypatch.setattr(main.gemini, "write_referral_notes", lambda *a: {
        "companies": [], "communities": [], "drafts": [{"id": "P1", "why_this_person": "x", "message": long}]})
    msg = client.post("/referrals", json={"facts": {"field": "cook"}}).json()["drafts"][0]["message"]
    assert len(msg.split()) <= 80 and "Restaurant 1 Oy" in msg


def test_referrals_without_gemini_still_return_exa_results(monkeypatch, referral_exa):
    monkeypatch.setattr(main.gemini, "write_referral_notes", lambda *a: None)
    body = client.post("/referrals", json={"facts": {"field": "cook"}}).json()
    assert body["mock"] is True
    assert len(body["companies"]) == 4 and len(body["drafts"]) == 1
    assert sorted(g["type"] for g in body["communities"]) == ["professional_group", "union"]


def test_referrals_without_exa_list_only_real_help_services(monkeypatch):
    monkeypatch.setattr(main.exa_search, "search_companies", lambda *a: None)
    monkeypatch.setattr(main.exa_search, "search_communities", lambda *a: None)
    monkeypatch.setattr(main.gemini, "write_referral_notes", lambda *a: pytest.fail("Gemini called without data"))
    body = client.post("/referrals", json={"facts": {}}).json()
    assert body["mock"] is True
    assert body["companies"] == [] and body["contacts"] == [] and body["drafts"] == []
    assert body["communities"]


def test_use_mock_returns_saved_examples_without_external_calls(monkeypatch):
    monkeypatch.setattr(main.config, "USE_MOCK", True)
    monkeypatch.setattr(main, "get_live_check", lambda rule_id: {"rule_id": rule_id, **ERROR})

    def unexpected(*_args, **_kwargs):
        raise AssertionError("External service called while USE_MOCK is enabled")

    for name in ("extract_facts", "write_plan", "write_referral_notes"):
        monkeypatch.setattr(main.gemini, name, unexpected)
    for name in ("search_plan_sources", "search_companies", "search_people", "search_communities"):
        monkeypatch.setattr(main.exa_search, name, unexpected)

    intake_body = client.post("/intake", json={"text": "ignored in saved example mode"}).json()
    assert intake_body["mock"] is True
    assert intake_body["facts"]["field"] == "restaurant worker"

    plan_body = client.post("/plan", json={"facts": intake_body["facts"]}).json()
    assert plan_body["mock"] is True
    assert plan_body["deadline"]["deadline_date"] == "2027-02-01"
    assert len(plan_body["this_week"]) == 3
    referrals_body = client.post("/referrals", json={"facts": intake_body["facts"]}).json()
    assert referrals_body["mock"] is True and referrals_body["drafts"]
    assert client.get("/rules").json()["trusted_domains"]


@pytest.mark.parametrize("name,model", [
    ("intake", "IntakeResponse"), ("intake_questions", "IntakeResponse"), ("intake_out_of_scope", "IntakeResponse"),
    ("plan", "PlanResponse"), ("referrals", "ReferralResponse"), ("chat", "ChatResponse")])
def test_saved_examples_match_response_models(name, model):
    import models
    from services import mocks
    getattr(models, model).model_validate(mocks.example(name), strict=False)


def test_saved_plan_example_matches_the_rules_engine(monkeypatch):
    """The documented example must agree with what the rules engine computes for the persona."""
    from services import mocks
    monkeypatch.setattr(main, "get_live_check", lambda rule_id: {"rule_id": rule_id, **VERIFIED})
    monkeypatch.setattr(main.gemini, "available", lambda: False)
    saved = mocks.example("plan")["deadline"]
    live = client.post("/plan", json={"facts": mocks.example_facts()}).json()["deadline"]
    for key in ("status", "months", "deadline_date", "rule_id"):
        assert live[key] == saved[key]


def test_openapi_docs_page_works():
    spec = client.get("/openapi.json").json()
    assert {"/intake", "/plan", "/rules", "/referrals"} <= spec["paths"].keys()
    assert "intake" in spec["paths"]["/intake"]["post"]["requestBody"]["content"]["application/json"]["examples"]
    assert client.get("/docs").status_code == 200


# ---------- /chat ----------

def _msg(text):
    return [{"role": "user", "text": text}]


def test_chat_asks_one_question_at_a_time_and_tracks_guesses(monkeypatch):
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {"citizenship_group": "other", "city": "Helsinki"})
    body = client.post("/chat", json={"messages": _msg("I lost my job in Helsinki")}).json()
    assert body["step"] == "about_you"
    assert body["question"]["id"] == "permit_type"
    assert body["reply"].endswith(body["question"]["question"])
    assert body["facts"]["city"] == "Helsinki"
    assert body["confirmed_fields"] == []  # extracted facts are guesses until confirmed


def test_chat_edited_facts_win_over_answers_and_extraction(monkeypatch):
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {"city": "Espoo", "permit_type": "student"})
    body = client.post("/chat", json={
        "messages": _msg("I live in Espoo"), "facts": {"city": "Tampere"},
        "answers": {"permit_type": "work_based"}, "edited_facts": {"city": "Helsinki"}}).json()
    assert body["facts"]["city"] == "Helsinki"
    assert body["facts"]["permit_type"] == "work_based"
    assert set(body["confirmed_fields"]) == {"permit_type", "city"}


def test_chat_does_not_reextract_when_last_message_is_from_assistant(monkeypatch):
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: pytest.fail("re-extracted an old message"))
    msgs = [*_msg("hi"), {"role": "assistant", "text": "Which permit?"}]
    body = client.post("/chat", json={"messages": msgs, "facts": {"citizenship_group": "other", "permit_type": "permanent", "city": "Espoo", "field": ""}}).json()
    assert body["step"] == "deadline"


def test_chat_moves_through_the_steps(verified, live_services, referral_exa, monkeypatch):
    monkeypatch.setattr(main.gemini, "write_referral_notes", lambda *a: None)
    session = {"messages": [], "facts": WORK_FACTS}
    d = client.post("/chat", json=session).json()
    assert d["step"] == "deadline" and d["deadline"]["deadline_date"] == "2027-02-01"
    assert d["quick_replies"] == [{"value": "next", "label": "Show me this week"}]
    assert "plan" not in d and "referrals" not in d

    w = client.post("/chat", json={**session, "step": "deadline", "action": "next"}).json()
    assert w["step"] == "this_week" and len(w["plan"]["this_week"]) == 3

    f = client.post("/chat", json={**session, "step": "this_week", "action": "next"}).json()
    assert f["step"] == "find_your_way_in" and f["referrals"]["companies"]
    assert f["quick_replies"] == []

    # Staying on the last step doesn't overflow.
    again = client.post("/chat", json={**session, "step": "find_your_way_in", "action": "next"}).json()
    assert again["step"] == "find_your_way_in"


def test_chat_goes_back_to_questions_if_an_edit_makes_a_fact_unknown(verified):
    body = client.post("/chat", json={"facts": WORK_FACTS, "step": "this_week",
                                      "edited_facts": {"permit_type": None}}).json()
    assert body["step"] == "about_you" and body["question"]["id"] == "permit_type"


def test_chat_out_of_scope(monkeypatch):
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {"job_was_in_finland": False})
    body = client.post("/chat", json={"messages": _msg("I lost my job in Norway")}).json()
    assert body["out_of_scope"] is True and body["link"]


def test_company_sentences_are_cleaned_to_one_short_line():
    long = "**Great** fit: " + " ".join(["word"] * 30) + ". Second sentence."
    out = main._clean_sentence(long)
    assert "*" not in out and len(out.split()) <= 20 and "Second" not in out
    assert main._clean_name("Rafla Oy | Careers") == "Rafla Oy"


def test_chat_stream_sends_progress_then_result(verified, live_services):
    import json
    with client.stream("POST", "/chat/stream", json={"facts": WORK_FACTS, "step": "deadline", "action": "next"}) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    stages = [e["stage"] for e in events if e["type"] == "progress"]
    assert stages == ["checking_rules", "finding_steps"]
    partials = [e["key"] for e in events if e["type"] == "partial"]
    assert partials == ["deadline", "plan"]  # roadmap nodes can fill in before the final result
    assert events[-1]["type"] == "result" and events[-1]["data"]["step"] == "this_week"
    assert events[-1]["data"]["deadline"]["rule_in_force_since"] == "2025-06-11"


def test_chat_stream_explains_who_did_what(monkeypatch, verified):
    import json
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {"citizenship_group": "other", "city": "Helsinki"})
    with client.stream("POST", "/chat/stream", json={"messages": _msg("I lost my job in Helsinki")}) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    texts = [e["text"] for e in events if e["type"] == "app"]
    assert texts[0] == "Picked out from your message: citizenship, city"
    assert texts[1].startswith("Asking about permit type (still needed for your deadline: permit type")

    with client.stream("POST", "/chat/stream", json={"facts": WORK_FACTS, "step": "deadline"}) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    assert any(e["type"] == "app" and e["who"] == "code" and "plain code: 3 months → 2027-02-01" in e["text"] for e in events)


def test_approximate_job_end_date_marks_deadline_approximate(verified):
    body = client.post("/chat", json={"facts": {**WORK_FACTS, "job_end_date": None}, "step": "deadline",
                                      "answers": {"job_end_date": "about:2026-11-01"}}).json()
    assert body["facts"]["job_end_date"] == "2026-11-01" and body["facts"]["job_end_date_approximate"] is True
    assert body["deadline"]["deadline_is_approximate"] is True and body["deadline"]["deadline_date"] == "2027-02-01"

    exact = client.post("/chat", json={"facts": body["facts"], "step": "deadline",
                                       "edited_facts": {"job_end_date": "2026-11-03"}}).json()
    assert exact["facts"]["job_end_date_approximate"] is False
    assert exact["deadline"]["deadline_is_approximate"] is False


def test_date_question_marks_vague_options():
    from datetime import date
    from questions import questions_for
    from models import Facts
    q = [q for q in questions_for(Facts(citizenship_group="other", permit_type="work_based", years_on_work_permit=1), date(2026, 11, 14))
         if q.id == "job_end_date"][0]
    assert [o.value for o in q.options] == ["2026-11-14", "about:2026-11-07", "about:2026-10-15"]


def test_referrals_are_capped_and_events_outside_30_days_lose_their_date(monkeypatch, referral_exa):
    many = [{"name": f"Co {i}", "url": f"https://c{i}.fi", "highlight": "h", "hiring_evidence": None} for i in range(8)]
    people = [{"name": f"P{i}", "role": "Chef", "company": "Co 0", "profile_url": f"https://p{i}", "highlight": "h"} for i in range(5)]
    monkeypatch.setattr(main.exa_search, "search_companies", lambda *a: [dict(c) for c in many])
    monkeypatch.setattr(main.exa_search, "search_people", lambda *a: [dict(p) for p in people])
    monkeypatch.setattr(main.gemini, "write_referral_notes", lambda *a: {
        "companies": [], "drafts": [],
        "communities": [{"id": "G1", "type": "event", "date_if_event": "2030-01-01"}]})
    body = client.post("/referrals", json={"facts": {"field": "cook"}}).json()
    assert len(body["companies"]) == 5 and len(body["contacts"]) == 3 and len(body["communities"]) <= 3
    far = [g for g in body["communities"] if g["name"] == "Helsinki Chefs Meetup"][0]
    assert far["date_if_event"] is None and far["type"] == "professional_group"


def test_question_order_is_fixed_required_then_optional():
    from models import Facts
    from questions import next_field
    f = Facts()
    order = []
    answers = {"citizenship_group": "other", "permit_type": "work_based", "years_on_work_permit": "under_2",
               "job_end_date": "2026-11-01", "city": "Helsinki", "field": ""}
    while (field := next_field(f)) is not None:
        order.append(field)
        f = f.model_copy(update={field: answers[field]})
    assert order == ["citizenship_group", "permit_type", "years_on_work_permit", "job_end_date", "city", "field"]


def test_skipped_optional_question_is_not_asked_again(verified, live_services):
    facts = {k: v for k, v in WORK_FACTS.items() if k != "city"}
    q = client.post("/chat", json={"facts": facts}).json()
    assert q["question"]["id"] == "city" and {"value": "", "label": "Skip"} in q["question"]["options"]
    done = client.post("/chat", json={"facts": facts, "answers": {"city": ""}}).json()
    assert "question" not in done and done["step"] == "deadline"


# ---------- /ask ----------

def test_ask_off_topic_is_politely_rejected(monkeypatch):
    monkeypatch.setattr(main.exa_search, "ask", lambda *a: pytest.fail("Exa called for an off-topic question"))
    body = client.post("/ask", json={"question": "What's a good pizza recipe?"}).json()
    assert body["off_topic"] is True and "losing a job in Finland" in body["answer"]


def test_ask_rules_question_uses_official_sources_and_suggests_a_step(monkeypatch):
    seen = {}

    def fake_ask(q, official, context):
        seen.update(official=official, context=context)
        return {"answer": "You can apply for labour market subsidy.",
                "citations": [{"title": "Kela", "url": "https://www.kela.fi/labour-market-subsidy", "published": "2026-10-01"}]}

    monkeypatch.setattr(main.exa_search, "ask", fake_ask)
    body = client.post("/ask", json={"question": "Can I get unemployment benefit from Kela?",
                                     "facts": {"permit_type": "work_based", "city": "Helsinki"}}).json()
    assert seen["official"] is True and "Helsinki" in seen["context"]
    assert body["sources"] == [{"title": "Kela", "url": "https://www.kela.fi/labour-market-subsidy", "domain": "kela.fi", "date": "2026-10-01"}]
    assert body["suggested_roadmap_step"] == "week1"


def test_ask_rules_question_without_official_citations_says_so(monkeypatch):
    monkeypatch.setattr(main.exa_search, "ask", lambda *a: {"answer": "Maybe.", "citations": []})
    body = client.post("/ask", json={"question": "Can I extend my residence permit?"}).json()
    assert "couldn't find this on the official sites" in body["answer"] and "suggested_roadmap_step" not in body


def test_ask_without_exa_falls_back(monkeypatch):
    monkeypatch.setattr(main.exa_search, "ask", lambda *a: None)
    body = client.post("/ask", json={"question": "How do I find companies hiring cooks?"}).json()
    assert body["mock"] is True and body["suggested_roadmap_step"] == "wayin"


def test_exa_ask_filters_citations_to_official_domains(monkeypatch):
    from types import SimpleNamespace
    from services import exa_search

    class FakeExa:
        def answer(self, q, **kw):
            assert "migri.fi" in kw["system_prompt"]
            return SimpleNamespace(answer="Yes.", citations=[
                SimpleNamespace(url="https://migri.fi/en/x", title="Migri", published_date="2026-09-01T00:00:00Z"),
                SimpleNamespace(url="https://someblog.com/y", title="Blog", published_date=None)])

    monkeypatch.setattr(exa_search, "_get_client", lambda: FakeExa())
    out = exa_search.ask("Can I extend my permit?", True)
    assert [c["url"] for c in out["citations"]] == ["https://migri.fi/en/x"]
    assert out["citations"][0]["published"] == "2026-09-01"


def test_eu_citizens_get_a_kind_message_and_links_not_a_roadmap(monkeypatch):
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {"citizenship_group": "eu_eea", "citizenship_country": "Germany"})
    monkeypatch.setattr(main, "build_full_plan", lambda *a: pytest.fail("built a roadmap for a citizen"))
    body = client.post("/chat", json={"messages": _msg("I'm German and lost my job in Helsinki")}).json()
    assert body["out_of_scope"] is True and "doesn't depend on your job" in body["reply"]
    assert [l["url"] for l in body["links"]][0] == "https://tyomarkkinatori.fi/en"
    assert "deadline" not in body and "question" not in body
