"""Every source Exa used: url, title, domain, page date and which roadmap step it was for.

Stored in a small JSON file (no database) so /rules and the "How we know this" page can list them.
Only public page info is stored: never the user's facts or search queries.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

PATH = Path(__file__).with_name(".sources_used.json")
MAX = 300
_lock = threading.Lock()

STEP_FOR_PURPOSE = {
    "rule check": "Your deadline",
    "registering as a jobseeker": "This week",
    "unemployment benefits": "This week",
    "labour-shortage sectors": "Week 4",
    "other permits": "Plan B",
    "companies": "Opportunities",
    "job posts": "Opportunities",
    "people": "Opportunities",
    "events": "Opportunities",
    "unions": "Opportunities",
    "hiring signals": "Opportunities",
    "support": "Opportunities",
    "perks": "Opportunities",
    "ask": "Ask",
}


def _domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def _load() -> list[dict]:
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def record(results: list[dict], purpose: str) -> None:
    """results: [{title, url, published?}]. Deduplicated by (url, step); newest first."""
    step = STEP_FOR_PURPOSE.get(purpose, "Other")
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        rows = _load()
        seen = {(r["url"], r["step"]) for r in rows}
        new = [{"url": r["url"], "title": r.get("title") or r["url"], "domain": _domain(r["url"]),
                "date": (r.get("published") or "")[:10] or None, "step": step, "used_at": now}
               for r in results if r.get("url") and (r["url"], step) not in seen]
        if not new:
            return
        try:
            PATH.write_text(json.dumps((new + rows)[:MAX], ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass


def recent(limit: int = 100) -> list[dict]:
    return _load()[:limit]
