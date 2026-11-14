"""Settings loaded from the repo-root .env. Missing keys => mock mode for that service."""

import contextvars
import hmac
import os
from pathlib import Path

from dotenv import load_dotenv
from countries.finland import TRUSTED_DOMAINS

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _flag(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in ("1", "true", "yes", "on")


USE_MOCK = _flag("USE_MOCK")


# ---------- Access codes: live (paid) APIs only for judges ----------
# ACCESS_CODES="code-a,code-b": a request runs live only with a valid X-Access-Code header; everyone else gets the
# free demo mode (no paid API calls: the keys are simply hidden for that request, and every service already falls
# back). Not set = live for everyone, as before.
ACCESS_CODES = [c.strip() for c in os.getenv("ACCESS_CODES", "").split(",") if c.strip()]
_live: contextvars.ContextVar[bool] = contextvars.ContextVar("live", default=True)


def live_for(code: str | None) -> bool:
    if not ACCESS_CODES:
        return True
    code = (code or "").strip()
    return bool(code) and any(hmac.compare_digest(code.encode(), c.encode()) for c in ACCESS_CODES)


def set_live(value: bool) -> contextvars.Token:
    return _live.set(value)


def reset_live(token: contextvars.Token) -> None:
    _live.reset(token)


def live() -> bool:
    """Whether this request may use the paid APIs."""
    return _live.get()


def _key(name: str) -> str | None:
    if _flag("FORCE_MOCKS") or USE_MOCK or not _live.get():
        return None
    return os.getenv(name) or None


def exa_key() -> str | None:
    return _key("EXA_API_KEY")


def context_key() -> str | None:
    return _key("CONTEXT_DEV_API_KEY")


def gemini_key() -> str | None:
    return _key("GEMINI_API_KEY")


GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")



def elevenlabs_key() -> str | None:
    return _key("ELEVENLABS_API_KEY")

OFFICIAL_DOMAINS = TRUSTED_DOMAINS

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
