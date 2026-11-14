"""Gemini calls. Each function returns None on missing key / failure so callers fall back to mocks."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from pydantic import BaseModel

import config

log = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    key = config.gemini_key()
    if not key:
        return None
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=key)
    return _client


def available() -> bool:
    return bool(config.gemini_key())


def _call(prompt: str, schema: Any = None) -> Any | None:
    """Ask Gemini for JSON. With a Pydantic `schema`, uses structured output."""
    client = _get_client()
    if client is None:
        return None
    try:
        from google.genai import types

        cfg = {"response_mime_type": "application/json", "temperature": 0.2}
        if schema is not None:
            cfg["response_schema"] = schema
        resp = client.models.generate_content(
            model=config.GEMINI_MODEL, contents=prompt, config=types.GenerateContentConfig(**cfg)
        )
        parsed = getattr(resp, "parsed", None)
        if isinstance(parsed, BaseModel):
            return parsed.model_dump()
        return json.loads(resp.text)
    except Exception as e:  # noqa: BLE001 - demo resilience: never crash the UI
        log.warning("Gemini call failed, using mock: %s", e)
        return None


def structured_call(prompt: str, schema: type[BaseModel]) -> dict | None:
    out = _call(prompt, schema)
    return out if isinstance(out, dict) else None


def _json_call(prompt: str) -> Any | None:
    return _call(prompt)


# ---------- /intake ----------

class Extracted(BaseModel):
    job_was_in_finland: Optional[bool] = None
    citizenship_group: Optional[str] = None
    citizenship_country: Optional[str] = None
    permit_type: Optional[str] = None
    years_on_work_permit: Optional[float] = None
    job_end_date: Optional[str] = None
    city: Optional[str] = None
    field: Optional[str] = None
    studied_in_finland: Optional[bool] = None
    family_in_finland: Optional[bool] = None


EXTRACT_PROMPT = """You read a short message from someone who lost (or is losing) their job and extract facts.
Use null whenever something is not stated or unclear. Never guess. Today is {today}.
- job_was_in_finland: false only if they clearly say the job was outside Finland
- citizenship_group: "eu_eea" (EU/EEA/Swiss citizen) | "other" (any other country) | "unknown"
- citizenship_country: country name in English
- permit_type: one of {permit_ids}
- years_on_work_permit: total years on a work-based permit in Finland, as a number
- job_end_date: last day of work as YYYY-MM-DD (resolve "yesterday", "last Friday" etc. from today)
- city: city in Finland
- field: their job or industry, short, in English
- studied_in_finland, family_in_finland: true/false if stated
Do not extract permit numbers, passport numbers, ID numbers, names or addresses.

Message: {text!r}"""


def extract_facts(text: str, today: str) -> dict | None:
    from countries.finland import PERMIT_TYPES

    ids = ", ".join(f'"{p["id"]}"' for p in PERMIT_TYPES)
    return structured_call(EXTRACT_PROMPT.format(text=text, today=today, permit_ids=ids), Extracted)


# ---------- /plan ----------

class _Action(BaseModel):
    title: str
    why: str
    how: list[str]
    source_ids: list[str]


class _Week(BaseModel):
    week: str
    steps: list[str]
    source_ids: list[str]


class _PlanB(BaseModel):
    option: str
    why: str
    latest_start_date: Optional[str] = None
    source_ids: list[str]


class GeneratedPlan(BaseModel):
    this_week: list[_Action]
    timeline: list[_Week]
    plan_b: list[_PlanB]


PLAN_PROMPT = """You help a worried person in Finland who has lost their job. Be calm, plain and specific.

Use ONLY facts from the SOURCES below. Do not use outside knowledge. Cite sources by id.
If the sources do not cover something they need, write "Check with Migri or your union" instead of guessing.
The deadline below was computed by our rules engine: do not change it or invent another date.

Write:
1. this_week: exactly 3 actions, most urgent first. Each has a title, why (one calm sentence),
   how (2-4 short steps) and source_ids (at least one).
2. timeline: steps working back from the deadline, with week labels "Week 1", "Week 2", "Week 4",
   "Week 8" and "Final weeks". Skip weeks that fall after the deadline. Each has steps and source_ids.
3. plan_b: alternatives if no new job is found in time (for example another permit type), each with
   why, latest_start_date (YYYY-MM-DD, or null if the sources don't support a date) and source_ids.

Person: {facts}
Deadline: {deadline}
Today: {today}

SOURCES:
{sources}"""


def write_plan(facts: dict, deadline: dict, sources: list[dict], today: str) -> dict | None:
    src = "\n\n".join(
        f"[{s['id']}] {s['title']} ({s['url']})\n{(s.get('highlight') or '')[:1000]}" for s in sources
    )
    return structured_call(
        PLAN_PROMPT.format(facts=facts, deadline=deadline, today=today, sources=src), GeneratedPlan
    )


# ---------- /referrals ----------

class _CompanyNote(BaseModel):
    id: str
    why_relevant: str


class _CommunityNote(BaseModel):
    id: str
    type: str
    date_if_event: Optional[str] = None


class _Draft(BaseModel):
    id: str
    why_this_person: str
    message: str


class ReferralNotes(BaseModel):
    companies: list[_CompanyNote]
    communities: list[_CommunityNote]
    drafts: list[_Draft]


REFERRALS_PROMPT = """You help a job seeker in Finland reach out to companies and people. Use ONLY the details below.
Today is {today}.

1. companies: for each company id, why_relevant: one sentence on why it fits this person, based on its highlight.
2. communities: for each community id, type: "professional_group" | "event" | "union", and date_if_event
   (YYYY-MM-DD) only if the highlight states a date within the next 30 days, else null.
3. drafts: for each contact id, why_this_person (one sentence) and message: a short, polite, personal message
   (max 80 words) from the job seeker. Mention exactly one real detail from that contact's or company's
   highlight. No exaggeration, no attachments, end with "[Your name]". These are drafts; nothing is sent.

Job seeker: {facts}

COMPANIES:
{companies}

CONTACTS:
{contacts}

COMMUNITIES:
{communities}"""


def write_referral_notes(facts: dict, companies: list[dict], contacts: list[dict], communities: list[dict],
                         today: str) -> dict | None:
    def lines(items, fields):
        return "\n".join(f"[{x['id']}] " + " | ".join(str(x.get(f) or "") for f in fields) for x in items) or "(none)"

    prompt = REFERRALS_PROMPT.format(
        today=today, facts=facts,
        companies=lines(companies, ("name", "url", "highlight")),
        contacts=lines(contacts, ("name", "role", "company", "highlight")),
        communities=lines(communities, ("name", "url", "highlight")),
    )
    return structured_call(prompt, ReferralNotes)
