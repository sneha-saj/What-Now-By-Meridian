"""Gemini calls. Each function returns None on missing key / failure so callers fall back to mocks."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
import logging
from typing import Any, Optional

from pydantic import BaseModel, Field

import activity
import config
import filecache
import limits

log = logging.getLogger(__name__)
CACHE_PATH = Path(__file__).resolve().parent.parent / ".gemini_cache.json"
CACHE_TTL = timedelta(hours=24)
TIMEOUT_MS = 45_000

_client = None


def _get_client():
    global _client
    key = config.gemini_key()
    if not key:
        return None
    if _client is None:
        from google import genai
        from google.genai import types

        # 45 s timeout and a single attempt: a slow or failing call falls back instead of hanging or retrying.
        _client = genai.Client(api_key=key, http_options=types.HttpOptions(
            timeout=TIMEOUT_MS, retry_options=types.HttpRetryOptions(attempts=1)))
    return _client


def available() -> bool:
    return bool(config.gemini_key()) and not limits.paused("Gemini")


def _call(prompt: str, schema: Any = None, purpose: str = "") -> Any | None:
    """Ask Gemini for JSON. With a Pydantic `schema`, uses structured output.

    Answers are cached on disk for 24h (same model + prompt + schema), so reloads and repeats are free.
    After a 429 Gemini is paused for a while and callers use their fallbacks; no retries.
    """
    k = filecache.key(config.GEMINI_MODEL, prompt, getattr(schema, "__name__", None))
    cached = filecache.read(CACHE_PATH, k)
    if cached is not None:
        activity.emit({"type": "gemini", "status": "cached", "purpose": purpose})
        return cached
    if limits.paused("Gemini"):
        return None
    client = _get_client()
    if client is None:
        return None
    activity.emit({"type": "gemini", "status": "working", "purpose": purpose})
    try:
        from google.genai import types

        # Low thinking: these are short extraction/writing tasks, so it's faster and cheaper on the free tier.
        cfg = {"response_mime_type": "application/json", "temperature": 0.2}
        if "lite" not in config.GEMINI_MODEL:
            cfg["thinking_config"] = types.ThinkingConfig(thinking_level="LOW")
        if schema is not None:
            cfg["response_schema"] = schema
        resp = client.models.generate_content(
            model=config.GEMINI_MODEL, contents=prompt, config=types.GenerateContentConfig(**cfg)
        )
        parsed = getattr(resp, "parsed", None)
        out = parsed.model_dump() if isinstance(parsed, BaseModel) else json.loads(resp.text)
    except Exception as e:  # noqa: BLE001 - demo resilience: never crash the UI
        if not limits.note_failure("Gemini", e):
            # The SDK's error text holds the HTTP status and Google's message, never the API key.
            log.warning("Gemini call failed, using fallback: %s %s %s", type(e).__name__,
                        getattr(e, "code", ""), str(getattr(e, "message", "") or e)[:200])
        return None
    filecache.write(CACHE_PATH, k, out, CACHE_TTL)
    activity.emit({"type": "gemini", "status": "done", "purpose": purpose})
    return out


def structured_call(prompt: str, schema: type[BaseModel], purpose: str = "") -> dict | None:
    out = _call(prompt, schema, purpose)
    return out if isinstance(out, dict) else None


def _json_call(prompt: str) -> Any | None:
    return _call(prompt)


# ---------- /intake ----------

class Extracted(BaseModel):
    lost_job: Optional[bool] = None
    job_was_in_finland: Optional[bool] = None
    citizenship_group: Optional[str] = None
    citizenship_country: Optional[str] = None
    permit_type: Optional[str] = None
    years_on_work_permit: Optional[float] = None
    job_end_date: Optional[str] = None
    job_end_date_approximate: Optional[bool] = None
    city: Optional[str] = None
    field: Optional[str] = None
    studied_in_finland: Optional[bool] = None
    family_in_finland: Optional[bool] = None
    unemployment_fund: Optional[str] = None
    registered_jobseeker: Optional[str] = None
    useful_questions: list[str] = Field(default_factory=list)


EXTRACT_PROMPT = """You read a short message from someone who lost (or is losing) their job and extract facts.
Use null whenever something is not stated or unclear. Never guess. Today is {today}.
- lost_job: true if they lost their job or are about to (laid off, fired, contract ending, notice); false if the
  message is clearly about something else; null if it doesn't say
- job_was_in_finland: false only if they clearly say the job was outside Finland
- citizenship_group: "eu_eea" (EU/EEA/Swiss citizen) | "other" (any other country) | "unknown"
- citizenship_country: country name in English
- permit_type: one of {permit_ids}
- years_on_work_permit: total years on a work-based permit in Finland, as a number
- job_end_date: last day of work as YYYY-MM-DD (resolve "yesterday", "last Friday" etc. from today)
- job_end_date_approximate: true if they gave a vague time ("last week", "a few weeks ago", "about a month
  ago", "early November"), false if exact ("yesterday", "last Friday", "1 November")
- city: city in Finland
- field: their job or industry, short, in English
- studied_in_finland, family_in_finland: true/false if stated
- unemployment_fund: "yes" if they say they are in an unemployment fund (työttömyyskassa) or a union with one,
  "no" if they say they are not; null otherwise
- registered_jobseeker: "yes" if they say they already registered as a jobseeker, "no" if they say they haven't
- useful_questions: up to 3 ids from the list below whose answers would most change THIS person's next steps,
  most useful first. Leave out anything the message already answers. Ids:
{personal}
Do not extract permit numbers, passport numbers, ID numbers, names or addresses.

Message: {text!r}"""


def extract_facts(text: str, today: str) -> dict | None:
    from countries.finland import PERMIT_TYPES, PERSONAL_QUESTIONS

    ids = ", ".join(f'"{p["id"]}"' for p in PERMIT_TYPES)
    personal = "\n".join(f"  - {k}: {why}" for k, why in PERSONAL_QUESTIONS.items())
    return structured_call(EXTRACT_PROMPT.format(text=text, today=today, permit_ids=ids, personal=personal), Extracted,
                           "reading your message and choosing what to ask you")


# ---------- /plan ----------

class _Action(BaseModel):
    title: str
    why: str
    how: list[str]
    source_ids: list[str]
    title_short: Optional[str] = None
    why_short: Optional[str] = None


class _Week(BaseModel):
    week: str
    steps: list[str]
    source_ids: list[str]


class _PlanB(BaseModel):
    candidate_id: str
    why: str
    source_ids: list[str]
    title_short: Optional[str] = None
    why_short: Optional[str] = None


class GeneratedPlan(BaseModel):
    this_week: list[_Action]
    timeline: list[_Week]
    plan_b: list[_PlanB]


PLAN_PROMPT = """You help a worried person in Finland who has lost their job. Be calm, plain and specific.

Use ONLY facts from the SOURCES below. Do not use outside knowledge. Cite sources by id.
If the sources do not cover something they need, write "Check with Migri or your union" instead of guessing.
The deadline below was computed by our rules engine: do not change it or invent another date.
Never use the word "deadline" in what you write; say "the date you can stay until" instead.
The steps are shown simply as Step 1, Step 2, ... in order, so don't write "this week", "next week" or "in week N"
inside titles, why or how; the week labels below are only for ordering.
Make every action specific to this person, using their facts and the sources: their city's services, their kind
of work, their permit and deadline. If registered_jobseeker is "yes", don't tell them to register again; give the
next step after registering. If unemployment_fund is "yes", point them to their fund for the earnings-related
allowance; if "no" or unknown, to Kela.

For every item also give title_short (max 6 words) and why_short (max 12 words): plain, complete phrases
for a compact card, e.g. "Register as a jobseeker" / "Keeps your benefit options open from day one".

Write:
1. this_week: exactly 3 actions, most urgent first. Each has a title, why (one calm sentence),
   how (2-4 short steps) and source_ids (at least one).
2. timeline: steps working back from the deadline, with week labels "Week 1", "Week 2", "Week 4",
   "Week 8" and "Final weeks". Skip weeks that fall after the deadline. Each has steps and source_ids.
3. plan_b: for each PLAN B CANDIDATE that the sources support, candidate_id, why (one or two calm sentences
   on what it is and the main condition, from the sources) and source_ids. Leave a candidate out if no
   source covers it. Do not add options that are not in the list.

PLAN B CANDIDATES:
{candidates}

Person: {facts}
Deadline: {deadline}
Today: {today}
{note}
SOURCES:
{sources}"""


def write_plan(facts: dict, deadline: dict, sources: list[dict], today: str, candidates: list[dict] | None = None,
               note: str | None = None) -> dict | None:
    src = "\n\n".join(
        f"[{s['id']}] {s['title']} ({s['url']})\n{(s.get('highlight') or '')[:1000]}" for s in sources
    )
    return structured_call(
        PLAN_PROMPT.format(facts=facts, deadline=deadline, today=today, sources=src,
                           candidates="\n".join(f"[{c['id']}] {c['option']}: {c['who_it_fits']}" for c in candidates or []) or "(none)",
                           note=(f"\nNEW INFORMATION from the person: {note}\nTake it into account in every step it affects.\n"
                                 if note else "")),
        GeneratedPlan, (f"rewriting your steps with what you added, from {len(sources)} pages Exa found" if note
                        else f"writing your plan from {len(sources)} official pages Exa found")
    )


# ---------- /opportunities ----------

class _OppCertificate(BaseModel):
    row_id: str
    how_to_get: str


class _OppDiscount(BaseModel):
    row_id: str
    name: str
    discount: str
    proof_needed: str
    title_short: Optional[str] = None
    why_short: Optional[str] = None


class _OppIncentive(BaseModel):
    row_id: str
    name: str
    what_it_is: str
    conditions_plain: str
    may_apply: bool
    caveat: str
    title_short: Optional[str] = None
    why_short: Optional[str] = None


class OpportunityNotes(BaseModel):
    certificate: Optional[_OppCertificate] = None
    discounts: list[_OppDiscount]
    incentives: list[_OppIncentive]


OPPORTUNITIES_PROMPT = """You help a person in Finland who lost their job find perks and support. Use ONLY the rows below.
Cite each item by its row id. Leave a row out if it doesn't clearly fit. Never invent names, dates or discounts.
Today is {today}. Plain language, one sentence per field, no markdown.
For every item also give title_short (max 6 words) and why_short (max 12 words): complete phrases for a compact card.

certificate: the [perks] row that explains how to get a job search certificate / proof of jobseeker status,
  with how_to_get in plain steps. null if no row explains it.
discounts: [perks] rows that state a concrete discount for unemployed jobseekers (sports, swimming, museums,
  culture, courses): name, discount (exactly as stated), proof_needed.
incentives: [perks] rows about employer hiring incentives: name, what_it_is, conditions_plain, may_apply (true only
  if the person plausibly meets the conditions), caveat (if a condition like "unemployed for 3 months" conflicts
  with their permit deadline of {deadline_months} months, say so plainly).

Person: {facts}

ROWS:
{rows}"""


def write_opportunities(facts: dict, deadline_months, rows: list[dict], today: str) -> dict | None:
    lines = "\n".join(f"[{r['id']}] [{r['purpose']}] {r['title']} ({r['url']}"
                      f"{', ' + r['published'] if r.get('published') else ''})\n{(r.get('highlight') or '')[:500]}"
                      for r in rows)
    return structured_call(
        OPPORTUNITIES_PROMPT.format(today=today, facts=facts, rows=lines or "(none)",
                                    deadline_months=deadline_months or "unknown"),
        OpportunityNotes, f"sorting {len(rows)} live finds into perks and support")
