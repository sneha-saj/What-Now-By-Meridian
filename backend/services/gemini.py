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

DRAFT_PROMPT = """Draft a short, warm, specific message (max 80 words) from a job seeker in Finland to each contact below.
The sender: {facts}. They recently lost their job and are looking for a new role in Finland.
Be honest, not desperate. Mention why this contact is relevant. No placeholders except [Your name].

Contacts:
{contacts}

Return JSON: {{"messages": [str, ...]}} in the same order as the contacts."""


def draft_messages(facts: dict, contacts: list[dict]) -> list[str] | None:
    lines = "\n".join(
        f"{i + 1}. {c['name']} – {c['role']} at {c['organization']} ({c['why']})"
        for i, c in enumerate(contacts)
    )
    out = _json_call(DRAFT_PROMPT.format(facts=facts, contacts=lines))
    msgs = out.get("messages") if isinstance(out, dict) else None
    return msgs if isinstance(msgs, list) and len(msgs) == len(contacts) else None
