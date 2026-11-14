"""Opportunities: Perks and support. Separate from the roadmap.

Exa finds (3 searches per city, cached 24h) on official and city sites, Gemini sorts and writes (1 call), plain
code enforces the rules: every item has an Exa source and its page date, the job search certificate comes first,
incentives only "may apply" (never claims eligibility), and incentive conditions that clash with the deadline are
flagged.
"""

from __future__ import annotations

import re
from datetime import date

import activity
from countries.finland import CITY_DOMAINS, PERK_QUERIES
from models import Certificate, Discount, Facts, Incentive, OpportunitiesResponse, PerksAndSupport
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


def build(f: Facts, deadline_months: int | None, today: date | None = None) -> OpportunitiesResponse:
    today = today or date.today()
    field, city = f.field or "professional", f.city or "Helsinki"
    raw = exa_search.search_opportunities(field, city, today.isoformat(), CITY_DOMAINS.get(city.lower(), []),
                                          PERK_QUERIES)
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

    perks = PerksAndSupport()
    if (c := notes.get("certificate")) and (r := row(c)) and r["section"] == "perks:certificate":
        perks.certificate = Certificate(name="Job search certificate (proof you're a jobseeker)", how_to_get=c["how_to_get"],
                                        source_url=r["url"], source_date=r.get("published"))
    perks.discounts = [Discount(name=n["name"], discount=n["discount"], proof_needed=n["proof_needed"], city=city,
                                source_url=r["url"], source_date=r.get("published"), **_short(n))
                       for n in notes.get("discounts", []) if (r := row(n)) and r["section"].startswith("perks:")][:MAX_ITEMS]
    for n in notes.get("incentives", []):
        r = row(n)
        if not (r and r["section"].startswith("perks:")):
            continue
        caveat = _deadline_conflict(n["conditions_plain"], deadline_months) or n.get("caveat") or MAY_APPLY
        perks.incentives.append(Incentive(name=n["name"], what_it_is=n["what_it_is"], conditions_plain=n["conditions_plain"],
                                          may_apply=bool(n.get("may_apply")), caveat=caveat,
                                          source_url=r["url"], source_date=r.get("published"),
                                          title_short=n.get("title_short") or ""))  # why_short: from the caveat
    perks.incentives = perks.incentives[:MAX_ITEMS]
    _partial("perks_and_support", perks)

    return OpportunitiesResponse(perks_and_support=perks, mock=not notes)
