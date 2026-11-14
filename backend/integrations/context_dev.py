"""Context.dev Scrape API (POST https://api.context.dev/v1/web/scrape), called with plain HTTP.

Used to read whole official pages and pull exact fields out of them with a JSON Schema (e.g. the discount and the
proof you need, from a city's page), where Exa only gives us a search snippet. The rule check in live_check.py
also reads Migri's page through Context.dev.

Settings: our own 24h file cache, `maxAgeMs` 1 day (the Migri rule check asks for a fresh copy instead, once a day),
a 30 s deadline with `return-partial`, no retries. On a 429
or 402 (out of credits) Context.dev is paused like Exa and Gemini and callers use their fallback. Zero Data
Retention stays off. The key is read from CONTEXT_DEV_API_KEY on the backend only; no personal answers are sent,
only the public page URL and a schema.

Try it once by hand (one live call): `cd backend && .venv/bin/python -m integrations.context_dev <url>`
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import timedelta
from pathlib import Path

import httpx

import activity
import config
import filecache
import limits

log = logging.getLogger(__name__)

API_URL = "https://api.context.dev/v1/web/scrape"
SERVICE = "Context.dev"
TIMEOUT_MS = 30_000
MAX_AGE_MS = 24 * 60 * 60 * 1000  # accept Context.dev's own copy of the page if it's under a day old
CACHE_PATH = Path(__file__).resolve().parent.parent / ".context_dev_cache.json"
CACHE_TTL = timedelta(hours=24)


class ScrapeError(RuntimeError):
    pass


def available() -> bool:
    return bool(config.context_key()) and not limits.paused(SERVICE)


def output(resp: dict | None, name: str):
    """The data of one output (e.g. "json", "markdown") if it was requested and succeeded, else None."""
    env = (resp or {}).get(name) or {}
    return env.get("data") if isinstance(env, dict) and env.get("success") is True else None


def scrape(url: str, formats: dict, *, purpose: str, max_age_ms: int = MAX_AGE_MS, cache: bool = True,
           **params) -> dict | None:
    """One scrape request. Returns the whole response (read outputs with `output()`), or None when Context.dev is
    not configured, paused, failed, or none of the requested outputs succeeded. A partial response (`isPartial`)
    is returned as is; callers only use the outputs that succeeded. `max_age_ms=0` asks for a fresh copy;
    `cache=False` skips our file cache (for callers that cache the result themselves)."""
    if not available():
        return None
    k = filecache.key("scrape", url, formats, max_age_ms, params)
    cached = filecache.read(CACHE_PATH, k) if cache else None
    if cached is not None:
        activity.emit({"type": "context", "status": "cached", "purpose": purpose, "url": url})
        return cached
    activity.emit({"type": "context", "status": "reading", "purpose": purpose, "url": url})
    body = {"url": url, "formats": formats, "maxAgeMs": max_age_ms,
            "timeoutOpts": {"milliseconds": TIMEOUT_MS, "behavior": "return-partial"}, **params}
    try:
        r = httpx.post(API_URL, json=body, timeout=TIMEOUT_MS / 1000 + 10,
                       headers={"Authorization": f"Bearer {config.context_key()}", "Content-Type": "application/json"})
        if r.status_code == 429:
            raise ScrapeError("429 rate limit")
        if r.status_code == 402:
            raise ScrapeError("402 quota exceeded (out of credits)")
        if r.status_code >= 400:
            code = ""
            try:
                code = r.json().get("error_code") or ""
            except ValueError:
                pass
            raise ScrapeError(f"HTTP {r.status_code} {code}".strip())
        resp = r.json()
    except Exception as e:  # noqa: BLE001
        if not limits.note_failure(SERVICE, e):
            log.warning("Context.dev could not read %s: %s", url, e if isinstance(e, ScrapeError) else type(e).__name__)
        activity.emit({"type": "context", "status": "failed", "purpose": purpose, "url": url})
        return None
    requested = [v for v in resp.values() if isinstance(v, dict) and v.get("requested")]
    if not any(v.get("success") is True for v in requested):
        activity.emit({"type": "context", "status": "failed", "purpose": purpose, "url": url})
        return None
    if cache:
        filecache.write(CACHE_PATH, k, resp, CACHE_TTL)
    activity.emit({"type": "context", "status": "read", "purpose": purpose, "url": url,
                   "partial": bool(resp.get("isPartial"))})
    return resp


def read_markdown(url: str, *, purpose: str, max_age_ms: int = MAX_AGE_MS, cache: bool = True) -> str | None:
    """The page's main content as Markdown, or None."""
    resp = scrape(url, {"markdown": True}, purpose=purpose, max_age_ms=max_age_ms, cache=cache,
                  sharedParams={"mainContentOnly": True})
    text = output(resp, "markdown")
    return text if isinstance(text, str) and text.strip() else None


def extract_json(url: str, schema: dict, instructions: str, *, purpose: str) -> dict | None:
    """Read a page and return the fields described by `schema` (a JSON Schema object), or None."""
    resp = scrape(url, {"json": True}, purpose=purpose,
                  jsonParams={"schema": schema, "instructions": instructions[:2000]},
                  sharedParams={"mainContentOnly": True})
    data = output(resp, "json")
    return data if isinstance(data, dict) else None


if __name__ == "__main__":  # manual check: one live call, prints the page title and the start of its Markdown
    if len(sys.argv) != 2:
        sys.exit("usage: python -m integrations.context_dev <url>")
    if not config.context_key():
        sys.exit("CONTEXT_DEV_API_KEY is not set in the repo-root .env (or USE_MOCK/FORCE_MOCKS is on).")
    page = scrape(sys.argv[1], {"markdown": True}, purpose="manual check", sharedParams={"mainContentOnly": True})
    if page is None:
        sys.exit("Context.dev returned nothing usable (see the log line above).")
    print(json.dumps({"title": (page.get("metadata") or {}).get("title"), "partial": bool(page.get("isPartial")),
                      "cache": page.get("cache_metadata"), "credits": page.get("key_metadata")}, indent=2))
    print((output(page, "markdown") or "")[:1500])
