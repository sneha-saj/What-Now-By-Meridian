"""Opportunities: hidden jobs, people, support, events, perks. Separate from the roadmap.

Exa finds (about 11 searches per city+field, cached 24h), Gemini sorts and writes (2 calls), plain code enforces
the rules: every item has an Exa source, hiring signals are from the last 60 days, events are in the next 30 days,
support "may apply" (never claims eligibility), and incentive conditions that clash with the deadline are flagged.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import activity
from countries.finland import CITY_DOMAINS, PERK_QUERIES, SUPPORT_TYPES
from models import (Certificate, Discount, EventItem, Facts, HiddenJob, Incentive, OppContact,
                    OpportunitiesResponse, PerksAndSupport, SupportItem)
from services import exa_search, gemini

MAX_ITEMS = 6  # the UI shows 3 and "Show more"
MAY_APPLY = "May apply, check the conditions."
MAX_DRAFT_WORDS = 80


def _partial(key: str, value) -> None:
    data = value.model_dump(mode="json") if hasattr(value, "model_dump") else [v.model_dump(mode="json") for v in value]
    activity.emit({"type": "partial", "key": key, "data": data})


def _template_draft(c: dict, field: str) -> str:
    return (f"Hi {c['name']}, I'm a {field} in Finland and saw that {c['company']} is growing. I'd really value a "
            "short chat about your team or a pointer to the right person. Thank you! [Your name]")


def _deadline_conflict(conditions: str, months: int | None) -> str | None:
    m = re.search(r"\b(\d+|three|six|two)\s+months?\b", conditions.lower())
    if not m or not months:
        return None
    n = {"two": 2, "three": 3, "six": 6}.get(m.group(1)) or int(m.group(1))
    if n >= months:
        return (f"This needs about {n} months of unemployment, but your permit's protection period is {months} "
                "months, so it may not work in time.")
    return None


def build(f: Facts, deadline_months: int | None, today: date | None = None) -> OpportunitiesResponse:
    today = today or date.today()
    field, city = f.field or "professional", f.city or "Helsinki"
    raw = exa_search.search_opportunities(field, city, today.isoformat(), CITY_DOMAINS.get(city.lower(), []),
                                          SUPPORT_TYPES, PERK_QUERIES)
    if not raw:
        return OpportunitiesResponse(mock=True)  # never invent opportunities

    rows = []
    for section, items in raw.items():
        for r in items:
            rows.append({**r, "id": f"R{len(rows) + 1}", "section": section})
    by_id = {r["id"]: r for r in rows}
    notes = gemini.write_opportunities(f.model_dump(mode="json"), deadline_months, rows, today.isoformat()) or {}

    def row(n):
        return by_id.get(n.get("row_id") or "")

    since, until = today - timedelta(days=60), today + timedelta(days=30)
    hidden = []
    for n in notes.get("hidden_jobs", []):
        r = row(n)
        if r and r["section"] == "hidden_jobs" and r.get("published") and date.fromisoformat(r["published"]) >= since:
            hidden.append(HiddenJob(company=n["company"], signal=n["signal"], signal_date=r["published"],
                                    source_url=r["url"], why_it_fits=n["why_it_fits"]))
    hidden = hidden[:MAX_ITEMS]
    _partial("hidden_jobs", hidden)

    support = [SupportItem(name=n["name"], what_it_is=n["what_it_is"], why_it_may_apply=n["why_it_may_apply"],
                           eligibility_note=MAY_APPLY, source_url=r["url"], source_date=r.get("published"))
               for n in notes.get("support", []) if n.get("plausible") and (r := row(n)) and r["section"].startswith("support:")]
    support = support[:MAX_ITEMS]
    _partial("support", support)

    events = []
    for n in notes.get("events", []):
        r = row(n)
        try:
            when = date.fromisoformat(n.get("date") or "")
        except ValueError:
            continue  # no stated date, no event
        if r and r["section"] == "events" and today <= when <= until:
            events.append(EventItem(name=n["name"], date=when.isoformat(), place=n.get("place"), url=r["url"],
                                    why_relevant=n["why_relevant"]))
    events = sorted(events, key=lambda e: e.date)[:MAX_ITEMS]
    _partial("events", events)

    perks = PerksAndSupport()
    if (c := notes.get("certificate")) and (r := row(c)) and r["section"] == "perks:certificate":
        perks.certificate = Certificate(name="Job search certificate (proof you're a jobseeker)", how_to_get=c["how_to_get"],
                                        source_url=r["url"], source_date=r.get("published"))
    perks.discounts = [Discount(name=n["name"], discount=n["discount"], proof_needed=n["proof_needed"], city=city,
                                source_url=r["url"], source_date=r.get("published"))
                       for n in notes.get("discounts", []) if (r := row(n)) and r["section"].startswith("perks:")][:MAX_ITEMS]
    for n in notes.get("incentives", []):
        r = row(n)
        if not (r and r["section"].startswith("perks:")):
            continue
        caveat = _deadline_conflict(n["conditions_plain"], deadline_months) or n.get("caveat") or MAY_APPLY
        perks.incentives.append(Incentive(name=n["name"], what_it_is=n["what_it_is"], conditions_plain=n["conditions_plain"],
                                          may_apply=bool(n.get("may_apply")), caveat=caveat,
                                          source_url=r["url"], source_date=r.get("published")))
    perks.incentives = perks.incentives[:MAX_ITEMS]
    _partial("perks_and_support", perks)

    # People at the top companies with hiring signals, with a drafted message each.
    people = []
    top = [{"name": h.company, "signal": h.signal} for h in hidden[:2]]
    found = exa_search.search_people(top, field, city, top=2, per_company=1) if top else None
    if found:
        signals = {t["name"]: t["signal"] for t in top}
        contacts = [{**p, "id": f"P{i + 1}", "signal": signals.get(p["company"], "")} for i, p in enumerate(found[:3])]
        incentive = next((i.name for i in perks.incentives if i.may_apply), None)
        drafts = {d["id"]: d for d in (gemini.write_contact_drafts(f.model_dump(mode="json"), contacts, incentive) or {}).get("drafts", [])}
        for c in contacts:
            d = drafts.get(c["id"], {})
            msg = d.get("message") or ""
            if not msg or len(msg.split()) > MAX_DRAFT_WORDS:
                msg = _template_draft(c, field)
            people.append(OppContact(name=c["name"], role=c["role"] or "Professional", company=c["company"],
                                     why_this_person=d.get("why_this_person") or f"Works at {c['company']}.",
                                     profile_url=c["profile_url"], draft=msg))
    _partial("people", people)

    return OpportunitiesResponse(hidden_jobs=hidden, people=people, support=support, events=events,
                                 perks_and_support=perks, mock=not notes)
