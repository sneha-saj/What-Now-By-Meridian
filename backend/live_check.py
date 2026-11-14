"""Cached checks of official rule pages using Exa Contents and Gemini."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel

import activity
import config
import filecache
import limits
from countries.finland import DEADLINE_RULES

log = logging.getLogger(__name__)
if not log.handlers:  # show live-check debugging (page snippet, Gemini's reasoning) in the backend terminal
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s live_check: %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
    log.propagate = False
CACHE_PATH = Path(__file__).with_name(".live_check_cache.json")
CACHE_TTL = timedelta(hours=24)
ERROR_TTL = timedelta(minutes=15)  # after a failed API call, don't call again on every request
PAGE_CACHE_PATH = Path(__file__).with_name(".live_check_pages.json")

def _read_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}

def _write_cache(cache: dict) -> None:
    try:
        CACHE_PATH.write_text(json.dumps(cache, indent=2))
    except OSError as exc:
        log.warning("Could not save live-check cache: %s", exc)

def _fetch_page(url: str) -> str:
    """Page text via Exa contents. Cached 24h by URL: the rules share one Migri page, so one Exa call."""
    k = filecache.key("page", url)
    cached = filecache.read(PAGE_CACHE_PATH, k)
    if cached is not None:
        return cached
    from exa_py import Exa
    client = Exa(api_key=config.exa_key())
    result = client.get_contents([url], text=True)
    results = getattr(result, "results", result)
    page = results[0]
    text = (getattr(page, "text", None) or getattr(page, "content", None) or "")[:20000]
    if text:
        filecache.write(PAGE_CACHE_PATH, k, text, CACHE_TTL)
    return text

class _Verdict(BaseModel):
    reasoning: str
    verified: bool
    evidence_snippet: str


def _ask_gemini(rule: dict, page: str) -> tuple[bool, str]:
    from services import gemini

    prompt = (
        "You check whether an official Migri page still supports a rule we show to users.\n"
        "Judge the MEANING, not the exact wording. verified=true if the page says the same thing in any words:\n"
        "the same length of time (for example '3 months', 'three months', 'up to three months') for the same\n"
        "group of people (for example 'work-based residence permit', 'specialist', 'EU Blue Card', 'held for\n"
        "less than two years'). For a rule that says the period does NOT apply to some groups, verified=true if\n"
        "the page only describes the period for work-based permits and does not extend it to those groups.\n"
        "verified=false only if the page clearly states a different length of time or different conditions.\n"
        "reasoning: one or two sentences on what the page says about this. evidence_snippet: a short exact quote.\n"
        f"Rule: {json.dumps({k: rule[k] for k in ('description', 'months', 'applies_to')})}\n"
        f"Page text:\n{page}"
    )
    result = gemini.structured_call(prompt, _Verdict, "checking that Migri's page still says the same")
    if result is None:
        raise RuntimeError("Gemini gave no answer")
    log.info("Live check %s: verified=%s reasoning=%r", rule["id"], result["verified"], result["reasoning"])
    return bool(result["verified"]), str(result["evidence_snippet"])[:500]

def check_rule(rule: dict, *, force: bool = False) -> dict:
    now = datetime.now(timezone.utc)
    cache = _read_cache()
    entry = cache.get(rule["id"])
    if not force and entry:
        try:
            checked = datetime.fromisoformat(entry["checked_at"])
            if checked.tzinfo is None:
                checked = checked.replace(tzinfo=timezone.utc)
            ttl = ERROR_TTL if entry.get("status") == "error" else CACHE_TTL
            if now - checked < ttl:
                return {"rule_id": rule["id"], **entry}
        except (KeyError, ValueError, TypeError):
            pass
    checked_at = now.isoformat()
    if not config.exa_key() or not config.gemini_key():
        # No call was made, so nothing to cache: adding keys works on the next request.
        return {"rule_id": rule["id"], "status": "error", "checked_at": checked_at,
                "evidence_snippet": "Live-check API keys are not configured"}
    if limits.paused("Exa") or limits.paused("Gemini"):
        return {"rule_id": rule["id"], "status": "error", "checked_at": checked_at,
                "evidence_snippet": "Paused after a rate limit"}
    service = "Exa"
    try:
        activity.emit({"type": "exa", "status": "searching", "purpose": "rule check", "query": rule["source_url"],
                       "domains": ["migri.fi"]})
        page = _fetch_page(rule["source_url"])
        activity.emit({"type": "exa", "status": "found", "purpose": "rule check", "query": rule["source_url"],
                       "results": [{"title": "Migri", "url": rule["source_url"]}], "count": 1})
        if not page:
            raise RuntimeError("Exa returned no page text")
        log.info("Live check %s: fetched %d chars, starts %r", rule["id"], len(page), page[:300])
        service = "Gemini"
        verified, evidence = _ask_gemini(rule, page)
        entry = {"rule_id": rule["id"], "status": "verified" if verified else "mismatch", "checked_at": checked_at, "evidence_snippet": evidence}
    except Exception as exc:  # graceful degradation for unavailable upstreams
        limits.note_failure(service, exc)
        log.warning("Live check failed for %s: %s", rule["id"], type(exc).__name__)
        entry = {"rule_id": rule["id"], "status": "error", "checked_at": checked_at,
                 "evidence_snippet": "Couldn't check right now"}
    cache[rule["id"]] = entry
    _write_cache(cache)
    return entry

def check_all_rules() -> list[dict]:
    return [{**rule, "live_check": check_rule(rule)} for rule in DEADLINE_RULES]

def get_live_check(rule_id: str | None) -> dict | None:
    if rule_id is None:
        return None
    rule = next((r for r in DEADLINE_RULES if r["id"] == rule_id), None)
    return check_rule(rule) if rule else None
