"""Opportunities: Perks and support. Separate from the steps.

Which topics: plain code picks them from a fixed list (countries/finland.py PERK_TOPICS) using the person's answers,
no AI: the certificate, discounts and employer incentives always, then up to 2 more (unemployment fund, Kela, free
language courses, cheaper travel). Exa finds pages for each topic (cached 24h) on official and city sites. Context.dev then reads the top page for
each perk in full and pulls the exact details with a JSON Schema (the certificate steps, each discount and the proof
needed, each incentive's conditions); those items are marked `read_by: "context.dev"`. Gemini sorts the rest and
judges whether incentives may apply (1 call). Without Context.dev everything comes from Exa + Gemini as before. Plain
code enforces the rules: every item has an Exa source and its page date, the job search certificate comes first,
incentives only "may apply" (never claims eligibility), and incentive conditions that clash with the deadline are
flagged.
"""

from __future__ import annotations

import contextvars
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import activity
from countries.finland import ALWAYS_PERKS, CITY_DOMAINS, MAX_PERK_TOPICS, PERK_TOPICS
from models import (Certificate, Discount, Facts, Incentive, OpportunitiesResponse, PerksAndSupport, PerkTopic,
                    SupportItem)
from questions import canonical_permit
from integrations import context_dev
from services import exa_search, gemini, mocks

MAX_ITEMS = 6  # the UI shows 3 and "Show more"
MAY_APPLY = "May apply, check the conditions."


def _partial(key: str, value) -> None:
    activity.emit({"type": "partial", "key": key, "data": value.model_dump(mode="json")})


def _short(n: dict) -> dict:
    """Gemini's short card text, if it gave any (limits are enforced by the models)."""
    return {"title_short": n.get("title_short") or "", "why_short": n.get("why_short") or ""}


def _deadline_conflict(conditions: str, months: int | None) -> str | None:
    m = re.search(r"\b(\d+|three|six|two)\s+months?\b", conditions.lower())
    if not m or not months:
        return None
    n = {"two": 2, "three": 3, "six": 6}.get(m.group(1)) or int(m.group(1))
    if n >= months:
        return (f"This needs about {n} months of unemployment, but your permit's protection period is {months} "
                "months, so it may not work in time.")
    return None


# ---------- Which topics fit this person (plain rules, no AI) ----------

def perk_topics(f: Facts) -> list[PerkTopic]:
    """The topics to search for this person, in order, each with the reason it was picked."""
    picked: list[tuple[str, str]] = [
        ("certificate", "Shown to everyone: most jobseeker discounts ask for it."),
        ("discounts", f"Shown to everyone{f' in {f.city}' if f.city else ''}."),
        ("incentives", "Shown to everyone: worth mentioning to employers."),
    ]
    fund = f.unemployment_fund
    if fund in ("yes", "not_sure"):
        picked.append(("fund_support", "You said you're in an unemployment fund." if fund == "yes"
                       else "You weren't sure if you're in an unemployment fund."))
    if fund != "yes":
        picked.append(("kela_extra", "You're not in an unemployment fund, so Kela is where most support comes from."
                       if fund == "no" else "Kela support may matter if you're not in an unemployment fund."))
    if canonical_permit(f) in ("work_based", "specialist_blue_card") and f.citizenship_group != "eu_eea":
        picked.append(("language_courses", "You're on a work-based permit: free courses can help you find work in Finland."))
    if f.city:
        picked.append(("travel_discount", f"You live in {f.city}; shown only if a page confirms a discount there."))
    assert [t for t, _ in picked[:3]] == ALWAYS_PERKS
    return [PerkTopic(id=t, title=PERK_TOPICS[t]["title"], label=PERK_TOPICS[t]["label"], reason=why)
            for t, why in picked[:MAX_PERK_TOPICS]]


# ---------- Context.dev: read the top page for each perk and extract the exact details ----------

_TEXT = {"type": ["string", "null"]}
PERK_SCHEMAS = {
    "perks:certificate": {
        "type": "object", "additionalProperties": False,
        "properties": {"how_to_get": {**_TEXT, "description": "How to get proof of being an unemployed jobseeker, in plain steps"}},
    },
    "perks:discounts": {
        "type": "object", "additionalProperties": False, "required": ["discounts"],
        "properties": {"discounts": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["name"],
            "properties": {"name": {"type": "string", "description": "What the discount is for, e.g. swimming halls"},
                           "discount": {**_TEXT, "description": "The price or reduction exactly as the page states it"},
                           "proof_needed": {**_TEXT, "description": "What you must show to get it"}}}}},
    },
    "perks:incentives": {
        "type": "object", "additionalProperties": False, "required": ["incentives"],
        "properties": {"incentives": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["name"],
            "properties": {"name": {"type": "string"},
                           "what_it_is": {**_TEXT, "description": "What the employer gets"},
                           "conditions": {**_TEXT, "description": "Who qualifies, e.g. how long unemployed, exactly as stated"}}}}},
    },
}
# Any other topic (fund, Kela, language courses, travel): the support the page describes.
SUPPORT_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["items"],
    "properties": {"items": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["name"],
        "properties": {"name": {"type": "string", "description": "Name of the support, course or discount"},
                       "what_it_is": {**_TEXT, "description": "What you get, with amounts exactly as stated"},
                       "who_can_get_it": {**_TEXT, "description": "Who qualifies, exactly as stated"},
                       "how_to_get": {**_TEXT, "description": "How to apply or sign up, in plain steps"}}}}},
}
WHAT = {"perks:certificate": "the job search certificate", "perks:discounts": "discounts for unemployed jobseekers",
        "perks:incentives": "hiring incentives an employer can get for hiring an unemployed jobseeker"}


def _what(section: str) -> str:
    return WHAT.get(section) or PERK_TOPICS[section.split(":", 1)[1]]["title"].lower() + " for unemployed jobseekers"


def _schema(section: str) -> dict:
    return PERK_SCHEMAS.get(section, SUPPORT_SCHEMA)


def _instructions(section: str, city: str) -> str:
    return (f"Extract only what this page states about {_what(section)} in {city} or Finland. Keep amounts, "
            "percentages and conditions exactly as written, translated to plain English. Use null when the page "
            "doesn't say. Don't add anything that isn't on the page.")


def _read_with_context(raw: dict, city: str) -> dict[str, dict]:
    """For each perk section, Context.dev reads the top page Exa found. Returns {section: {row, data}}."""
    if not context_dev.available():
        return {}
    tops = {s: rows[0] for s, rows in raw.items() if s.startswith("perks:") and rows and rows[0].get("url")}

    def one(item):
        section, top = item
        return section, top, context_dev.extract_json(top["url"], _schema(section), _instructions(section, city),
                                                      purpose=_what(section))
    with ThreadPoolExecutor(max_workers=MAX_PERK_TOPICS) as pool:
        done = list(pool.map(lambda it: contextvars.copy_context().run(one, it), tops.items()))
    return {s: {"row": top, "data": data} for s, top, data in done if data}


def build(f: Facts, deadline_months: int | None, today: date | None = None) -> OpportunitiesResponse:
    today = today or date.today()
    field, city = f.field or "professional", f.city or "Helsinki"
    topics = perk_topics(f)
    raw = exa_search.search_opportunities(field, city, today.isoformat(), CITY_DOMAINS.get(city.lower(), []),
                                          {t.id: PERK_TOPICS[t.id]["query"] for t in topics})
    if not raw:
        # No live search (demo mode, or Exa down): careful general pointers to the official pages, never specifics.
        saved = [SupportItem(**x) for x in mocks.saved_perks(f.city, CITY_DOMAINS.get(city.lower(), []), [t.id for t in topics])]
        return OpportunitiesResponse(perks_and_support=PerksAndSupport(topics=topics, support=saved), mock=True)

    read = _read_with_context(raw, city)
    read_urls = {v["row"]["url"] for v in read.values()}
    rows = []
    for section, items in raw.items():
        for r in items:
            row_ = {**r, "id": f"R{len(rows) + 1}", "section": section}
            if section in read and r.get("url") == read[section]["row"]["url"]:
                # Gemini judges incentives from the whole page's details, not just the search snippet.
                row_["highlight"] = "Read from the page by Context.dev: " + json.dumps(read[section]["data"], ensure_ascii=False)[:1500]
            rows.append(row_)
    by_id = {r["id"]: r for r in rows}
    notes = gemini.write_opportunities(f.model_dump(mode="json"), deadline_months, rows, today.isoformat()) or {}

    def row(n):
        return by_id.get(n.get("row_id") or "")

    perks = PerksAndSupport(topics=topics)
    cert_name = "Job search certificate (proof you're a jobseeker)"
    if (c := read.get("perks:certificate")) and (how := (c["data"].get("how_to_get") or "").strip()):
        perks.certificate = Certificate(name=cert_name, how_to_get=how, source_url=c["row"]["url"],
                                        source_date=c["row"].get("published"), read_by="context.dev")
    elif (c := notes.get("certificate")) and (r := row(c)) and r["section"] == "perks:certificate":
        perks.certificate = Certificate(name=cert_name, how_to_get=c["how_to_get"],
                                        source_url=r["url"], source_date=r.get("published"))

    # Discounts Context.dev read straight from the page come first (only ones with a stated discount).
    exact = read.get("perks:discounts")
    discounts = [Discount(name=d["name"], discount=d["discount"], proof_needed=d.get("proof_needed") or "Not stated on the page",
                          city=city, source_url=exact["row"]["url"], source_date=exact["row"].get("published"),
                          read_by="context.dev")
                 for d in (exact["data"].get("discounts") or [] if exact else [])
                 if isinstance(d, dict) and d.get("name") and d.get("discount")]
    seen = {d.name.lower() for d in discounts}
    discounts += [Discount(name=n["name"], discount=n["discount"], proof_needed=n["proof_needed"], city=city,
                           source_url=r["url"], source_date=r.get("published"),
                           read_by="context.dev" if r["url"] in read_urls else None, **_short(n))
                  for n in notes.get("discounts", [])
                  if (r := row(n)) and r["section"].startswith("perks:") and n["name"].lower() not in seen]
    perks.discounts = discounts[:MAX_ITEMS]
    for n in notes.get("incentives", []):
        r = row(n)
        if not (r and r["section"].startswith("perks:")):
            continue
        caveat = _deadline_conflict(n["conditions_plain"], deadline_months) or n.get("caveat") or MAY_APPLY
        perks.incentives.append(Incentive(name=n["name"], what_it_is=n["what_it_is"], conditions_plain=n["conditions_plain"],
                                          may_apply=bool(n.get("may_apply")), caveat=caveat,
                                          source_url=r["url"], source_date=r.get("published"),
                                          read_by="context.dev" if r["url"] in read_urls else None,
                                          title_short=n.get("title_short") or ""))  # why_short: from the caveat
    perks.incentives = perks.incentives[:MAX_ITEMS]

    # The other topics: support Context.dev read from the page first, then Gemini's from the search results.
    support: list[SupportItem] = []
    for t in topics[3:]:
        section = f"perks:{t.id}"
        if (got := read.get(section)):
            support += [SupportItem(topic=t.id, name=i["name"], what_it_is=i.get("what_it_is") or "",
                                    how_to_get=i.get("how_to_get"), who_can_get_it=i.get("who_can_get_it"),
                                    source_url=got["row"]["url"], source_date=got["row"].get("published"),
                                    read_by="context.dev")
                        for i in got["data"].get("items") or [] if isinstance(i, dict) and i.get("name") and i.get("what_it_is")][:3]
        else:
            support += [SupportItem(topic=t.id, name=n["name"], what_it_is=n["what_it_is"], how_to_get=n.get("how_to_get"),
                                    who_can_get_it=n.get("who_can_get_it"), source_url=r["url"],
                                    source_date=r.get("published"), **_short(n))
                        for n in notes.get("support", []) if (r := row(n)) and r["section"] == section][:3]
    perks.support = support
    _partial("perks_and_support", perks)

    return OpportunitiesResponse(perks_and_support=perks, mock=not (notes or read))
