"""Gemini calls. Each function returns None on missing key / failure so callers fall back to mocks."""

from __future__ import annotations

import json
import logging
from typing import Any

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


def _json_call(prompt: str) -> Any | None:
    client = _get_client()
    if client is None:
        return None
    try:
        from google.genai import types

        resp = client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", temperature=0.2
            ),
        )
        return json.loads(resp.text)
    except Exception as e:  # noqa: BLE001 - demo resilience: never crash the UI
        log.warning("Gemini call failed, using mock: %s", e)
        return None


EXTRACT_PROMPT = """You extract facts from one sentence written by a person in Finland who just lost their job.
Return JSON with exactly these keys (use null when not stated or unclear; never guess):
- citizenship: "finnish" | "eu" | "non_eu" | null
- permit_type: "work" | "specialist" | "eu_blue_card" | "student" | "family" | "permanent" | "other" | null
- job_end_date: ISO date "YYYY-MM-DD" | null   (today is {today})
- over_two_years_on_work_permit: true | false | null
- occupation: short job title in English | null
- city: city in Finland | null

Sentence: {text!r}"""


def extract_facts(text: str, today: str) -> dict | None:
    return _json_call(EXTRACT_PROMPT.format(text=text, today=today))


STEPS_PROMPT = """You help a stressed non-EU worker in Finland who just lost their job.
Write exactly 3 things they should do THIS WEEK, most urgent first.
Rules:
- Plain language, short sentences, calm tone. No legal jargon. Max 2 sentences per detail.
- Only state facts supported by the SOURCES below. Cite them by id.
- Every step must cite at least one source id.

Person: {facts}
Deadline (computed by rules, do not change it): {deadline}

SOURCES:
{sources}

Return JSON: {{"steps": [{{"title": str, "detail": str, "source_ids": [str]}}]}}"""


def write_steps(facts: dict, deadline: dict, sources: list[dict]) -> list[dict] | None:
    src = "\n".join(
        f"[{s['id']}] {s['title']} ({s['url']})\n{(s.get('snippet') or '')[:800]}" for s in sources
    )
    out = _json_call(STEPS_PROMPT.format(facts=facts, deadline=deadline, sources=src))
    return out.get("steps") if isinstance(out, dict) else None


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
