"""What Now? by Meridian — agent backend."""

from datetime import date

import json

from fastapi import Body, FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from models import (STEPS, Action, ChatRequest, ChatResponse, Community, Company, Contact, Deadline, Draft, QuickReply, Facts, IntakeRequest, IntakeResponse, PlanBOption, PlanRequest,
                    PlanResponse, PossibleDate, ReferralRequest, ReferralResponse, Source,
                    TimelineStep)
from questions import canonical_permit, needed_fields, questions_for
from rules import calculate_deadline
from countries.finland import DEADLINE_RULES, SOURCE_TITLE, SOURCE_URL, TRUSTED_DOMAINS
from live_check import check_all_rules, get_live_check
from services import exa_search, gemini, mocks

app = FastAPI(title="What Now? by Meridian", description="Calm next steps for people who lost their job in Finland. See docs/api.md.")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS,
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"ok": True, "gemini": bool(config.gemini_key()), "exa": bool(config.exa_key()),
            "oxylabs": config.ENABLE_OXYLABS, "elevenlabs": config.ENABLE_ELEVENLABS}


@app.get("/rules", summary="Deadline rules, their latest live check and trusted domains")
def rules():
    """The Finland deadline rules from the country config, each with its latest live check against the
    official page (cached 24h), plus the domains we trust for sources."""
    if config.USE_MOCK:
        return mocks.example("rules")
    return {"rules": check_all_rules(), "trusted_domains": TRUSTED_DOMAINS}


def _examples(*names: str) -> dict:
    """Request examples for /docs, from the saved persona examples in backend/mocks/."""
    out = {}
    for n in names:
        out[n] = {"summary": n.replace("_", " "), "value": json.loads((mocks.EXAMPLES_DIR / f"{n}.json").read_text())["request"]}
    return out


OUT_OF_SCOPE_LINK = "https://www.infofinland.fi/en/work-and-enterprise/unemployment"
DISCLAIMER = ("This is general guidance based on official Finnish sources, not legal advice. "
              "Rules can change: confirm your situation with Migri, Kela or your union.")
WARNING = "This rule may have changed. Please check Migri."


@app.post("/intake", response_model=IntakeResponse, response_model_exclude_none=True,
          summary="Turn the user's sentence into facts and ask what's missing")
def intake(req: IntakeRequest = Body(openapi_examples=_examples("intake", "intake_questions", "intake_out_of_scope"))):
    """Gemini extracts facts from free text, merged with `answers` to earlier questions (answers win).
    Returns up to 3 tap-to-answer questions for what the deadline still needs, or `out_of_scope`
    if the job was outside Finland."""
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


@app.post("/plan", response_model=PlanResponse, summary="Deadline, this week's 3 actions, timeline and plan B")
def plan(req: PlanRequest = Body(openapi_examples=_examples("plan"))):
    """The rules engine computes the deadline (hidden if today's live check can't verify the rule).
    Exa finds official pages on the trusted domains; Gemini writes the plan from them only, citing sources."""
    return build_full_plan(req.facts)


def build_full_plan(f: Facts, d: Deadline | None = None) -> PlanResponse:
    if config.USE_MOCK:
        return PlanResponse(**mocks.example("plan"))
    today = date.today()
    d = d or build_deadline(f, today)
    built = build_plan(f, d, today)
    mock = built is None
    if built is None:
        built = mocks.plan(d.deadline_date.isoformat() if d.deadline_date else None)
    return PlanResponse(deadline=d, disclaimer=DISCLAIMER, mock=mock, **built)


MAX_DRAFT_WORDS = 80


def _template_draft(c: dict, field: str) -> str:
    return (f"Hi {c['name']}, I'm a {field} in Finland looking for my next role. I came across your work at "
            f"{c['company']} and would really value a short chat or a pointer to the right person. "
            "Thank you for your time! [Your name]")


@app.post("/referrals", response_model=ReferralResponse, summary="Companies, people, communities and draft messages")
def referrals(req: ReferralRequest = Body(openapi_examples=_examples("referrals"))):
    """Exa finds companies hiring, public professional profiles at the top companies and communities.
    Gemini drafts one short message per contact. Drafts only: nothing is ever sent."""
    return build_referrals(req.facts)


def build_referrals(f: Facts) -> ReferralResponse:
    field = f.field or "professional"
    city = f.city or "Helsinki"
    today = date.today().isoformat()

    if config.USE_MOCK:
        return ReferralResponse(**mocks.example_referrals(), mock=True)

    companies = exa_search.search_companies(field, city) or []
    contacts = exa_search.search_people(companies, field, city) if companies else []
    contacts = contacts or []
    communities = exa_search.search_communities(field, city, today) or []
    if not (companies or communities):
        return ReferralResponse(**mocks.referrals(city), mock=True)

    companies = [{**c, "id": f"C{i + 1}"} for i, c in enumerate(companies)]
    contacts = [{**c, "id": f"P{i + 1}"} for i, c in enumerate(contacts)]
    communities = [{**c, "id": f"G{i + 1}"} for i, c in enumerate(communities)]
    notes = gemini.write_referral_notes(f.model_dump(mode="json"), companies, contacts, communities, today) or {}
    why = {n["id"]: n["why_relevant"] for n in notes.get("companies", [])}
    kinds = {n["id"]: n for n in notes.get("communities", [])}
    drafts = {n["id"]: n for n in notes.get("drafts", [])}

    out_companies = [Company(name=c["name"], url=c["url"], source=Source(title=c["name"], url=c["url"], highlight=c["highlight"]),
                             why_relevant=why.get(c["id"]) or f"From their page: {c['highlight'][:160]}")
                     for c in companies]
    out_contacts, out_drafts = [], []
    for c in contacts:
        d = drafts.get(c["id"], {})
        message = d.get("message", "")
        if not message or len(message.split()) > MAX_DRAFT_WORDS:
            message = _template_draft(c, field)
        out_contacts.append(Contact(name=c["name"], role=c["role"] or "Professional", company=c["company"],
                                    profile_url=c["profile_url"],
                                    why_this_person=d.get("why_this_person") or f"Works at {c['company']}."))
        out_drafts.append(Draft(to=c["name"], profile_url=c["profile_url"], message=message))
    out_communities = []
    for g in communities:
        n = kinds.get(g["id"], {})
        kind = n.get("type") if n.get("type") in ("professional_group", "event", "union") else g["kind"]
        out_communities.append(Community(name=g["name"], url=g["url"], type=kind,
                                         date_if_event=n.get("date_if_event") if kind == "event" else None))
    return ReferralResponse(companies=out_companies, contacts=out_contacts, communities=out_communities,
                            drafts=out_drafts, mock=not notes)


# ---------- guided chat ----------

NEXT_LABEL = {"deadline": "Show me this week", "this_week": "Help me find my way in"}
STEP_REPLY = {
    "deadline": "Thank you. Here is your deadline and the rule behind it. Take your time with it.",
    "this_week": "Here are the three most useful things to do this week, each with its official source.",
    "find_your_way_in": ("Here are companies, people and communities that could help. The messages are drafts: "
                         "read them, change anything, and send them yourself if you want to."),
}
FIRST_REPLY = "Thank you for telling me. One quick question: "


def _merge_chat_facts(req: ChatRequest, extracted: dict) -> tuple[Facts, list[str]]:
    """edited_facts always win, then tapped answers, then what Gemini read from the latest message."""
    known = Facts.model_fields
    merged = {k: v for k, v in req.facts.items() if k in known and v is not None}
    merged.update({k: v for k, v in extracted.items() if k in known and v is not None})
    merged.update({k: v for k, v in req.answers.items() if k in known})
    merged.update({k: v for k, v in req.edited_facts.items() if k in known})
    confirmed = [k for k in {**req.answers, **req.edited_facts} if k in known]
    return Facts.model_validate(merged), confirmed


@app.post("/chat", response_model=ChatResponse, response_model_exclude_none=True,
          summary="Guided chat that keeps a live 'Your situation' card")
def chat(req: ChatRequest = Body(openapi_examples=_examples("chat"))):
    """The browser keeps the session and sends it each time (no accounts, nothing stored here).
    Steps: about_you -> deadline -> this_week -> find_your_way_in. Send `action: "next"` to move on."""
    today = date.today()
    latest = req.messages[-1] if req.messages else None
    extracted, mock = {}, config.USE_MOCK
    if latest and latest.role == "user" and latest.text.strip():
        if config.USE_MOCK:
            extracted = mocks.example_facts()
        else:
            extracted = gemini.extract_facts(latest.text, today.isoformat())
            if extracted is None:
                extracted, mock = mocks.extract_facts(latest.text, today), True
        if extracted.get("job_was_in_finland") is False:
            return ChatResponse(reply=("What Now? only covers jobs in Finland. If your job was in another country, "
                                       "that country's official services are the right place to start."),
                                step="about_you", facts=Facts(), out_of_scope=True, link=OUT_OF_SCOPE_LINK, mock=mock)

    facts, confirmed = _merge_chat_facts(req, extracted)
    first = sum(m.role == "user" for m in req.messages) <= 1 and not req.answers and not req.edited_facts
    needed = needed_fields(facts)
    if needed:
        q = questions_for(facts, today)[0]
        reply = (FIRST_REPLY if first else "") + q.question
        return ChatResponse(reply=reply, step="about_you", facts=facts, confirmed_fields=confirmed,
                            question=q, mock=mock)

    current = STEPS.index(req.step) if req.step in STEPS else 0
    step = STEPS[max(1, min(current + (req.action == "next"), len(STEPS) - 1))]
    deadline = build_deadline(facts, today) if not config.USE_MOCK else PlanResponse(**mocks.example("plan")).deadline
    resp = ChatResponse(reply=STEP_REPLY[step], step=step, facts=facts, confirmed_fields=confirmed,
                        deadline=deadline, mock=mock)
    if step in ("this_week", "find_your_way_in"):
        resp.plan = build_full_plan(facts, deadline)
        resp.mock = resp.mock or resp.plan.mock
    if step == "find_your_way_in":
        resp.referrals = build_referrals(facts)
        resp.mock = resp.mock or resp.referrals.mock
    if step in NEXT_LABEL:
        resp.quick_replies = [QuickReply(value="next", label=NEXT_LABEL[step])]
    return resp
