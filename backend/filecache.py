"""Small JSON file cache shared by the Exa and Gemini wrappers. Never stores API keys."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

log = logging.getLogger(__name__)


def key(*parts) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def read(path: Path, k: str):
    try:
        entry = json.loads(path.read_text(encoding="utf-8")).get(k)
        if not entry:
            return None
        expires = datetime.fromisoformat(entry["expires_at"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return entry["value"] if datetime.now(timezone.utc) < expires else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def write(path: Path, k: str, value, ttl: timedelta) -> None:
    try:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        data[k] = {"expires_at": (datetime.now(timezone.utc) + ttl).isoformat(), "value": value}
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        log.warning("Could not write cache %s: %s", path.name, exc)
