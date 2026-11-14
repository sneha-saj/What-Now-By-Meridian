"""Mock data used when API keys are missing or a call fails. Keeps the demo always runnable.

TODO: verify every URL below before the demo.
"""

import re
import json
from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "mocks"


def example(name: str) -> dict:
    """Saved example response (persona: restaurant worker from India, 1 year on a work permit, Helsinki).

    Used when USE_MOCK=true and documented in docs/api.md.
    """
    return deepcopy(json.loads((EXAMPLES_DIR / f"{name}.json").read_text(encoding="utf-8"))["response"])


def example_facts() -> dict:
    return example("intake")["facts"]


def example_referrals() -> dict:
    out = example("referrals")
    out.pop("mock", None)
    return out

SOURCES = {
    "migri": {"title": "Migri – Finnish Immigration Service", "url": "https://migri.fi/en/home"},
    "kela": {"title": "Kela – Unemployment", "url": "https://www.kela.fi/unemployment"},
    "infofinland": {"title": "InfoFinland – Unemployment",
                    "url": "https://www.infofinland.fi/en/work-and-enterprise/unemployment"},
    "tyomarkkinatori": {"title": "Job Market Finland (Työmarkkinatori)", "url": "https://tyomarkkinatori.fi/en"},
}


OUTSIDE_FINLAND = re.compile(
    r"\b(?:job|work(?:ed|ing)?|employ\w*)\b[^.]*\b(?:in|at)\s+(?:the\s+)?"
    r"(germany|sweden|estonia|norway|denmark|uk|united kingdom|usa|united states|india|china|spain|france|"
    r"netherlands|poland|italy|canada|australia)\b|outside finland"
)
EU_COUNTRIES = ("germany", "france", "spain", "italy", "estonia", "sweden", "poland", "netherlands",
                "denmark", "latvia", "lithuania", "portugal", "romania", "greece", "ireland", "norway")
OTHER_COUNTRIES = ("india", "china", "nepal", "vietnam", "nigeria", "brazil", "usa", "ukraine", "russia",
                   "pakistan", "philippines", "bangladesh", "iran", "turkey", "egypt", "kenya")


MONTHS = {m: i + 1 for i, m in enumerate(
    ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
     "november", "december"))}
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
NUMBERS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}


def job_end_date(t: str, today: date) -> date | None:
    """Resolve the last day of work from text, relative to today. None if unsure (then we ask)."""
    t = t.lower()
    if m := re.search(r"\d{4}-\d{2}-\d{2}", t):
        return date.fromisoformat(m.group(0))
    if "yesterday" in t:
        return today - timedelta(days=1)
    if "today" in t:
        return today
    if m := re.search(r"\b(\d+|a|an|one|two|three|four|five|six) (day|week|month)s? ago\b", t):
        n = int(m.group(1)) if m.group(1).isdigit() else NUMBERS[m.group(1)]
        return today - timedelta(days=n * {"day": 1, "week": 7, "month": 30}[m.group(2)])
    if "last week" in t:
        return today - timedelta(days=7)
    if "last month" in t:
        return today - timedelta(days=30)
    if m := re.search(r"\blast (" + "|".join(WEEKDAYS) + r")\b", t):
        back = (today.weekday() - WEEKDAYS.index(m.group(1))) % 7 or 7
        return today - timedelta(days=back)
    month_names = "|".join(MONTHS)
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)? (" + month_names + r")\b", t) or \
        re.search(r"\b(" + month_names + r") (\d{1,2})(?:st|nd|rd|th)?\b", t)
    if m:
        a, b = m.groups()
        day, month = (int(a), MONTHS[b]) if a.isdigit() else (int(b), MONTHS[a])
        try:
            d = date(today.year, month, day)
        except ValueError:
            return None
        return d if d <= today + timedelta(days=60) else date(today.year - 1, month, day)  # notice periods allowed
    return None


def extract_facts(text: str, today: date) -> dict:
    """Keyword heuristics standing in for Gemini."""
    t = text.lower()
    facts: dict = {"job_was_in_finland": not OUTSIDE_FINLAND.search(t)}

    if m := re.search(r"\bfrom (" + "|".join(EU_COUNTRIES) + r")\b", t):
        facts.update(citizenship_group="eu_eea", citizenship_country=m.group(1).title())
    elif "eu citizen" in t:
        facts["citizenship_group"] = "eu_eea"
    elif m := re.search(r"\bfrom (" + "|".join(OTHER_COUNTRIES) + r")\b", t):
        facts.update(citizenship_group="other", citizenship_country=m.group(1).title())

    for pat, val in [(r"blue card|specialist", "specialist_blue_card"), (r"student", "student"),
                     (r"family|spouse", "family_based"), (r"permanent", "permanent"),
                     (r"work(-based)? permit|work visa", "work_based")]:
        if re.search(pat, t):
            facts["permit_type"] = val
            break

    if (end := job_end_date(t, today)) is not None:
        facts["job_end_date"] = end.isoformat()

    if m := re.search(r"(\d+(?:\.\d+)?)\s+years?", t):
        facts["years_on_work_permit"] = float(m.group(1))

    for city in ("helsinki", "espoo", "vantaa", "tampere", "turku", "oulu", "jyväskylä", "lahti"):
        if city in t:
            facts["city"] = city.title()

    if m := re.search(r"\bas an? ([a-z ]+?)(?:\s+(?:in|at|for)\b|[,.]|$)", t):
        facts["field"] = m.group(1).strip()
    if re.search(r"studied in finland|graduated in finland|finnish (university|degree)", t):
        facts["studied_in_finland"] = True
    return facts


def plan(deadline_date: str | None) -> dict:
    """Generic plan used when Exa or Gemini is unavailable. Sources are official landing pages, no quotes."""
    m, k, i, t = SOURCES["migri"], SOURCES["kela"], SOURCES["infofinland"], SOURCES["tyomarkkinatori"]
    final = f"before {deadline_date}" if deadline_date else "before your deadline"
    return {
        "this_week": [
            {"title": "Register as a jobseeker", "why": "Registering early keeps your benefit options open.",
             "how": ["Go to Job Market Finland (Työmarkkinatori)", "Register as an unemployed jobseeker"],
             "sources": [t, i]},
            {"title": "Check what support you can get", "why": "Money worries are easier with a clear picture.",
             "how": ["Read Kela's unemployment page", "Ask your unemployment fund if you belong to one"],
             "sources": [k, i]},
            {"title": "Confirm your permit situation", "why": "Knowing your exact date lets you plan calmly.",
             "how": ["Check your permit details with Migri", "If anything is unclear, check with Migri or your union"],
             "sources": [m]},
        ],
        "timeline": [
            {"week": "Week 1", "steps": ["Register as a jobseeker", "Check benefit options"], "sources": [t, k]},
            {"week": "Week 2", "steps": ["Update your CV and apply for open roles"], "sources": [t]},
            {"week": "Week 4", "steps": ["Review your options with Migri or your union"], "sources": [m]},
            {"week": "Final weeks", "steps": [f"Apply for a new permit {final} if you have a new job offer"],
             "sources": [m]},
        ],
        "plan_b": [
            {"option": "Another residence permit", "why": "Another permit type may fit your situation; check with Migri or your union.",
             "latest_start_date": None, "sources": [m, i]},
        ],
    }


def referrals(city: str) -> dict:
    """No Exa: point to real, official help services only. No invented companies or people."""
    ih = "International House Helsinki"
    return {
        "companies": [],
        "contacts": [],
        "communities": [
            {"name": ih, "type": "professional_group", "url": "https://www.ihhelsinki.fi/"},
            {"name": "Work in Finland", "type": "professional_group", "url": "https://www.workinfinland.com/"},
        ],
        "drafts": [],
    }
