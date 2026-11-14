"""Cached checks of official rule pages using Exa Contents and Gemini."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel

import config
from countries.finland import DEADLINE_RULES

log = logging.getLogger(__name__)
CACHE_PATH = Path(__file__).with_name(".live_check_cache.json")
CACHE_TTL = timedelta(hours=24)

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
    from exa_py import Exa
    client = Exa(api_key=config.exa_key())
    result = client.get_contents([url], text=True)
    results = getattr(result, "results", result)
    page = results[0]
    return (getattr(page, "text", None) or getattr(page, "content", None) or "")[:12000]

class _Verdict(BaseModel):
    verified: bool
    evidence_snippet: str


def _ask_gemini(rule: dict, page: str) -> tuple[bool, str]:
    from services import gemini

    prompt = (
        "Check whether this official page still supports the rule below. Answer verified=true only if the page "
        "states the same number of months AND the same conditions. evidence_snippet: a short exact quote from "
        "the page, or a one-line reason if it doesn't match.\n"
        f"Rule: {json.dumps({k: rule[k] for k in ('description', 'months', 'applies_to')})}\n"
        f"Page text:\n{page}"
    )
    result = gemini.structured_call(prompt, _Verdict)
    if result is None:
        raise RuntimeError("Gemini gave no answer")
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
            if now - checked < CACHE_TTL:
                return {"rule_id": rule["id"], **entry}
        except (KeyError, ValueError, TypeError):
            pass
    checked_at = now.isoformat()
    try:
        if not config.exa_key() or not config.gemini_key():
            raise RuntimeError("Live-check API keys are not configured")
        page = _fetch_page(rule["source_url"])
        if not page:
            raise RuntimeError("Exa returned no page text")
        verified, evidence = _ask_gemini(rule, page)
        entry = {"rule_id": rule["id"], "status": "verified" if verified else "mismatch", "checked_at": checked_at, "evidence_snippet": evidence}
    except Exception as exc:  # graceful degradation for unavailable upstreams
        log.warning("Live check failed for %s: %s", rule["id"], exc)
        # Errors are not cached, so adding API keys or a network blip recovers on the next request.
        return {"rule_id": rule["id"], "status": "error", "checked_at": checked_at, "evidence_snippet": str(exc)[:500]}
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
