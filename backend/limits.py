"""Rate-limit guard for paid APIs (Gemini free tier, limited Exa credits).

After a 429 / quota error, the service is paused for COOLDOWN and the app uses its fallbacks instead of
retrying. One clear log line says so. Never logs keys or request bodies.
"""

from __future__ import annotations

import logging
import time

COOLDOWN_SECONDS = 15 * 60
_paused_until: dict[str, float] = {}
log = logging.getLogger("limits")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s rate-limit: %(message)s"))
    log.addHandler(_h)
    log.propagate = False


def is_rate_limit(exc: BaseException) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    return code == 429 or "429" in text or "rate limit" in text or "resource_exhausted" in text or "quota" in text


def paused(service: str) -> bool:
    return time.time() < _paused_until.get(service, 0)


def note_failure(service: str, exc: BaseException) -> bool:
    """Call on any API error. Returns True (and pauses the service) if it was a rate limit."""
    if not is_rate_limit(exc):
        return False
    if not paused(service):
        log.error("%s rate limit hit (429). Pausing %s calls for %d minutes and using fallbacks. "
                  "Not retrying.", service, service, COOLDOWN_SECONDS // 60)
    _paused_until[service] = time.time() + COOLDOWN_SECONDS
    return True


def reset() -> None:
    _paused_until.clear()
