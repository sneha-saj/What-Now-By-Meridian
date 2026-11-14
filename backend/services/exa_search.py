"""Exa search. Returns None on missing key / failure so callers fall back to mocks."""

from __future__ import annotations

import logging
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import config

log = logging.getLogger(__name__)

_client = None
CACHE_PATH = Path(__file__).resolve().parent.parent / ".exa_search_cache.json"
CACHE_TTL = timedelta(hours=24)


def _cache_key(kind: str, params: dict) -> str:
    serialized = json.dumps({"kind": kind, **params}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _cache_read(key: str):
    try:
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        entry = cache.get(key)
        if not entry:
            return None
        expires_at = datetime.fromisoformat(entry["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= expires_at:
            return None
        return entry["value"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _cache_write(key: str, value) -> None:
    try:
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cache = {}
        cache[key] = {
            "expires_at": (datetime.now(timezone.utc) + CACHE_TTL).isoformat(),
            "value": value,
        }
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        log.warning("Could not save Exa result cache: %s", exc)


def _get_client():
    global _client
    key = config.exa_key()
    if not key:
        return None
    if _client is None:
        from exa_py import Exa

        _client = Exa(api_key=key)
    return _client


OFFICIAL_OBJECTIVE = (
    "Help a foreign worker in Finland who just lost their job understand what to do next. "
    "Rank official guidance pages from Migri, Kela, InfoFinland and Tyomarkkinatori first; "
    "exclude news, forums and law-firm marketing. Pull concrete facts: deadlines and time limits, "
    "eligibility conditions, required registrations and the steps to take."
)


def _snippet(r) -> str:
    highlights = getattr(r, "highlights", None) or []
    return (" ... ".join(highlights) or getattr(r, "text", None) or "")[:1200]


def _to_sources(results) -> list[dict]:
    out = []
    for r in results:
        out.append({
            "title": r.title or r.url,
            "url": r.url,
            "snippet": _snippet(r),
        })
    return out


def search_official(queries: list[str], per_query: int = 3) -> list[dict] | None:
    """Search only official Finnish sources (Migri, Kela, InfoFinland, Työmarkkinatori)."""
    key = _cache_key("official", {"queries": queries, "per_query": per_query})
    cached = _cache_read(key)
    if cached is not None:
        return cached
    exa = _get_client()
    if exa is None:
        return None
    seen: dict[str, dict] = {}
    try:
        for q in queries:
            res = exa.search(
                q,
                num_results=per_query,
                include_domains=config.OFFICIAL_DOMAINS,
                contents={"highlights": True},
                objective=OFFICIAL_OBJECTIVE,
            )
            for s in _to_sources(res.results):
                seen.setdefault(s["url"], s)
    except Exception as e:  # noqa: BLE001
        log.warning("Exa official search failed, using mock: %s", e)
        return None
    results = list(seen.values()) or None
    if results:
        _cache_write(key, results)
    return results


def _cached_search(kind: str, params: dict, run):
    """Shared cache + error handling for the referral searches. `run(exa)` returns a list."""
    key = _cache_key(kind, params)
    cached = _cache_read(key)
    if cached is not None:
        return cached
    exa = _get_client()
    if exa is None:
        return None
    try:
        results = run(exa)
    except Exception as e:  # noqa: BLE001
        log.warning("Exa %s search failed, using mock: %s", kind, e)
        return None
    if results:
        _cache_write(key, results)
    return results or None


def _hl(r) -> str:
    return " ... ".join(getattr(r, "highlights", None) or [])[:600]


def search_companies(field: str, city: str, n: int = 8) -> list[dict] | None:
    """Companies hiring now in the user's field (or labour-shortage sectors) in or near their city."""
    def run(exa):
        res = exa.search(
            f"companies in or near {city}, Finland currently hiring {field} or in labour-shortage sectors",
            category="company", num_results=n, contents={"highlights": True},
            objective=(f"Companies in or near {city}, Finland that are hiring now for {field} roles, or work in "
                       "sectors with a labour shortage, and that hire international workers. Prefer company "
                       "and careers pages. Pull what the company does and any open roles."),
        )
        return [{"name": r.title or r.url, "url": r.url, "highlight": _hl(r)} for r in res.results][:n]
    return _cached_search("companies", {"field": field, "city": city, "n": n}, run)


def _split_profile_title(title: str) -> tuple[str, str]:
    """'Jane Doe - Head Chef - Restaurant Oy | LinkedIn' -> ('Jane Doe', 'Head Chef')."""
    parts = [p.strip() for p in title.split("|")[0].split(" - ") if p.strip()]
    return (parts[0] if parts else title), (parts[1] if len(parts) > 1 else "")


def search_people(companies: list[dict], field: str, city: str, top: int = 3, per_company: int = 2) -> list[dict] | None:
    """Public professional profiles of likely contacts at the top companies."""
    names = [c["name"] for c in companies[:top]]

    def run(exa):
        people = []
        for company in names:
            res = exa.search(
                f"{field} hiring manager, team lead or recruiter at {company} in {city}, Finland",
                category="people", num_results=per_company, contents={"highlights": True},
                objective=(f"Public professional profiles of people at {company} who hire for {field} roles "
                           "or have a similar background, so a job seeker can reach out politely."),
            )
            for r in res.results:
                name, role = _split_profile_title(r.title or "")
                if name:
                    people.append({"name": name, "role": role, "company": company, "profile_url": r.url,
                                   "highlight": _hl(r)})
        return people
    return _cached_search("people", {"companies": names, "field": field, "city": city,
                                     "per_company": per_company}, run)


def search_communities(field: str, city: str, today: str, n: int = 3) -> list[dict] | None:
    """International professional groups, upcoming meetups/events and union career services."""
    queries = [
        ("professional_group", f"international professionals {field} network, meetups or events in {city} Finland "
                               f"in the next 30 days from {today}"),
        ("union", f"trade union career services for {field} workers in Finland, in English"),
    ]

    def run(exa):
        out = []
        for kind, q in queries:
            res = exa.search(
                q, num_results=n, contents={"highlights": True},
                objective=("Help an international job seeker in Finland find professional groups, upcoming events "
                           "(next 30 days) and union career services. Pull event dates when stated."),
            )
            out += [{"name": r.title or r.url, "url": r.url, "kind": kind, "highlight": _hl(r)} for r in res.results]
        return out
    return _cached_search("communities", {"field": field, "city": city, "today": today, "n": n}, run)


PLAN_OBJECTIVE = (
    "Official guidance for a foreign worker in Finland who has lost their job. Rank pages from "
    "Migri, Kela, InfoFinland and Tyomarkkinatori first, preferring pages updated after June 2025 "
    "(the rules changed on 11 June 2025). Exclude news and forums. Pull concrete facts: steps, "
    "time limits, eligibility conditions and where to apply."
)


def plan_topics(field: str | None, studied_in_finland: bool | None, family_in_finland: bool | None) -> list[tuple[str, str]]:
    """(topic, query) pairs for the /plan search."""
    alt = ["residence permit options after losing a job in Finland"]
    if studied_in_finland:
        alt.append("residence permit for looking for work after graduating in Finland")
    if family_in_finland:
        alt.append("family-based residence permit Finland")
    shortage = "labour shortage occupations in Finland occupational barometer"
    if field:
        shortage += f" {field}"
    return [
        ("register_jobseeker", "register as an unemployed jobseeker in Finland as a foreigner"),
        ("unemployment_benefits", "unemployment benefits Finland Kela or unemployment fund for immigrants"),
        ("alternative_permits", "; ".join(alt)),
        ("labour_shortage", shortage),
    ]


def search_plan_sources(topics: list[tuple[str, str]], per_topic: int = 3) -> list[dict] | None:
    """Search the trusted domains for each topic. Returns [{topic, title, url, highlight}] or None."""
    key = _cache_key("plan", {"topics": topics, "per_topic": per_topic})
    cached = _cache_read(key)
    if cached is not None:
        return cached
    exa = _get_client()
    if exa is None:
        return None
    seen: dict[str, dict] = {}
    try:
        for topic, query in topics:
            res = exa.search(
                query,
                num_results=per_topic,
                include_domains=config.OFFICIAL_DOMAINS,
                contents={"highlights": True},
                objective=PLAN_OBJECTIVE,
            )
            for r in res.results:
                highlight = " ... ".join(getattr(r, "highlights", None) or [])[:1200]
                if r.url not in seen and highlight:
                    seen[r.url] = {"topic": topic, "title": r.title or r.url, "url": r.url, "highlight": highlight}
    except Exception as e:  # noqa: BLE001
        log.warning("Exa plan search failed, using mock: %s", e)
        return None
    results = list(seen.values()) or None
    if results:
        _cache_write(key, results)
    return results
