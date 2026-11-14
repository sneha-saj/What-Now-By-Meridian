"""Exa search. Returns None on missing key / failure so callers fall back to mocks."""

from __future__ import annotations

import logging

import config

log = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    key = config.exa_key()
    if not key:
        return None
    if _client is None:
        from exa_py import Exa

        _client = Exa(api_key=key)
    return _client


def _to_sources(results) -> list[dict]:
    out = []
    for r in results:
        out.append({
            "title": r.title or r.url,
            "url": r.url,
            "snippet": (getattr(r, "text", None) or "")[:1200],
        })
    return out


def search_official(queries: list[str], per_query: int = 3) -> list[dict] | None:
    """Search only official Finnish sources (Migri, Kela, InfoFinland, Työmarkkinatori)."""
    exa = _get_client()
    if exa is None:
        return None
    seen: dict[str, dict] = {}
    try:
        for q in queries:
            res = exa.search_and_contents(
                q,
                num_results=per_query,
                include_domains=config.OFFICIAL_DOMAINS,
                text={"max_characters": 1500},
            )
            for s in _to_sources(res.results):
                seen.setdefault(s["url"], s)
    except Exception as e:  # noqa: BLE001
        log.warning("Exa official search failed, using mock: %s", e)
        return None
    return list(seen.values()) or None


def search_referrals(occupation: str, city: str, n: int = 3) -> list[dict] | None:
    """Find companies hiring + people to contact.

    TODO: swap to Exa Websets (exa.websets.create with criteria like
    "hiring {occupation} in {city}, English-friendly") for richer, verified lists.
    """
    exa = _get_client()
    if exa is None:
        return None
    try:
        companies = exa.search_and_contents(
            f"companies in {city}, Finland hiring {occupation} English-speaking",
            category="company", num_results=n, text={"max_characters": 500},
        ).results
        people = exa.search_and_contents(
            f"{occupation} recruiter or hiring manager in {city}, Finland",
            category="people", num_results=n, text={"max_characters": 500},
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
    return contacts[: n * 2] or None
