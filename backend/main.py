"""What Now? by Meridian — agent backend."""

from datetime import date

import contextvars
import json
import logging
import queue
import threading

from fastapi import Body, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from fastapi.responses import Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

import activity
import config
import sources_log
from models import (STEPS, OpportunitiesRequest, OpportunitiesResponse, Action, AskRequest, AskResponse, AskSource,
                    ChatRequest, ChatResponse, Deadline, QuickReply, Facts, IntakeRequest, IntakeResponse, PlanBOption,
                    PlanRequest, PlanResponse, PossibleDate, Source, StepsUpdateRequest, StepsUpdateResponse,
                    TimelineStep)
import ask as ask_rules
import opportunities as opps
import plan_b
from questions import APPROX, canonical_permit, needed_fields, next_field, question, questions_for
from rules import calculate_deadline
from countries.finland import (DEADLINE_RULES, MAX_PERSONAL, PERSONAL_QUESTIONS, SOURCE_TITLE, SOURCE_URL,
                               TRUSTED_DOMAINS)
from live_check import check_all_rules, get_live_check
from integrations import elevenlabs
from services import exa_search, gemini, mocks

app = FastAPI(title="What Now? by Meridian", description="Calm next steps for people who lost their job in Finland. See docs/api.md.")
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS,
                   allow_methods=["*"], allow_headers=["*"])


class AccessCodeMiddleware:
    """Sets, for each request, whether it may use the paid APIs (see config.ACCESS_CODES). Plain ASGI so the
    setting reaches the endpoint and its worker threads."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        code = dict(scope.get("headers") or []).get(b"x-access-code", b"").decode("utf-8", "ignore")
        token = config.set_live(config.live_for(code))
        try:
            await self.app(scope, receive, send)
        finally:
            config.reset_live(token)


app.add_middleware(AccessCodeMiddleware)


@app.get("/health")
def health():
    return {"ok": True, "live": config.live(), "access_codes": bool(config.ACCESS_CODES),
            "gemini": bool(config.gemini_key()), "exa": bool(config.exa_key()),
            "context_dev": bool(config.context_key()),
            "voice_configured": bool(config.elevenlabs_key()), "voice": elevenlabs.available()}


@app.get("/rules", summary="Deadline rules, their latest live check and trusted domains")
def rules():
    """The Finland deadline rules from the country config, each with its latest live check against the
    official page (cached 24h), the domains we trust, and `sources_used`: every page Exa used recently
    (url, title, domain, page date, roadmap step)."""
    if config.USE_MOCK:
        return {**mocks.example("rules"), "sources_used": []}
    return {"rules": check_all_rules(), "trusted_domains": TRUSTED_DOMAINS, "sources_used": sources_log.recent()}


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
CHECK_ERROR = "Couldn't check Migri's page right now. The date is based on the rule we last confirmed."


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
    end = merged.get("job_end_date")
    if isinstance(end, str) and end.startswith(APPROX):
        merged["job_end_date"], merged["job_end_date_approximate"] = end[len(APPROX):], True
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
    statuses = {c["status"] for c in checks}
    if not checks:
        check_status = "none"
    elif "mismatch" in statuses:
        check_status = "mismatch"
    elif "error" in statuses:
        check_status = "error"
    else:
        check_status = "verified"

    d = Deadline(
        status=status, explanation=r["explanation"], applies=r["applies"], months=r["months"],
        deadline_date=r["deadline_date"], possible_dates=possible, missing=missing, rule_id=r["rule_id"],
        source=Source(title=SOURCE_TITLE, url=r["source_url"]), verified=check_status == "verified",
        deadline_is_approximate=bool(f.job_end_date_approximate) and r["deadline_date"] is not None,
        rule_in_force_since=next((x["in_force_since"] for x in DEADLINE_RULES if x["id"] in rule_ids), None),
        check_status=check_status, live_checks=checks,
    )
    if d.deadline_date:
        d.days_left = (d.deadline_date - today).days
    # The date always comes from our rules engine. The live check only adds a note next to it.
    if check_status == "mismatch":
        d.warning, d.warning_link = WARNING, r["source_url"]
    elif check_status == "error":
        d.warning, d.warning_link = CHECK_ERROR, r["source_url"]
    return d


def _cite(ids: list[str], by_id: dict) -> list[Source]:
    return [Source(title=by_id[i]["title"], url=by_id[i]["url"], highlight=by_id[i]["highlight"],
                   published=by_id[i].get("published"))
            for i in ids if i in by_id]


def build_plan(f: Facts, d: Deadline, today: date, note: str | None = None) -> dict | None:
    """Exa finds official pages, Gemini writes the plan from them. None if either is unavailable."""
    if not gemini.available():  # no point spending Exa credits if Gemini can't write the plan
        return None
    cands = plan_b.candidates(f, canonical_permit(f))
    topics = exa_search.plan_topics(f.field, cands, f.city, f.unemployment_fund, f.registered_jobseeker, note)
    sources = exa_search.search_plan_sources(topics)
    if not sources:
        return None
    sources = [{**s, "id": f"S{i + 1}"} for i, s in enumerate(sources)]
    by_id = {s["id"]: s for s in sources}
    out = gemini.write_plan(f.model_dump(mode="json"), d.model_dump(mode="json"), sources, today.isoformat(), cands, note)
    if not out:
        return None

    this_week = [Action(title=a["title"], why=a["why"], how=a["how"], sources=_cite(a["source_ids"], by_id),
                        title_short=a.get("title_short") or "", why_short=a.get("why_short") or "")
                 for a in out.get("this_week", [])]
    this_week = [a for a in this_week if a.sources][:3]  # every action must cite a real source
    if len(this_week) < 3:
        return None
    timeline = [TimelineStep(week=w["week"], steps=w["steps"], sources=_cite(w["source_ids"], by_id))
                for w in out.get("timeline", [])]
    by_cand = {c["id"]: c for c in cands}
    plan_b_out = []
    for p in out.get("plan_b", []):
        c = by_cand.get(p.get("candidate_id"))
        cited = _cite(p.get("source_ids", []), by_id)
        if c and cited:
            plan_b_out.append(_plan_b_option(c, p["why"], cited, d, p.get("why_short") or ""))
    return {"this_week": this_week, "timeline": [w for w in timeline if w.sources],
            **_with_plan_b_note(plan_b_out, cands)}


def _plan_b_option(c: dict, why: str, sources: list[Source], d: Deadline, why_short: str = "") -> PlanBOption:
    # Apply while your current permit's protection period still runs: that's the deadline from the rules engine.
    latest = d.deadline_date.isoformat() if d.deadline_date else None
    return PlanBOption(id=c["id"], option=c["option"], who_it_fits=c["who_it_fits"], why=why,
                       latest_start_date=latest, sources=sources, title_short=c.get("title_short", ""),
                       why_short=why_short)


def _with_plan_b_note(options: list[PlanBOption], cands: list[dict]) -> dict:
    if options:
        return {"plan_b": options}
    return {"plan_b": [], "plan_b_note": plan_b.NO_PERMIT_RISK if not cands else plan_b.NONE_FIT}


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
        cands = plan_b.candidates(f, canonical_permit(f))
        migri = Source(**mocks.SOURCES["migri"])
        built.update(_with_plan_b_note(
            [_plan_b_option(c, "Check the conditions and how to apply on Migri's site.", [migri], d) for c in cands], cands))
    return PlanResponse(deadline=d, disclaimer=DISCLAIMER, mock=mock, **built)


# ---------- /steps/update ----------
# The steps are shown as one numbered list: this week's 3 actions, then the later weeks (not "Week 1", which is the
# same as this week), then the Plan B options. Adding info to step k rewrites step k and everything after it.

def _later_weeks(p: PlanResponse) -> list[TimelineStep]:
    return [w for w in p.timeline if w.week.strip().lower() != "week 1"]


def merge_from_step(old: PlanResponse, new: PlanResponse, k: int) -> PlanResponse:
    """Steps before k stay exactly as they were; step k onward come from the new plan."""
    n_a, old_weeks = len(old.this_week), _later_weeks(old)
    if k <= n_a:
        this_week = old.this_week[:k - 1] + new.this_week[k - 1:3]
        if len(this_week) < len(old.this_week):  # the new plan had fewer actions: keep the old ones
            this_week += old.this_week[len(this_week):]
        timeline, plan_b, note = new.timeline, new.plan_b, new.plan_b_note
    elif k <= n_a + len(old_weeks):
        kept = old_weeks[:k - n_a - 1]
        labels = {w.week for w in kept}
        week1 = [w for w in old.timeline if w not in old_weeks]
        this_week = old.this_week
        timeline = week1 + kept + [w for w in _later_weeks(new) if w.week not in labels]
        plan_b, note = new.plan_b, new.plan_b_note
    else:
        kept_b = old.plan_b[:k - n_a - len(old_weeks) - 1]
        ids = {p.id or p.option for p in kept_b}
        this_week, timeline = old.this_week, old.timeline
        plan_b = kept_b + [p for p in new.plan_b if (p.id or p.option) not in ids]
        note = new.plan_b_note if not plan_b else None
    return PlanResponse(deadline=new.deadline, this_week=this_week, timeline=timeline, plan_b=plan_b,
                        plan_b_note=note, disclaimer=new.disclaimer, mock=new.mock)


# Facts a step note may change. The ones behind the date (permit, years, last day) are only changed in
# "What we know so far", so a loose phrase like "last week" in a note can't silently move the date.
STEP_FACTS = {"unemployment_fund", "registered_jobseeker", "studied_in_finland", "family_in_finland", "city"}


@app.post("/steps/update", response_model=StepsUpdateResponse, response_model_exclude_none=True,
          summary="Add info to one step; that step and the ones after it are rewritten")
def steps_update(req: StepsUpdateRequest):
    """New facts in the note are picked up with plain keyword rules (no AI). Then one extra Exa search on what the
    person wrote, plus the usual searches (cached), and one Gemini call rewrite the plan; steps before `step` are
    kept exactly as they were. `/steps/update/stream` sends live Exa activity first."""
    today = date.today()
    found = _clean_extracted(mocks.extract_facts(req.note, today))
    now = req.facts.model_dump(mode="json")
    update = {k: v for k, v in found.items()
              if k in STEP_FACTS and v not in (None, "") and now.get(k) != v}
    if update:
        activity.emit({"type": "app", "who": "code",
                       "text": f"Noted from what you wrote: {', '.join(FIELD_NAMES.get(k, k) for k in update)}"})
    facts = Facts.model_validate({**now, **update})
    if config.USE_MOCK:
        return StepsUpdateResponse(plan=req.plan, facts=facts, facts_update=update, updated_from=req.step, mock=True,
                                   message="Live updates are off in demo mode. You can still save what you added.")
    _progress("checking_rules")
    d = build_deadline(facts, today)
    _progress("finding_steps")
    built = build_plan(facts, d, today, note=req.note.strip())
    if built is None:
        return StepsUpdateResponse(plan=req.plan, facts=facts, facts_update=update, updated_from=req.step, mock=True,
                                   message="Couldn't update your steps live right now. You can still save what you added, and try the update again later.")
    new = PlanResponse(deadline=d, disclaimer=DISCLAIMER, mock=False, **built)
    merged = merge_from_step(req.plan, new, req.step)
    _partial("plan", merged)
    return StepsUpdateResponse(plan=merged, facts=facts, facts_update=update, updated_from=req.step)


@app.post("/steps/update/stream", summary="Same as /steps/update, streamed with live Exa activity")
def steps_update_stream(req: StepsUpdateRequest):
    return _stream(lambda: steps_update(req).model_dump(mode="json", exclude_none=True), "steps update")


def _stream(run, what: str):
    events: queue.Queue = queue.Queue()

    def work():
        activity.set_emitter(events.put)
        try:
            events.put({"type": "result", "data": run()})
        except Exception as e:  # noqa: BLE001
            logging.getLogger(__name__).exception("%s stream failed: %s", what, e)
            events.put({"type": "error"})
        events.put(None)

    threading.Thread(target=contextvars.copy_context().run, args=(work,), daemon=True).start()  # keeps the live/demo setting

    def gen():
        while (event := events.get()) is not None:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------- guided chat ----------

FIELD_NAMES = {"lost_job": "whether you lost your job", "citizenship_group": "citizenship", "citizenship_country": "country", "permit_type": "permit type",
               "years_on_work_permit": "time on a work permit", "job_end_date": "last day of work", "city": "city",
               "field": "your work", "studied_in_finland": "studies in Finland", "family_in_finland": "family in Finland",
               "unemployment_fund": "unemployment fund", "registered_jobseeker": "registering as a jobseeker"}
NEXT_LABEL = {"deadline": "Show me this week"}
STEP_REPLY = {
    "deadline": "Thank you. Here is your deadline and the rule behind it. Take your time with it.",
    "this_week": "Here are the three most useful things to do this week, each with its official source.",
}
FIRST_REPLY = "Thank you for telling me. One quick question: "
CITIZEN_REPLY = ("Good news: as an EU/EEA or Finnish citizen, your right to stay in Finland doesn't depend on your job, "
                 "so there's no permit end date to worry about. What Now? is built for people on a residence permit, "
                 "but these official services can help you with income and your next job.")
NOT_JOB_LOSS_REPLY = ("I'm sorry you're going through this. What Now? only helps with losing a job in Finland and "
                      "what it means for your residence permit. If your permit is based on a relationship that has "
                      "ended, Migri explains what happens next.")
OFF_TOPIC_START_REPLY = ("I focus on job loss in Finland, so I can't help with that one. If you've lost your job or "
                         "are about to, tell me what happened and I'll work out how long you can stay and your next steps.")
NOT_JOB_LOSS_LINKS = [
    Source(title="Residence permits and changes in your situation (Migri)", url="https://migri.fi/en/home"),
    Source(title="Living in Finland (InfoFinland)", url="https://www.infofinland.fi/en"),
]
CITIZEN_LINKS = [
    Source(title="Register as a jobseeker (Job Market Finland)", url="https://tyomarkkinatori.fi/en"),
    Source(title="Unemployment benefits (Kela)", url="https://www.kela.fi/unemployment"),
    Source(title="Unemployment in Finland (InfoFinland)", url="https://www.infofinland.fi/en/work-and-enterprise/unemployment"),
]


def _clean_extracted(extracted: dict) -> dict:
    """Keep only values our models accept, and Gemini's picks only from our list of personal questions."""
    out = dict(extracted)
    for k, allowed in (("unemployment_fund", {"yes", "no", "not_sure"}), ("registered_jobseeker", {"yes", "no"})):
        if out.get(k) not in allowed:
            out.pop(k, None)
    if "useful_questions" in out:
        picks = [q for q in out.pop("useful_questions") or [] if q in PERSONAL_QUESTIONS]
        out["to_ask"] = list(dict.fromkeys(picks))[:MAX_PERSONAL]
    return out


def _merge_chat_facts(req: ChatRequest, extracted: dict) -> tuple[Facts, list[str]]:
    """edited_facts always win, then tapped answers, then what Gemini read from the latest message."""
    known = Facts.model_fields
    extracted = _clean_extracted(extracted)
    merged = {k: v for k, v in req.facts.items() if k in known and v is not None}
    merged.update({k: v for k, v in extracted.items() if k in known and v is not None and k != "to_ask"})
    if merged.get("to_ask") is None and "to_ask" in extracted:  # chosen once, from the first message
        merged["to_ask"] = extracted["to_ask"]
    merged.update({k: v for k, v in req.answers.items() if k in known})
    merged.update({k: v for k, v in req.edited_facts.items() if k in known})
    # "About a week ago" arrives as "about:2026-11-07"; an exact date (tapped, picked or edited) clears the flag.
    end = merged.get("job_end_date")
    if isinstance(end, str) and end.startswith(APPROX):
        merged["job_end_date"], merged["job_end_date_approximate"] = end[len(APPROX):], True
    elif "job_end_date" in req.answers or "job_end_date" in req.edited_facts:
        merged["job_end_date_approximate"] = False
    confirmed = [k for k in {**req.answers, **req.edited_facts} if k in known]
    return Facts.model_validate(merged), confirmed


@app.post("/chat", response_model=ChatResponse, response_model_exclude_none=True,
          summary="Guided chat that keeps a live 'What we know so far' card")
def chat(req: ChatRequest = Body(openapi_examples=_examples("chat"))):
    """The browser keeps the session and sends it each time (no accounts, nothing stored here).
    Steps: about_you -> deadline -> this_week. Send `action: "next"` to move on.
    `/chat/stream` returns the same result with progress events first."""
    return run_chat(req)


PROGRESS = ("reading_situation", "checking_rules", "finding_steps")


@app.post("/chat/stream", summary="Same as /chat, streamed as server-sent events with progress")
def chat_stream(req: ChatRequest):
    """Events: `{"type": "progress", "stage": ...}` for each of reading_situation, checking_rules and
    finding_steps (only the ones this step needs), then `{"type": "result", "data": <ChatResponse>}`
    or `{"type": "error"}`."""
    events: queue.Queue = queue.Queue()

    def work():
        activity.set_emitter(events.put)
        try:
            resp = run_chat(req)
            events.put({"type": "result", "data": resp.model_dump(mode="json", exclude_none=True)})
        except Exception as e:  # noqa: BLE001
            logging.getLogger(__name__).exception("chat stream failed: %s", e)
            events.put({"type": "error"})
        events.put(None)

    threading.Thread(target=contextvars.copy_context().run, args=(work,), daemon=True).start()  # keeps the live/demo setting

    def gen():
        while (event := events.get()) is not None:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _progress(stage: str) -> None:
    activity.emit({"type": "progress", "stage": stage})


def _partial(key: str, value) -> None:
    activity.emit({"type": "partial", "key": key, "data": value.model_dump(mode="json", exclude_none=True)})


def _off_topic_start(mock: bool) -> ChatResponse:
    activity.emit({"type": "app", "who": "code", "text": "Not about losing a job: kindly saying what we help with"})
    return ChatResponse(reply=OFF_TOPIC_START_REPLY, step="about_you", facts=Facts(), out_of_scope=True, mock=mock)


def run_chat(req: ChatRequest) -> ChatResponse:
    resp = _run_chat(req)
    resp.demo = config.USE_MOCK  # the app then says clearly that it's a sample person, not you
    return resp


def _run_chat(req: ChatRequest) -> ChatResponse:
    today = date.today()
    latest = req.messages[-1] if req.messages else None
    extracted, mock = {}, config.USE_MOCK
    if latest and latest.role == "user" and latest.text.strip():
        # A first message that's clearly not about losing a job (e.g. "best pizza in Helsinki?") gets a polite no.
        starting = not req.facts and not req.answers and not req.edited_facts
        off_topic = starting and not ask_rules.on_topic(latest.text) and not mocks.JOB_LOSS.search(latest.text.lower())
        if off_topic and config.USE_MOCK:
            return _off_topic_start(mock)
        _progress("reading_situation")
        if config.USE_MOCK:
            extracted = mocks.example_facts()
        else:
            extracted = gemini.extract_facts(latest.text, today.isoformat())
            if extracted is None:
                extracted, mock = mocks.extract_facts(latest.text, today), True
        if extracted.get("job_was_in_finland") is False:
            return ChatResponse(reply=("I'm sorry about your job. What Now? only covers jobs in Finland, so the official "
                                       "services of the country where you worked are the best place to start."),
                                step="about_you", facts=Facts(), out_of_scope=True, link=OUT_OF_SCOPE_LINK,
                                links=[Source(title="Moving and working in Finland (InfoFinland)", url=OUT_OF_SCOPE_LINK)],
                                mock=mock)

        # No job words and Gemini didn't say it's about losing a job: same polite reply as demo mode.
        if off_topic and extracted.get("lost_job") is not True:
            return _off_topic_start(mock)

    facts, confirmed = _merge_chat_facts(req, extracted)
    if facts.lost_job is False:
        activity.emit({"type": "app", "who": "code", "text": "Not about losing a job: showing useful links instead"})
        return ChatResponse(reply=NOT_JOB_LOSS_REPLY, step="about_you", facts=facts, confirmed_fields=confirmed,
                            out_of_scope=True, links=NOT_JOB_LOSS_LINKS, mock=mock)
    if facts.citizenship_group == "eu_eea":
        # Not who What Now? is for: a kind message and useful links, no roadmap.
        activity.emit({"type": "app", "who": "code", "text": "EU/EEA citizen: no permit end date, showing useful links"})
        return ChatResponse(reply=CITIZEN_REPLY, step="about_you", facts=facts, confirmed_fields=confirmed,
                            out_of_scope=True, links=CITIZEN_LINKS, mock=mock)
    if extracted:
        found = [FIELD_NAMES[k] for k, v in extracted.items() if k in FIELD_NAMES and v is not None]
        activity.emit({"type": "app", "who": "gemini" if not mock else "app",
                       "text": f"Picked out from your message: {', '.join(found)}" if found else "Nothing clear in that message yet"})
    first = sum(m.role == "user" for m in req.messages) <= 1 and not req.answers and not req.edited_facts
    missing = needed_fields(facts)
    ask = next_field(facts)
    if ask:
        q = question(ask, today)
        why = (f"still needed to work out how long you can stay: {', '.join(FIELD_NAMES[m] for m in missing)}" if missing
               else "checking whether this is about losing a job" if ask == "lost_job"
               else "so your steps fit you")
        activity.emit({"type": "app", "who": "code", "text": f"Asking about {FIELD_NAMES[ask]} ({why})"})
        reply = (FIRST_REPLY if first else "") + q.question
        return ChatResponse(reply=reply, step="about_you", facts=facts, confirmed_fields=confirmed,
                            question=q, mock=mock)

    current = STEPS.index(req.step) if req.step in STEPS else 0
    step = STEPS[max(1, min(current + (req.action == "next"), len(STEPS) - 1))]
    _progress("checking_rules")
    deadline = build_deadline(facts, today) if not config.USE_MOCK else PlanResponse(**mocks.example("plan")).deadline
    if deadline.months and deadline.deadline_date:
        activity.emit({"type": "app", "who": "code",
                       "text": f"Worked out how long you can stay, with plain code: {deadline.months} months → {deadline.deadline_date.isoformat()}"})
    elif deadline.status == "not_applicable":
        activity.emit({"type": "app", "who": "code", "text": "Checked the rules: your permit doesn't depend on this job"})
    _partial("deadline", deadline)
    resp = ChatResponse(reply=STEP_REPLY[step], step=step, facts=facts, confirmed_fields=confirmed,
                        deadline=deadline, mock=mock)

    if step == "this_week":
        _progress("finding_steps")
        resp.plan = build_full_plan(facts, deadline)
        _partial("plan", resp.plan)
        resp.mock = resp.mock or resp.plan.mock
    if step in NEXT_LABEL:
        resp.quick_replies = [QuickReply(value="next", label=NEXT_LABEL[step])]
    return resp


# ---------- /ask ----------

@app.post("/ask", response_model=AskResponse, response_model_exclude_none=True,
          summary="Ask a question; Exa answers from live sources")
def ask_question(req: AskRequest):
    """Exa's Answer endpoint answers with citations. Questions about rules (permits, benefits, registering)
    are limited to the trusted official domains. Off-topic questions get a polite no. Answers are cached 24h."""
    q = req.question.strip()
    update = _facts_in_question(q, req.facts)
    if not q or (not ask_rules.on_topic(q) and not update):
        return AskResponse(answer=ask_rules.OFF_TOPIC_REPLY, off_topic=True)
    official = ask_rules.about_rules(q)
    f = req.facts
    context = ", ".join(x for x in [
        f.permit_type and f"{f.permit_type.replace('_', ' ')} permit", f.city and f"lives in {f.city}",
        f.field and f"works as {f.field}"] if x)
    step = ask_rules.suggested_step(q)
    if update and not ask_rules.on_topic(q):
        # Only a correction ("I've been here 3 years"): update the situation, nothing to look up.
        return AskResponse(answer="Thanks, I've updated your situation. Your roadmap is being rebuilt.", facts_update=update)
    out = None if config.USE_MOCK else exa_search.ask(q, official, context)
    if out is None:
        return AskResponse(answer=("I can't look that up live right now. For permits, check migri.fi; for benefits, "
                                   "kela.fi; for registering as a jobseeker, tyomarkkinatori.fi."),
                           suggested_roadmap_step=step, official_only=official, facts_update=update, mock=True)
    sources = [AskSource(title=c["title"], url=c["url"], domain=exa_search._domain(c["url"]), date=c.get("published"))
               for c in out["citations"]]
    answer = out["answer"]
    if official and not sources:
        answer = ("I couldn't find this on the official sites (Migri, Kela, InfoFinland, Työmarkkinatori). "
                  "Please check with Migri or your union.")
    return AskResponse(answer=answer, sources=sources, suggested_roadmap_step=step if sources else None,
                       official_only=official, facts_update=update)


ASK_IGNORED = {"lost_job", "job_was_in_finland", "job_end_date_approximate", "to_ask"}


def _facts_in_question(q: str, current: Facts) -> dict:
    """Facts in the question that differ from the current situation (Gemini, or the keyword fallback)."""
    if not q or config.USE_MOCK:
        return {}
    today = date.today().isoformat()
    found = gemini.extract_facts(q, today) if gemini.available() else None
    if found is None:
        found = mocks.extract_facts(q, date.today())
    found = _clean_extracted(found)
    now = current.model_dump(mode="json")
    update = {}
    for k, v in found.items():
        if k in Facts.model_fields and k not in ASK_IGNORED and v not in (None, "") and now.get(k) != v:
            update[k] = v
    if update:
        activity.emit({"type": "app", "who": "gemini",
                       "text": f"Found new details in your question: {', '.join(FIELD_NAMES.get(k, k) for k in update)}"})
    return update


# ---------- /opportunities ----------

def _deadline_months(f: Facts) -> int | None:
    permit = canonical_permit(f)
    if permit is None:
        return None
    try:
        return calculate_deadline(permit, f.years(), f.job_end_date).get("months")
    except ValueError:
        return None


@app.post("/opportunities", response_model=OpportunitiesResponse,
          summary="Perks and support, found live")
def opportunities(req: OpportunitiesRequest):
    """Separate from the roadmap: the job search certificate, city discounts for unemployed jobseekers and employer
    hiring incentives ("may apply", with conditions). Every item comes from an Exa source on an official or city
    site, with the page date. 3 Exa searches and 1 Gemini call per city, cached 24h.
    `/opportunities/stream` streams the result with live activity."""
    if config.USE_MOCK:
        return OpportunitiesResponse(**mocks.example("opportunities"), demo=True)
    return opps.build(req.facts, _deadline_months(req.facts))


@app.post("/opportunities/stream", summary="Same as /opportunities, streamed with live activity")
def opportunities_stream(req: OpportunitiesRequest):
    events: queue.Queue = queue.Queue()

    def work():
        activity.set_emitter(events.put)
        try:
            resp = opportunities(req)
            events.put({"type": "result", "data": resp.model_dump(mode="json")})
        except Exception as e:  # noqa: BLE001
            logging.getLogger(__name__).exception("opportunities stream failed: %s", e)
            events.put({"type": "error"})
        events.put(None)

    threading.Thread(target=contextvars.copy_context().run, args=(work,), daemon=True).start()  # keeps the live/demo setting

    def gen():
        while (event := events.get()) is not None:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------- voice (ElevenLabs) ----------

@app.post("/voice/transcribe", summary="Voice typing: a short recording in, its text out")
async def voice_transcribe(request: Request):
    """Send the raw recording as the body (e.g. Content-Type: audio/webm from the browser's MediaRecorder), max 5 MB.
    Returns {"text": ...}. 503 when voice isn't set up, so the app can hide the mic. Nothing is stored here."""
    if not elevenlabs.available():
        raise HTTPException(503, "Voice typing isn't available right now.")
    audio = await request.body()
    if not audio or len(audio) > elevenlabs.MAX_AUDIO_BYTES:
        raise HTTPException(413 if audio else 422, "Please record a shorter message (up to about a minute).")
    text = elevenlabs.transcribe(audio, request.headers.get("content-type", "audio/webm"))
    if not text:
        raise HTTPException(502, "Couldn't understand that recording. Please try again or type instead.")
    return {"text": text}


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=elevenlabs.MAX_TTS_CHARS)


@app.post("/voice/speak", summary="Listen: text in, MP3 out (cached 7 days)")
def voice_speak(req: SpeakRequest):
    audio = elevenlabs.speak(req.text)
    if audio is None:
        raise HTTPException(503, "Listening isn't available right now.")
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=86400"})

