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


JOB_LOSS = re.compile(r"\b(laid off|layoff|lay-off|let go|fired|dismiss\w*|terminat\w*|made redundant|redundan\w*|"
                      r"position (was |is )?eliminated|role (was |is )?eliminated|lost (my|the|a) job|"
                      r"job (ended|ends|is ending)|contract (ended|ends|is ending)|unemploy\w*|notice period|"
                      r"last day (at|of) work)\b")


def extract_facts(text: str, today: date) -> dict:
    """Keyword heuristics standing in for Gemini."""
    t = text.lower()
    facts: dict = {"job_was_in_finland": not OUTSIDE_FINLAND.search(t)}
    if JOB_LOSS.search(t):
        facts["lost_job"] = True
    if re.search(r"\b(unemployment fund|työttömyyskassa|kassa|union member)", t):
        facts["unemployment_fund"] = "no" if re.search(r"\b(not|no|never)\b[^.]{0,30}(fund|kassa|union)", t) else "yes"
    if re.search(r"\balready registered\b|\bregistered as (an? )?(unemployed )?jobseeker", t):
        facts["registered_jobseeker"] = "yes"

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
        facts["job_end_date_approximate"] = bool(re.search(r"last (week|month)|weeks? ago|months? ago|few|about|around", t))

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
    final = (f"before {date.fromisoformat(deadline_date).strftime('%-d %B %Y')}" if deadline_date
             else "before the date you can stay until")
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


def saved_perks(city: str | None, city_domains: list[str], topic_ids: list[str]) -> list[dict]:
    """Perks and support when there's no live search (demo mode, or Exa down): careful general pointers, one per
    topic, each linking to an official page. No specific prices, amounts or conditions: those need a live search.
    Cheaper travel is left out because it can't be said in general."""
    where = city or "your city"
    city_url = f"https://www.{city_domains[0]}/" if city_domains else SOURCES["infofinland"]["url"]
    guide = {
        "certificate": ("Proof that you're a registered jobseeker",
                        "Once you've registered as an unemployed jobseeker, you can usually get proof of it. Many discounts ask for it.",
                        "Register on Job Market Finland, then ask the employment services for proof of your jobseeker status.",
                        SOURCES["tyomarkkinatori"]["url"]),
        "discounts": (f"Discounts in {where}",
                      "Many Finnish cities offer lower prices for unemployed jobseekers, for example at swimming halls, "
                      "sports centres or museums. What's offered differs by city.",
                      f"Check {where}'s official website, and bring proof that you're a jobseeker.", city_url),
        "incentives": ("Pay subsidy for employers",
                       "An employer who hires an unemployed jobseeker may be able to get a pay subsidy. The employment "
                       "services decide case by case.",
                       "Mention it to employers, and ask the employment services whether it may apply to you.",
                       SOURCES["tyomarkkinatori"]["url"]),
        "fund_support": ("Earnings-related allowance",
                         "If you're a member of an unemployment fund, the fund may pay an earnings-related allowance while "
                         "you're unemployed.",
                         "Register as a jobseeker first, then apply to your fund.", SOURCES["infofinland"]["url"]),
        "kela_extra": ("Support from Kela",
                       "If you're not in an unemployment fund, Kela may pay basic unemployment support, and you may also "
                       "be able to get other support, such as help with housing costs.",
                       "Register as a jobseeker, then check the conditions and apply on Kela's website.",
                       SOURCES["kela"]["url"]),
        "language_courses": ("Finnish or Swedish courses",
                             "Language courses may be available for unemployed jobseekers who moved to Finland.",
                             "Ask the employment services when you register.", SOURCES["infofinland"]["url"]),
    }
    return [{"topic": t, "name": g[0], "what_it_is": g[1], "how_to_get": g[2], "source_url": g[3]}
            for t in topic_ids if (g := guide.get(t))]

