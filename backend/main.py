"""What Now? by Meridian — agent backend."""

from datetime import date

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from models import (Action, Deadline, Facts, IntakeRequest, IntakeResponse, PlanBOption, PlanRequest,
                    PlanResponse, PossibleDate, Referral, ReferralRequest, ReferralResponse, Source,
                    TimelineStep)
from questions import canonical_permit, needed_fields, questions_for
from rules import calculate_deadline
from countries.finland import DEADLINE_RULES, SOURCE_TITLE, SOURCE_URL, TRUSTED_DOMAINS
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


OUT_OF_SCOPE_LINK = "https://www.infofinland.fi/en/work-and-enterprise/unemployment"
DISCLAIMER = ("This is general guidance based on official Finnish sources, not legal advice. "
              "Rules can change: confirm your situation with Migri, Kela or your union.")
WARNING = "This rule may have changed. Please check Migri."


@app.post("/intake", response_model=IntakeResponse, response_model_exclude_none=True)
def intake(req: IntakeRequest):
    today = date.today()
    if config.USE_MOCK:
        raw, mock = mocks.example_facts(), True
    else:
        raw = gemini.extract_facts(req.text, today.isoformat()) if req.text.strip() else {}
        mock = raw is None
        if raw is None:
            raw = mocks.extract_facts(req.text, today)

    if raw.get("job_was_in_finland") is False:
        return IntakeResponse(
            out_of_scope=True, mock=mock, link=OUT_OF_SCOPE_LINK,
            message="What Now? only covers jobs in Finland. If your job was in another country, "
                    "check that country's official services. InfoFinland explains unemployment in Finland.",
        )

    merged = {k: v for k, v in raw.items() if k in Facts.model_fields and v is not None}
    merged.update({k: v for k, v in req.answers.items() if k in Facts.model_fields})  # answers win
    facts = Facts.model_validate(merged)
    return IntakeResponse(facts=facts, missing_questions=questions_for(facts, today), mock=mock)


def build_deadline(f: Facts, today: date) -> Deadline:
    migri = Source(title=SOURCE_TITLE, url=SOURCE_URL)
    missing = needed_fields(f)
    permit = canonical_permit(f)
    if permit is None:
        return Deadline(status="needs_info", explanation="A couple more answers and we can work out your date.",
                        missing=missing, source=migri)

    r = calculate_deadline(permit, f.years(), f.job_end_date)
    possible = [PossibleDate(**p) for p in r.get("possible_dates", [])]
    if not r["applies"]:
        status = "not_applicable"
    elif r["rule_id"] is None:
        status = "unclear"
    elif r["deadline_date"] is None:
        status = "needs_info"
    else:
        status = "ok"

    rule_ids = [r["rule_id"]] if r["rule_id"] else [p.rule_id for p in possible]
    checks = [c for c in (get_live_check(i) for i in rule_ids) if c]
    verified = bool(checks) and all(c["status"] == "verified" for c in checks)

    d = Deadline(
        status=status, explanation=r["explanation"], applies=r["applies"], months=r["months"],
        deadline_date=r["deadline_date"], possible_dates=possible, missing=missing, rule_id=r["rule_id"],
        source=Source(title=SOURCE_TITLE, url=r["source_url"]), verified=verified, live_checks=checks,
    )
    if d.deadline_date:
        d.days_left = (d.deadline_date - today).days
    if not verified and rule_ids:
        # Don't show a date we couldn't confirm against Migri today.
        d.deadline_date = d.days_left = None
        for p in d.possible_dates:
            p.deadline_date = None
        rule = next((x for x in DEADLINE_RULES if x["id"] == r["rule_id"]), None)
        if rule:  # the engine's explanation includes the date, so fall back to the plain rule text
            d.explanation = rule["description"]
        d.warning, d.warning_link = WARNING, r["source_url"]
    return d


def _cite(ids: list[str], by_id: dict) -> list[Source]:
    return [Source(title=by_id[i]["title"], url=by_id[i]["url"], highlight=by_id[i]["highlight"])
            for i in ids if i in by_id]


def build_plan(f: Facts, d: Deadline, today: date) -> dict | None:
    """Exa finds official pages, Gemini writes the plan from them. None if either is unavailable."""
    if not gemini.available():  # no point spending Exa credits if Gemini can't write the plan
        return None
    topics = exa_search.plan_topics(f.field, f.studied_in_finland, f.family_in_finland)
    sources = exa_search.search_plan_sources(topics)
    if not sources:
        return None
    sources = [{**s, "id": f"S{i + 1}"} for i, s in enumerate(sources)]
    by_id = {s["id"]: s for s in sources}
    out = gemini.write_plan(f.model_dump(mode="json"), d.model_dump(mode="json"), sources, today.isoformat())
    if not out:
        return None

    this_week = [Action(title=a["title"], why=a["why"], how=a["how"], sources=_cite(a["source_ids"], by_id))
                 for a in out.get("this_week", [])]
    this_week = [a for a in this_week if a.sources][:3]  # every action must cite a real source
    if len(this_week) < 3:
        return None
    timeline = [TimelineStep(week=w["week"], steps=w["steps"], sources=_cite(w["source_ids"], by_id))
                for w in out.get("timeline", [])]
    plan_b = [PlanBOption(option=p["option"], why=p["why"], latest_start_date=p.get("latest_start_date"),
                          sources=_cite(p["source_ids"], by_id))
              for p in out.get("plan_b", [])]
    return {"this_week": this_week,
            "timeline": [w for w in timeline if w.sources],
            "plan_b": [p for p in plan_b if p.sources]}


@app.post("/plan", response_model=PlanResponse)
def plan(req: PlanRequest):
    today = date.today()
    f = req.facts
    d = build_deadline(f, today)
    built = None if config.USE_MOCK else build_plan(f, d, today)
    mock = built is None
    if built is None:
        built = mocks.plan(d.deadline_date.isoformat() if d.deadline_date else None)
    return PlanResponse(deadline=d, disclaimer=DISCLAIMER, mock=mock, **built)


@app.post("/referrals", response_model=ReferralResponse)
def referrals(req: ReferralRequest):
    occupation = req.facts.field or "professional"
    city = req.facts.city or "Helsinki"

    if config.USE_MOCK:
        contacts, messages = mocks.example_referrals()
        mock = True
    else:
        contacts = exa_search.search_referrals(occupation, city)
        mock = contacts is None
    if contacts is None:
        contacts = mocks.referrals(occupation, city)
        messages = None
    if not config.USE_MOCK:
        messages = gemini.draft_messages(req.facts.model_dump(mode="json"), contacts)
    if messages is None:
        messages = [mocks.message(c, occupation) for c in contacts]

    return ReferralResponse(
        referrals=[Referral(message=m, **c) for c, m in zip(contacts, messages)], mock=mock
    )
