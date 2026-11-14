"""Settings loaded from the repo-root .env. Missing keys => mock mode for that service."""

import os
from pathlib import Path

from dotenv import load_dotenv
from countries.finland import TRUSTED_DOMAINS

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _flag(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in ("1", "true", "yes", "on")


USE_MOCK = _flag("USE_MOCK")


def _key(name: str) -> str | None:
    if _flag("FORCE_MOCKS") or USE_MOCK:
        return None
    return os.getenv(name) or None


def exa_key() -> str | None:
    return _key("EXA_API_KEY")


def context_key() -> str | None:
    return _key("CONTEXT_DEV_API_KEY")


def gemini_key() -> str | None:
    return _key("GEMINI_API_KEY")


GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

ENABLE_ELEVENLABS = _flag("ENABLE_ELEVENLABS")

OFFICIAL_DOMAINS = TRUSTED_DOMAINS

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
