"""Cached checks of official rule pages using Context.dev or Exa and Gemini."""
from __future__ import annotations

import json
import logging
import httpx
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel

import activity
import config
import sources_log
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

MAX_PAGE_AGE_HOURS = 168


def _failed_status(result) -> str | None:
    for st in getattr(result, "statuses", None) or []:
        status = getattr(st, "status", None) or (st.get("status") if isinstance(st, dict) else None)
        if status and status != "success":
            err = getattr(st, "error", None) or (st.get("error") if isinstance(st, dict) else None)
            return f"{status} {getattr(err, 'tag', None) or err or ''}".strip()
    return None


def _fetch_page(url: str) -> str:
    """Read one official URL, caching the shared rule page for 24 hours."""
    k = filecache.key("page", url)
    cached = filecache.read(PAGE_CACHE_PATH, k)
    if cached is not None:
        return cached
    if config.context_key() and not limits.paused("Context.dev"):
        try:
            text = _fetch_context_page(url)
            filecache.write(PAGE_CACHE_PATH, k, text, CACHE_TTL)
            return text
        except Exception as exc:
            limits.note_failure("Context.dev", exc)
            log.warning("Context.dev could not read %s: %s", url, type(exc).__name__)
            if not config.exa_key() or limits.paused("Exa"):
                raise
    if not config.exa_key() or limits.paused("Exa"):
        raise RuntimeError("No page retrieval provider is available")
    return _fetch_exa_page(url, k)


def _fetch_context_page(url: str) -> str:
    """Use Context.dev's Scrape API for the exact official page, with no user facts."""
    response = httpx.post(
        "https://api.context.dev/v1/web/scrape",
        headers={"Authorization": f"Bearer {config.context_key()}"},
        json={"url": url, "formats": {"markdown": True},
              "sharedParams": {"mainContentOnly": True}, "maxAgeMs": 0},
        timeout=15,
    )
    response.raise_for_status()
    markdown = response.json().get("markdown") or {}
    if markdown.get("success") is not True or not isinstance(markdown.get("data"), str) or not markdown["data"].strip():
        raise RuntimeError("Context.dev returned no Markdown for the official page")
    return markdown["data"][:20000]


def _fetch_exa_page(url: str, k: str) -> str:
    """Use Exa Contents, then its search index if the official site blocks crawling."""
    from exa_py import Exa
    client = Exa(api_key=config.exa_key())
    # Migri's page is slow to crawl live, so accept Exa's copy if it's under a week old. If a fresh crawl still
    # times out, try once more from Exa's cache only (-1). At most two calls, never a loop.
    result = client.get_contents([url], text=True, max_age_hours=MAX_PAGE_AGE_HOURS, livecrawl_timeout=20000)
    if _failed_status(result):
        log.info("Live crawl of %s failed (%s); trying Exa's cached copy", url, _failed_status(result))
        result = client.get_contents([url], text=True, max_age_hours=-1)
    if (status := _failed_status(result)):
        # Migri blocks Exa's crawler on some URLs (403) and the exact URL may not be stored. Read the same
        # page from Exa's search index instead: one search limited to migri.fi, preferring the exact page.
        log.info("Contents failed (%s); reading the page from Exa's migri.fi index", status)
        return _from_search(client, url, k)
    results = getattr(result, "results", result)
    if not results:
        raise RuntimeError("Exa returned no result for the Migri page")
    page = results[0]
    text = (getattr(page, "text", None) or "")[:20000]
    log.info("Fetched %s: %d chars, page date %s", url, len(text), getattr(page, "published_date", None))
    if text:
        filecache.write(PAGE_CACHE_PATH, k, text, CACHE_TTL)
    return text

def _from_search(client, url: str, k: str) -> str:
    path = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    res = client.search(
        "work-based residence permit protection period unemployment three months six months new job",
        include_domains=["migri.fi"], num_results=3, contents={"text": {"max_characters": 20000}},
    )
    pages = sorted(res.results, key=lambda r: path not in (r.url or ""))  # the exact page first, if found
    page = next((p for p in pages if getattr(p, "text", None)), None)
    if page is None:
        raise RuntimeError("Exa found no Migri page about the protection period")
    log.info("Read %s from Exa's index: %d chars, page date %s", page.url, len(page.text), getattr(page, "published_date", None))
    filecache.write(PAGE_CACHE_PATH, k, page.text[:20000], CACHE_TTL)
    return page.text[:20000]


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
    if not (config.exa_key() or config.context_key()) or not config.gemini_key():
        # No call was made, so nothing to cache: adding keys works on the next request.
        return {"rule_id": rule["id"], "status": "error", "checked_at": checked_at,
                "evidence_snippet": "Live-check API keys are not configured"}
    if (not (config.exa_key() and not limits.paused("Exa"))
            and not (config.context_key() and not limits.paused("Context.dev"))) or limits.paused("Gemini"):
        return {"rule_id": rule["id"], "status": "error", "checked_at": checked_at,
                "evidence_snippet": "Paused after a rate limit"}
    service = "Context.dev" if config.context_key() else "Exa"
    try:
        if service == "Exa":
            activity.emit({"type": "exa", "status": "searching", "purpose": "rule check", "query": rule["source_url"],
                           "domains": ["migri.fi"]})
        page = _fetch_page(rule["source_url"])
        sources_log.record([{"title": rule.get("description", "Migri"), "url": rule["source_url"]}], "rule check")
        if service == "Exa":
            activity.emit({"type": "exa", "status": "found", "purpose": "rule check", "query": rule["source_url"],
                           "results": [{"title": "Migri", "url": rule["source_url"]}], "count": 1})
        if not page:
            raise RuntimeError("The official page returned no text")
        log.info("Live check %s: fetched %d chars, starts %r", rule["id"], len(page), page[:300])
        service = "Gemini"
        verified, evidence = _ask_gemini(rule, page)
        entry = {"rule_id": rule["id"], "status": "verified" if verified else "mismatch", "checked_at": checked_at, "evidence_snippet": evidence}
    except Exception as exc:  # graceful degradation for unavailable upstreams
        limits.note_failure(service, exc)
        log.warning("Live check failed for %s: %s: %s", rule["id"], type(exc).__name__, str(exc)[:200])
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
