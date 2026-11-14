"""Exa search. Returns None on missing key / failure so callers fall back to mocks."""

from __future__ import annotations

import logging
import contextvars
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import activity
import config
import limits
import sources_log

log = logging.getLogger(__name__)
MAX_PARALLEL = 6


def _parallel(fn, items):
    """Run Exa calls side by side; results keep the input order. Any error propagates."""
    items = list(items)
    if len(items) <= 1:
        return [fn(i) for i in items]
    with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL, len(items))) as pool:
        # copy_context so each thread can still report activity for this request
        futures = [pool.submit(contextvars.copy_context().run, fn, i) for i in items]
        return [f.result() for f in futures]


def _search(exa, query: str, purpose: str, **kwargs):
    """exa.search plus a live activity event describing what was searched and what came back."""
    activity.emit({"type": "exa", "status": "searching", "purpose": purpose, "query": query,
                   "domains": kwargs.get("include_domains") or [], "category": kwargs.get("category")})
    res = exa.search(query, **kwargs)
    found = [{"title": r.title or r.url, "url": r.url, "published": getattr(r, "published_date", None)} for r in res.results]
    sources_log.record(found, purpose)
    activity.emit({"type": "exa", "status": "found", "purpose": purpose, "query": query,
                   "results": found[:5], "count": len(res.results)})
    return res

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
    if not key or limits.paused("Exa"):
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
        if not limits.note_failure("Exa", e):
            log.warning("Exa official search failed, using fallback: %s", type(e).__name__)
        return None
    results = list(seen.values()) or None
    if results:
        _cache_write(key, results)
    return results


def _cached_search(kind: str, params: dict, run):
    """Shared cache + error handling for the opportunities searches. `run(exa)` returns a list."""
    key = _cache_key(kind, params)
    cached = _cache_read(key)
    if cached is not None:
        activity.emit({"type": "exa", "status": "cached", "purpose": kind, "count": len(cached)})
        return cached
    exa = _get_client()
    if exa is None:
        return None
    try:
        results = run(exa)
    except Exception as e:  # noqa: BLE001
        if not limits.note_failure("Exa", e):
            log.warning("Exa %s search failed, using fallback: %s", kind, type(e).__name__)
        return None
    if results:
        _cache_write(key, results)
    return results or None


REGION = {"helsinki": "Uusimaa", "espoo": "Uusimaa", "vantaa": "Uusimaa", "kauniainen": "Uusimaa",
          "tampere": "Pirkanmaa", "turku": "Varsinais-Suomi", "oulu": "Pohjois-Pohjanmaa",
          "jyväskylä": "Keski-Suomi", "lahti": "Päijät-Häme", "kuopio": "Pohjois-Savo", "pori": "Satakunta"}


def region_of(city: str | None) -> str | None:
    return REGION.get((city or "").strip().lower())


def _date(r) -> str | None:
    return (getattr(r, "published_date", None) or "")[:10] or None


def _hl(r) -> str:
    return " ... ".join(getattr(r, "highlights", None) or [])[:600]


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


PLAN_OBJECTIVE = (
    "Official guidance for a foreign worker in Finland who has lost their job. Rank pages from "
    "Migri, Kela, InfoFinland and Tyomarkkinatori first, preferring pages updated after June 2025 "
    "(the rules changed on 11 June 2025). Exclude news and forums. Pull concrete facts: steps, "
    "time limits, eligibility conditions and where to apply."
)


TOPIC_PURPOSE = {"register_jobseeker": "registering as a jobseeker", "unemployment_benefits": "unemployment benefits",
                 "labour_shortage": "labour-shortage sectors", "plan_b": "other permits", "your_update": "what you added"}


def plan_topics(field: str | None, candidates: list[dict], city: str | None = None, fund: str | None = None,
                registered: str | None = None, note: str | None = None) -> list[tuple[str, str]]:
    """(topic, query) pairs for the /plan search: the 3 core topics plus one per Plan B candidate.
    Personalised with the user's field, city, region, unemployment fund and registration so results are specific."""
    region = region_of(city)
    shortage = f"labour shortage occupations {region or 'Finland'} occupational barometer"
    if field:
        shortage += f" {field}"
    where = f"in {city} " if city else "in Finland "
    return [
        ("register_jobseeker", f"after registering as a jobseeker {where}employment plan obligations" if registered == "yes"
         else f"register as an unemployed jobseeker {where}employment services foreigner"),
        ("unemployment_benefits", "earnings-related unemployment allowance apply to your unemployment fund" if fund == "yes"
         else "unemployment benefits Finland Kela basic unemployment allowance labour market subsidy for immigrants"),
        ("labour_shortage", shortage),
        *[(f"plan_b:{c['id']}", c["query"]) for c in candidates],
        *([("your_update", f"{' '.join(note.split())[:150]} Finland {city or ''}".strip())] if note else []),
    ]


def search_plan_sources(topics: list[tuple[str, str]], per_topic: int = 3) -> list[dict] | None:
    """Search the trusted domains for each topic. Returns [{topic, title, url, highlight}] or None."""
    key = _cache_key("plan", {"topics": topics, "per_topic": per_topic})
    cached = _cache_read(key)
    if cached is not None:
        activity.emit({"type": "exa", "status": "cached", "purpose": "official guidance", "count": len(cached)})
        return cached
    exa = _get_client()
    if exa is None:
        return None
    seen: dict[str, dict] = {}

    def one(item):
        topic, query = item
        return topic, _search(exa, query, TOPIC_PURPOSE.get(topic.split(":")[0], topic), num_results=per_topic,
                              include_domains=config.OFFICIAL_DOMAINS, contents={"highlights": True},
                              objective=PLAN_OBJECTIVE)
    try:
        for topic, res in _parallel(one, topics):
            for r in res.results:
                highlight = " ... ".join(getattr(r, "highlights", None) or [])[:1200]
                if r.url not in seen and highlight:
                    seen[r.url] = {"topic": topic, "title": r.title or r.url, "url": r.url, "highlight": highlight,
                                   "published": (getattr(r, "published_date", None) or "")[:10] or None}
    except Exception as e:  # noqa: BLE001
        if not limits.note_failure("Exa", e):
            log.warning("Exa plan search failed, using fallback: %s", type(e).__name__)
        return None
    results = list(seen.values()) or None
    if results:
        _cache_write(key, results)
    return results


ASK_CACHE_TTL = timedelta(hours=24)


def ask(question: str, official_only: bool, context: str = "") -> dict | None:
    """Exa's Answer endpoint: a grounded answer with citations. For rules questions, limited (by system prompt
    and by filtering citations) to the trusted official domains. None if Exa is unavailable."""
    key = _cache_key("ask", {"q": question.strip().lower(), "official": official_only, "ctx": context})
    cached = _cache_read(key)
    if cached is not None:
        activity.emit({"type": "exa", "status": "cached", "purpose": "ask", "count": len(cached.get("citations", []))})
        return cached
    exa = _get_client()
    if exa is None:
        return None
    domains = config.OFFICIAL_DOMAINS
    system = ("Answer for a person in Finland who lost their job. Plain language, 2-4 short sentences, no markdown. "
              + (f"Use ONLY these official sites: {', '.join(domains)}. If they don't answer it, say so. " if official_only else "")
              + (f"Their situation: {context}." if context else ""))
    activity.emit({"type": "exa", "status": "searching", "purpose": "ask", "query": question,
                   "domains": domains if official_only else []})
    try:
        res = exa.answer(question, system_prompt=system, user_location="FI")
    except Exception as e:  # noqa: BLE001
        if not limits.note_failure("Exa", e):
            log.warning("Exa answer failed: %s", type(e).__name__)
        return None
    citations = [{"title": getattr(c, "title", None) or getattr(c, "url", ""), "url": getattr(c, "url", ""),
                  "published": (getattr(c, "published_date", None) or "")[:10] or None}
                 for c in (getattr(res, "citations", None) or []) if getattr(c, "url", None)]
    if official_only:
        citations = [c for c in citations if any(_domain(c["url"]).endswith(d) for d in domains)]
    out = {"answer": (getattr(res, "answer", None) or "").strip(), "citations": citations[:5]}
    sources_log.record(out["citations"], "ask")
    activity.emit({"type": "exa", "status": "found", "purpose": "ask", "query": question,
                   "results": out["citations"], "count": len(out["citations"])})
    _cache_write(key, out)
    return out


# ---------- /opportunities ----------

def _rows(res, purpose: str) -> list[dict]:
    return [{"title": r.title or r.url, "url": r.url, "published": _date(r), "highlight": _hl(r), "purpose": purpose}
            for r in res.results]


def search_opportunities(field: str, city: str, today: str, city_domains: list[str], perk_queries: dict) -> dict | None:
    """The Perks and support searches for one city, in parallel, cached 24h: one Exa search per perk topic picked
    for the person (see opportunities.perk_topics) on the official + city domains. Returns raw rows per section,
    or None if Exa is unavailable."""
    official = list(config.OFFICIAL_DOMAINS) + city_domains
    calls = [(f"perks:{k}", "perks", dict(
        query=f"{q} {city}", num_results=4, include_domains=official, contents={"highlights": True},
        objective=f"Official page in {city} or Finland: {q}. Pull the exact discount, conditions and proof needed."))
        for k, q in perk_queries.items()]

    def run(exa):
        def one(c):
            section, purpose, kw = c
            kw = dict(kw)
            return section, _rows(_search(exa, kw.pop("query"), purpose, **kw), purpose)
        return dict(_parallel(one, calls))
    return _cached_search("opportunities", {"field": field, "city": city, "today": today, "topics": sorted(perk_queries),
                                            "v": 3}, run)
