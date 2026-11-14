"""What Now? by Meridian — agent backend."""

from datetime import date

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from models import (Deadline, Facts, IntakeRequest, IntakeResponse, PlanRequest, PlanResponse,
                    Referral, ReferralRequest, ReferralResponse, Source, Step)
from questions import questions_for
from rules import compute_deadline
from countries.finland import TRUSTED_DOMAINS
from live_check import check_all_rules, get_live_check
from services import exa_search, gemini, mocks

app = FastAPI(title="What Now? by Meridian")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS,
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"ok": True, "gemini": bool(config.gemini_key()), "exa": bool(config.exa_key()),
            "oxylabs": config.ENABLE_OXYLABS, "elevenlabs": config.ENABLE_ELEVENLABS}


@app.get("/rules")
def rules():
    return {"rules": check_all_rules(), "trusted_domains": TRUSTED_DOMAINS}


@app.post("/intake", response_model=IntakeResponse)
def intake(req: IntakeRequest):
    today = date.today()
    raw = gemini.extract_facts(req.text, today.isoformat())
    mock = raw is None
    if mock:
        raw = mocks.extract_facts(req.text, today)
    facts = Facts.model_validate({k: v for k, v in raw.items() if k in Facts.model_fields})
    return IntakeResponse(facts=facts, questions=questions_for(facts, today), mock=mock)


@app.post("/plan", response_model=PlanResponse)
def plan(req: PlanRequest):
    f = req.facts
    d = compute_deadline(f.to_rules())
    live = get_live_check(d.rule_id)
    warning = None
    if live and live["status"] != "verified":
        warning = "This rule may have changed. Please check Migri."
        d.deadline = None
        d.days_left = None
    deadline = Deadline(status=d.status, reason=d.reason, deadline=d.deadline, months=d.months,
                        days_left=d.days_left, missing=d.missing, source=Source(**d.source),
                        live_check=live, warning=warning)

    permit = (f.permit_type or "work").replace("_", " ")
    queries = [
        f"lost my job on a {permit} residence permit Finland what happens to my permit",
        "register as unemployed jobseeker Finland foreigner",
        "Kela unemployment benefit for immigrants",
    ]
    steps = None
    sources = exa_search.search_official(queries)
    if sources:
        for i, s in enumerate(sources):
            s["id"] = f"S{i + 1}"
        by_id = {s["id"]: s for s in sources}
        raw_steps = gemini.write_steps(f.model_dump(mode="json"), deadline.model_dump(mode="json"), sources)
        if raw_steps:
            steps = []
            for st in raw_steps[:3]:
                cited = [Source(title=by_id[i]["title"], url=by_id[i]["url"])
                         for i in st.get("source_ids", []) if i in by_id]
                if cited:  # drop any step without a real source
                    steps.append(Step(title=st["title"], detail=st["detail"], sources=cited))
            steps = steps or None

    mock = steps is None
    if mock:
        steps = [Step(**s) for s in mocks.steps(d.status)]
    return PlanResponse(deadline=deadline, this_week=steps, mock=mock)


@app.post("/referrals", response_model=ReferralResponse)
def referrals(req: ReferralRequest):
    occupation = req.facts.occupation or "professional"
    city = req.facts.city or "Helsinki"

    contacts = exa_search.search_referrals(occupation, city)
    mock = contacts is None
    if mock:
        contacts = mocks.referrals(occupation, city)

    messages = gemini.draft_messages(req.facts.model_dump(mode="json"), contacts)
    if messages is None:
        messages = [mocks.message(c, occupation) for c in contacts]

    return ReferralResponse(
        referrals=[Referral(message=m, **c) for c, m in zip(contacts, messages)], mock=mock
    )
