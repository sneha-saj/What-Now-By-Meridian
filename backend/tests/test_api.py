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
              "job_end_date": "2026-11-01", "field": "nurse", "city": "Espoo", "unemployment_fund": "no"}

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


def test_use_mock_returns_saved_examples_without_external_calls(monkeypatch):
    monkeypatch.setattr(main.config, "USE_MOCK", True)
    monkeypatch.setattr(main, "get_live_check", lambda rule_id: {"rule_id": rule_id, **ERROR})

    def unexpected(*_args, **_kwargs):
        raise AssertionError("External service called while USE_MOCK is enabled")

    for name in ("extract_facts", "write_plan", "write_opportunities"):
        monkeypatch.setattr(main.gemini, name, unexpected)
    for name in ("search_plan_sources", "search_opportunities"):
        monkeypatch.setattr(main.exa_search, name, unexpected)

    intake_body = client.post("/intake", json={"text": "ignored in saved example mode"}).json()
    assert intake_body["mock"] is True
    assert intake_body["facts"]["field"] == "restaurant worker"

    plan_body = client.post("/plan", json={"facts": intake_body["facts"]}).json()
    assert plan_body["mock"] is True
    assert plan_body["deadline"]["deadline_date"] == "2027-02-01"
    assert len(plan_body["this_week"]) == 3
    opp_body = client.post("/opportunities", json={"facts": intake_body["facts"]}).json()
    assert set(opp_body) == {"perks_and_support", "counts", "mock", "demo"}
    assert opp_body["mock"] is True and opp_body["perks_and_support"]["certificate"]
    assert client.get("/rules").json()["trusted_domains"]


@pytest.mark.parametrize("name,model", [
    ("intake", "IntakeResponse"), ("intake_questions", "IntakeResponse"), ("intake_out_of_scope", "IntakeResponse"),
    ("plan", "PlanResponse"), ("chat", "ChatResponse"),
    ("opportunities", "OpportunitiesResponse")])
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
    assert {"/intake", "/plan", "/rules", "/opportunities"} <= spec["paths"].keys()
    assert "/referrals" not in spec["paths"]
    assert "intake" in spec["paths"]["/intake"]["post"]["requestBody"]["content"]["application/json"]["examples"]
    assert client.get("/docs").status_code == 200


# ---------- /chat ----------

def _msg(text):
    return [{"role": "user", "text": text}]


def test_chat_asks_one_question_at_a_time_and_tracks_guesses(monkeypatch):
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {"lost_job": True, "citizenship_group": "other", "city": "Helsinki"})
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
    body = client.post("/chat", json={"messages": msgs, "facts": {"lost_job": True, "citizenship_group": "other", "permit_type": "permanent", "city": "Espoo", "field": "", "unemployment_fund": "not_sure"}}).json()
    assert body["step"] == "deadline"


def test_chat_moves_through_the_steps(verified, live_services):
    session = {"messages": [], "facts": WORK_FACTS}
    d = client.post("/chat", json=session).json()
    assert d["step"] == "deadline" and d["deadline"]["deadline_date"] == "2027-02-01"
    assert d["quick_replies"] == [{"value": "next", "label": "Show me this week"}]
    assert "plan" not in d and "referrals" not in d

    w = client.post("/chat", json={**session, "step": "deadline", "action": "next"}).json()
    assert w["step"] == "this_week" and len(w["plan"]["this_week"]) == 3
    assert w["quick_replies"] == [] and "referrals" not in w  # this week is the last step

    # Staying on the last step doesn't overflow.
    again = client.post("/chat", json={**session, "step": "this_week", "action": "next"}).json()
    assert again["step"] == "this_week"


def test_chat_goes_back_to_questions_if_an_edit_makes_a_fact_unknown(verified):
    body = client.post("/chat", json={"facts": WORK_FACTS, "step": "this_week",
                                      "edited_facts": {"permit_type": None}}).json()
    assert body["step"] == "about_you" and body["question"]["id"] == "permit_type"


def test_chat_out_of_scope(monkeypatch):
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {"job_was_in_finland": False})
    body = client.post("/chat", json={"messages": _msg("I lost my job in Norway")}).json()
    assert body["out_of_scope"] is True and body["link"]


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
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {"lost_job": True, "citizenship_group": "other", "city": "Helsinki"})
    with client.stream("POST", "/chat/stream", json={"messages": _msg("I lost my job in Helsinki")}) as r:
        events = [json.loads(line[6:]) for line in r.iter_lines() if line.startswith("data: ")]
    texts = [e["text"] for e in events if e["type"] == "app"]
    assert texts[0] == "Picked out from your message: whether you lost your job, citizenship, city"
    assert texts[1].startswith("Asking about permit type (still needed to work out how long you can stay: permit type")

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


def test_question_order_deadline_facts_then_personal_questions():
    from models import Facts
    from questions import next_field
    f = Facts()
    order = []
    answers = {"lost_job": True, "citizenship_group": "other", "permit_type": "work_based", "years_on_work_permit": "under_2",
               "job_end_date": "2026-11-01", "city": "Helsinki", "field": "", "unemployment_fund": "no"}
    while (field := next_field(f)) is not None:
        order.append(field)
        f = f.model_copy(update={field: answers[field]})
    # Without Gemini's picks: the default personal questions, after the deadline facts.
    assert order == ["lost_job", "citizenship_group", "permit_type", "years_on_work_permit", "job_end_date",
                     "city", "field", "unemployment_fund"]


def test_gemini_picks_which_personal_questions_to_ask(verified, monkeypatch):
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {
        "lost_job": True, "citizenship_group": "other", "permit_type": "work_based", "years_on_work_permit": 3,
        "job_end_date": "2026-10-31", "city": "Espoo", "field": "software developer",
        "useful_questions": ["registered_jobseeker", "city", "made_up", "studied_in_finland", "family_in_finland"]})
    first = client.post("/chat", json={"messages": _msg("I'm from Brazil, software developer in Espoo, 3 years...")}).json()
    assert first["facts"]["to_ask"] == ["registered_jobseeker", "city", "studied_in_finland"]  # only our ids, max 3
    assert first["question"]["id"] == "registered_jobseeker"  # city is already known, so it's skipped

    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: pytest.fail("taps don't call Gemini"))
    second = client.post("/chat", json={"facts": first["facts"], "answers": {"registered_jobseeker": "no"}}).json()
    assert second["question"]["id"] == "studied_in_finland"
    done = client.post("/chat", json={"facts": second["facts"], "answers": {"studied_in_finland": "false"}}).json()
    assert "question" not in done and done["step"] == "deadline"
    assert done["deadline"]["months"] == 6 and done["deadline"]["deadline_date"] == "2027-04-30"


def test_personal_questions_can_be_skipped_and_are_not_asked_again(verified, live_services):
    facts = {k: v for k, v in WORK_FACTS.items() if k != "city"}
    q = client.post("/chat", json={"facts": facts}).json()
    assert q["question"]["id"] == "city" and {"value": "", "label": "Skip"} in q["question"]["options"]
    done = client.post("/chat", json={"facts": facts, "answers": {"city": ""}}).json()
    assert "question" not in done and done["step"] == "deadline"


def test_bad_gemini_values_are_dropped_not_crashing(monkeypatch):
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {
        "lost_job": True, "unemployment_fund": "maybe", "registered_jobseeker": "sort of", "useful_questions": None})
    body = client.post("/chat", json={"messages": _msg("I was laid off")}).json()
    assert "unemployment_fund" not in body["facts"] and body["question"]["id"] == "citizenship_group"


def test_steps_search_follows_fund_and_registration():
    from services import exa_search
    plain = dict(exa_search.plan_topics("cook", [], "Helsinki"))
    tailored = dict(exa_search.plan_topics("cook", [], "Helsinki", fund="yes", registered="yes"))
    assert "Kela" in plain["unemployment_benefits"] and "unemployment fund" in tailored["unemployment_benefits"]
    assert plain["register_jobseeker"].startswith("register") and tailored["register_jobseeker"].startswith("after registering")


@pytest.mark.parametrize("phrase", ["laid off", "fired", "let go", "dismissed", "terminated", "made redundant", "position eliminated", "contract ended"])
def test_job_loss_wording_is_recognized_by_fallback(phrase):
    from services.mocks import extract_facts

    assert extract_facts(f"I was {phrase} last week", main.date(2026, 11, 14))["lost_job"] is True


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
    body = client.post("/ask", json={"question": "How do I write a CV for jobs in Finland?"}).json()
    assert body["mock"] is True and body["suggested_roadmap_step"] == "week2"


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



def test_message_not_about_job_loss_asks_first_then_redirects_kindly(monkeypatch):
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {"lost_job": None})
    q = client.post("/chat", json={"messages": _msg("I broke up")}).json()
    assert q["question"]["id"] == "lost_job" and q["step"] == "about_you"
    assert {"value": "false", "label": "No, it's something else"} in q["question"]["options"]

    no = client.post("/chat", json={"facts": q["facts"], "answers": {"lost_job": "false"}}).json()
    assert no["out_of_scope"] is True and "relationship" in no["reply"] and no["links"]

    yes = client.post("/chat", json={"facts": q["facts"], "answers": {"lost_job": "true"}}).json()
    assert yes["question"]["id"] == "citizenship_group"


def test_job_loss_in_the_message_skips_the_check(monkeypatch):
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: None)  # keyword fallback
    body = client.post("/chat", json={"messages": _msg("I was laid off last week, I'm on a work permit")}).json()
    assert body["facts"]["lost_job"] is True and body["question"]["id"] != "lost_job"



def test_ask_picks_up_new_facts_so_the_roadmap_can_rebuild(monkeypatch):
    monkeypatch.setattr(main.gemini, "available", lambda: True)
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {"years_on_work_permit": 3, "lost_job": True, "city": "Espoo"})
    monkeypatch.setattr(main.exa_search, "ask", lambda *a: pytest.fail("nothing to look up in a correction"))
    body = client.post("/ask", json={"question": "Actually I have been here 3 years", "facts": WORK_FACTS}).json()
    assert body["facts_update"] == {"years_on_work_permit": 3.0} or body["facts_update"] == {"years_on_work_permit": 3}
    assert "updated your situation" in body["answer"]


def test_ask_question_with_no_new_facts_has_empty_update(monkeypatch):
    monkeypatch.setattr(main.gemini, "available", lambda: True)
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {"city": "Espoo"})
    monkeypatch.setattr(main.exa_search, "ask", lambda *a: {"answer": "Yes.", "citations": [
        {"title": "Kela", "url": "https://www.kela.fi/x", "published": None}]})
    body = client.post("/ask", json={"question": "Can I get Kela benefit?", "facts": WORK_FACTS}).json()
    assert body["facts_update"] == {} and body["sources"]


@pytest.mark.parametrize("use_mock", [True, False])
def test_off_topic_first_message_gets_a_polite_no_not_a_roadmap(monkeypatch, use_mock):
    monkeypatch.setattr(main.config, "USE_MOCK", use_mock)
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {"lost_job": False})
    body = client.post("/chat", json={"messages": _msg("What's the best pizza place in Helsinki?")}).json()
    assert body["out_of_scope"] is True and "job loss in Finland" in body["reply"]
    assert "relationship" not in body["reply"] and "deadline" not in body and body["facts"] == {}


@pytest.mark.parametrize("extracted", [{}, {"lost_job": None}, {"city": "Helsinki"}])
def test_off_topic_first_message_is_polite_live_even_if_gemini_is_unsure(monkeypatch, extracted):
    monkeypatch.setattr(main.config, "USE_MOCK", False)
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: extracted)
    body = client.post("/chat", json={"messages": _msg("I need food")}).json()
    assert body["out_of_scope"] is True and "job loss in Finland" in body["reply"] and body["facts"] == {}


def test_off_topic_words_but_gemini_reads_a_job_loss_carries_on(monkeypatch):
    monkeypatch.setattr(main.config, "USE_MOCK", False)
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {"lost_job": True})
    body = client.post("/chat", json={"messages": _msg("I got sacked and I need food")}).json()
    assert body.get("out_of_scope") is not True and body["question"]["id"] == "citizenship_group"


@pytest.mark.parametrize("text", ["My company closed down", "Probation ended last week", "I was made redundant"])
def test_job_loss_wording_is_not_mistaken_for_off_topic(monkeypatch, text):
    monkeypatch.setattr(main.config, "USE_MOCK", True)
    body = client.post("/chat", json={"messages": _msg(text)}).json()
    assert body.get("out_of_scope") is not True


# ---------- /steps/update ----------

def _plan(tag: str, n_weeks: int = 2, n_b: int = 1):
    from models import Action, PlanBOption, PlanResponse, Source, TimelineStep
    src = [Source(title="Kela", url="https://www.kela.fi/x")]
    return PlanResponse(
        deadline={"status": "ok", "explanation": "x", "source": {"title": "Migri", "url": "https://migri.fi"}},
        this_week=[Action(title=f"{tag} a{i}", why="w", how=["h"], sources=src) for i in range(1, 4)],
        timeline=[TimelineStep(week="Week 1", steps=[f"{tag} w1"], sources=src)]
        + [TimelineStep(week=f"Week {2 ** (i + 1)}", steps=[f"{tag} w{i}"], sources=src) for i in range(n_weeks)],
        plan_b=[PlanBOption(id=f"b{i}", option=f"{tag} b{i}", why="y", sources=src) for i in range(n_b)],
        disclaimer="d", mock=False)


@pytest.mark.parametrize("k,expect_actions,expect_weeks,expect_b", [
    (1, ["new a1", "new a2", "new a3"], ["new w0", "new w1"], ["new b0"]),
    (2, ["old a1", "new a2", "new a3"], ["new w0", "new w1"], ["new b0"]),
    (5, ["old a1", "old a2", "old a3"], ["old w0", "new w1"], ["new b0"]),   # steps 4-5 are the later weeks
    (6, ["old a1", "old a2", "old a3"], ["old w0", "old w1"], ["new b0"]),   # step 6 is Plan B
])
def test_steps_before_the_edited_one_stay_the_rest_are_rewritten(k, expect_actions, expect_weeks, expect_b):
    out = main.merge_from_step(_plan("old"), _plan("new"), k)
    assert [a.title for a in out.this_week] == expect_actions
    assert [w.steps[0] for w in main._later_weeks(out)] == expect_weeks
    assert [p.option for p in out.plan_b] == expect_b


def test_step_update_picks_up_facts_searches_what_you_wrote_and_keeps_earlier_steps(verified, monkeypatch):
    seen = {}
    monkeypatch.setattr(main.gemini, "available", lambda: True)
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: pytest.fail("no Gemini call just to read the note"))
    monkeypatch.setattr(main.exa_search, "search_plan_sources",
                        lambda topics: seen.setdefault("topics", dict(topics)) and [dict(s) for s in EXA_SOURCES])
    monkeypatch.setattr(main.gemini, "write_plan", lambda *a: seen.setdefault("note", a[-1]) and GEMINI_PLAN)
    old = _plan("old").model_dump(mode="json")
    body = client.post("/steps/update", json={"facts": WORK_FACTS, "plan": old, "step": 2,
                                              "note": "I already registered as a jobseeker last week"}).json()
    assert body["facts_update"] == {"registered_jobseeker": "yes"} and body["facts"]["registered_jobseeker"] == "yes"
    assert "registered" in seen["topics"]["your_update"] and seen["topics"]["register_jobseeker"].startswith("after registering")
    assert "already registered" in seen["note"]
    titles = [a["title"] for a in body["plan"]["this_week"]]
    assert titles == ["old a1", "Apply for support", "Check permits"]  # step 1 kept, 2-3 rewritten
    assert body["updated_from"] == 2 and body["mock"] is False


def test_step_update_without_live_services_keeps_the_steps_and_says_so(verified, monkeypatch):
    monkeypatch.setattr(main.gemini, "available", lambda: False)
    old = _plan("old").model_dump(mode="json")
    body = client.post("/steps/update", json={"facts": WORK_FACTS, "plan": old, "step": 1, "note": "I have a job offer"}).json()
    assert body["mock"] is True and body["message"] and body["plan"]["this_week"][0]["title"] == "old a1"


def test_step_update_in_mock_mode_makes_no_external_calls(monkeypatch):
    monkeypatch.setattr(main.config, "USE_MOCK", True)
    monkeypatch.setattr(main.exa_search, "search_plan_sources", lambda *a: pytest.fail("Exa called in mock mode"))
    monkeypatch.setattr(main.gemini, "write_plan", lambda *a: pytest.fail("Gemini called in mock mode"))
    old = _plan("old").model_dump(mode="json")
    body = client.post("/steps/update", json={"facts": WORK_FACTS, "plan": old, "step": 1,
                                              "note": "I'm in an unemployment fund"}).json()
    assert body["mock"] is True and body["facts"]["unemployment_fund"] == "yes"


def test_demo_mode_is_flagged_so_the_app_can_say_it_is_a_sample_person(monkeypatch):
    monkeypatch.setattr(main.config, "USE_MOCK", True)
    body = client.post("/chat", json={"messages": _msg("I was laid off")}).json()
    assert body["demo"] is True and body["facts"]["city"] == "Helsinki"  # the saved sample person
    assert client.post("/opportunities", json={"facts": {}}).json()["demo"] is True
    monkeypatch.setattr(main.config, "USE_MOCK", False)
    monkeypatch.setattr(main.gemini, "extract_facts", lambda *a: {"lost_job": True})
    assert client.post("/chat", json={"messages": _msg("I was laid off")}).json().get("demo") in (None, False)
