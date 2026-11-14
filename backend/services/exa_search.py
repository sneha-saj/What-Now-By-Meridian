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


def search_referrals(occupation: str, city: str, n: int = 3) -> list[dict] | None:
    """Find companies hiring + people to contact.

    TODO: for richer, verified lists, move this to Exa's Agent API (/agent) —
    the build-with-exa skill says list-building belongs there, not Websets.
    """
    key = _cache_key("referrals", {"occupation": occupation, "city": city, "n": n})
    cached = _cache_read(key)
    if cached is not None:
        return cached
    exa = _get_client()
    if exa is None:
        return None
    try:
        companies = exa.search(
            f"companies in {city}, Finland hiring {occupation} English-speaking",
            category="company", num_results=n, contents={"highlights": True},
            objective=(f"Find companies in {city}, Finland that currently hire {occupation}s and work in English, "
                       "so a job seeker can contact them. Prefer company pages and careers pages."),
        ).results
        people = exa.search(
            f"{occupation} recruiter or hiring manager in {city}, Finland",
            category="people", num_results=n, contents={"highlights": True},
            objective=(f"Find recruiters or hiring managers who hire {occupation}s in {city}, Finland, "
                       "so a job seeker can reach out to them directly."),
        ).results
    except Exception as e:  # noqa: BLE001
        log.warning("Exa referral search failed, using mock: %s", e)
        return None

    contacts = []
    for p in people:
        contacts.append({
            "name": p.title or "Contact",
            "role": "Recruiter / hiring manager",
            "organization": (getattr(p, "author", None) or "See profile"),
            "why": f"Works in {occupation} hiring around {city}.",
            "source": {"title": p.title or p.url, "url": p.url},
        })
    for c in companies:
        contacts.append({
            "name": "Hiring team",
            "role": "Recruitment",
            "organization": c.title or c.url,
            "why": f"Company in {city} that hires {occupation}s.",
            "source": {"title": c.title or c.url, "url": c.url},
        })
    results = contacts[: n * 2] or None
    if results:
        _cache_write(key, results)
    return results
