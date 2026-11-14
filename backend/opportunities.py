"""Opportunities: Perks and support. Separate from the roadmap.

Exa finds (3 searches per city, cached 24h) on official and city sites. Context.dev then reads the top page for
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
from countries.finland import CITY_DOMAINS, PERK_QUERIES
from models import Certificate, Discount, Facts, Incentive, OpportunitiesResponse, PerksAndSupport
from integrations import context_dev
from services import exa_search, gemini

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
WHAT = {"perks:certificate": "the job search certificate", "perks:discounts": "discounts for unemployed jobseekers",
        "perks:incentives": "hiring incentives an employer can get for hiring an unemployed jobseeker"}


def _instructions(section: str, city: str) -> str:
    return (f"Extract only what this page states about {WHAT[section]} in {city} or Finland. Keep amounts, "
            "percentages and conditions exactly as written, translated to plain English. Use null when the page "
            "doesn't say. Don't add anything that isn't on the page.")


def _read_with_context(raw: dict, city: str) -> dict[str, dict]:
    """For each perk section, Context.dev reads the top page Exa found. Returns {section: {row, data}}."""
    if not context_dev.available():
        return {}
    tops = {s: rows[0] for s, rows in raw.items() if s in PERK_SCHEMAS and rows and rows[0].get("url")}

    def one(item):
        section, top = item
        return section, top, context_dev.extract_json(top["url"], PERK_SCHEMAS[section], _instructions(section, city),
                                                      purpose=WHAT[section])
    with ThreadPoolExecutor(max_workers=3) as pool:
        done = list(pool.map(lambda it: contextvars.copy_context().run(one, it), tops.items()))
    return {s: {"row": top, "data": data} for s, top, data in done if data}


def build(f: Facts, deadline_months: int | None, today: date | None = None) -> OpportunitiesResponse:
    today = today or date.today()
    field, city = f.field or "professional", f.city or "Helsinki"
    raw = exa_search.search_opportunities(field, city, today.isoformat(), CITY_DOMAINS.get(city.lower(), []),
                                          PERK_QUERIES)
    if not raw:
        return OpportunitiesResponse(mock=True)  # never invent opportunities

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

    perks = PerksAndSupport()
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
    _partial("perks_and_support", perks)

    return OpportunitiesResponse(perks_and_support=perks, mock=not (notes or read))
