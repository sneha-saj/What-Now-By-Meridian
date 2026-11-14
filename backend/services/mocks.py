"""Mock data used when API keys are missing or a call fails. Keeps the demo always runnable.

TODO: verify every URL below before the demo.
"""

import re
import json
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

_EXAMPLES = json.loads(Path(__file__).with_name("mock_responses.json").read_text())


def example_facts() -> dict:
    return deepcopy(_EXAMPLES["intake_facts"])


def example_sources() -> list[dict]:
    return deepcopy(_EXAMPLES["official_sources"])


def example_steps() -> list[dict]:
    return deepcopy(_EXAMPLES["steps"])


def example_referrals() -> tuple[list[dict], list[str]]:
    return deepcopy(_EXAMPLES["referrals"]), list(_EXAMPLES["messages"])

SOURCES = {
    "migri": {"title": "Migri – Finnish Immigration Service", "url": "https://migri.fi/en/home"},
    "kela": {"title": "Kela – Unemployment", "url": "https://www.kela.fi/unemployment"},
    "infofinland": {"title": "InfoFinland – Unemployment",
                    "url": "https://www.infofinland.fi/en/work-and-enterprise/unemployment"},
    "tyomarkkinatori": {"title": "Job Market Finland (Työmarkkinatori)", "url": "https://tyomarkkinatori.fi/en"},
}


def extract_facts(text: str, today: date) -> dict:
    """Keyword heuristics standing in for Gemini."""
    t = text.lower()
    facts: dict = {}

    if re.search(r"\b(eu citizen|from (germany|france|spain|italy|estonia|sweden|poland))\b", t):
        facts["citizenship"] = "eu"
    elif "finnish citizen" in t:
        facts["citizenship"] = "finnish"
    elif re.search(r"\b(permit|visa|blue card|from (india|china|nepal|vietnam|nigeria|brazil|usa|ukraine|russia|pakistan|philippines|bangladesh))\b", t):
        facts["citizenship"] = "non_eu"

    for pat, val in [(r"blue card", "eu_blue_card"), (r"specialist", "specialist"),
                     (r"student", "student"), (r"family|spouse", "family"),
                     (r"permanent", "permanent"), (r"work(-based)? permit|work visa", "work")]:
        if re.search(pat, t):
            facts["permit_type"] = val
            break

    if m := re.search(r"\d{4}-\d{2}-\d{2}", t):
        facts["job_end_date"] = m.group(0)
    elif "yesterday" in t:
        facts["job_end_date"] = (today - timedelta(days=1)).isoformat()
    elif "today" in t:
        facts["job_end_date"] = today.isoformat()
    elif "last week" in t:
        facts["job_end_date"] = (today - timedelta(days=7)).isoformat()

    if m := re.search(r"(\d+)\s+years?", t):
        facts["over_two_years_on_work_permit"] = int(m.group(1)) > 2

    for city in ("helsinki", "espoo", "vantaa", "tampere", "turku", "oulu", "jyväskylä", "lahti"):
        if city in t:
            facts["city"] = city.title()

    if m := re.search(r"\bas an? ([a-z ]+?)(?:\s+(?:in|at|for)\b|[,.]|$)", t):
        facts["occupation"] = m.group(1).strip()

    return facts


def steps(deadline_status: str) -> list[dict]:
    first = (
        {"title": "Check your permit date with Migri",
         "detail": "Log in to Enter Finland and note your permit's end date. "
                   "If you're unsure what applies to you, Migri's advice line can confirm.",
         "sources": [SOURCES["migri"]]}
        if deadline_status in ("ok", "needs_info", "unsupported") else
        {"title": "Your stay isn't at risk — focus on income",
         "detail": "Your right to stay doesn't depend on this job. Put this week into money and job search.",
         "sources": [SOURCES["infofinland"]]}
    )
    return [
        first,
        {"title": "Register as a jobseeker",
         "detail": "Register on Job Market Finland as soon as possible. "
                   "Unemployment benefits usually depend on this registration.",
         "sources": [SOURCES["tyomarkkinatori"], SOURCES["infofinland"]]},
        {"title": "Check what Kela can pay you",
         "detail": "See whether you can get unemployment benefit or other support from Kela, "
                   "or an earnings-related allowance from your unemployment fund if you belong to one.",
         "sources": [SOURCES["kela"], SOURCES["infofinland"]]},
    ]


def referrals(occupation: str, city: str) -> list[dict]:
    return [
        {"name": "International House advisors", "role": "Guidance for internationals",
         "organization": f"International House {city}" if city == "Helsinki" else "International House Helsinki",
         "why": "Free in-person advice on permits, Kela and job search in English.",
         "source": {"title": "International House Helsinki", "url": "https://www.ihhelsinki.fi/"}},
        {"name": "Talent Boost team", "role": "International talent services",
         "organization": "Work in Finland",
         "why": f"Connects international {occupation}s with Finnish employers.",
         "source": {"title": "Work in Finland", "url": "https://www.workinfinland.com/"}},
        {"name": "Example Recruiter (mock)", "role": f"Recruiter, {occupation}",
         "organization": f"Example Oy, {city}",
         "why": "Placeholder until Exa people search is wired up.",
         "source": {"title": "Job Market Finland", "url": "https://tyomarkkinatori.fi/en"}},
    ]


def message(contact: dict, occupation: str) -> str:
    return (
        f"Hi {contact['name']},\n\n"
        f"I'm a {occupation} based in Finland and I'm currently looking for my next role. "
        f"I saw that {contact['organization']} {contact['why'][0].lower() + contact['why'][1:]} "
        "Would you have 15 minutes for a short chat, or could you point me to the right person?\n\n"
        "Thank you,\n[Your name]"
    )
