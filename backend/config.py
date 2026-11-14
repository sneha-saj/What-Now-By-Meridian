"""Settings loaded from the repo-root .env. Missing keys => mock mode for that service."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _flag(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in ("1", "true", "yes", "on")


def _key(name: str) -> str | None:
    if _flag("FORCE_MOCKS"):
        return None
    return os.getenv(name) or None


def exa_key() -> str | None:
    return _key("EXA_API_KEY")


def gemini_key() -> str | None:
    return _key("GEMINI_API_KEY")


GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

ENABLE_OXYLABS = _flag("ENABLE_OXYLABS")
ENABLE_ELEVENLABS = _flag("ENABLE_ELEVENLABS")

OFFICIAL_DOMAINS = ["migri.fi", "kela.fi", "infofinland.fi", "tyomarkkinatori.fi"]

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
