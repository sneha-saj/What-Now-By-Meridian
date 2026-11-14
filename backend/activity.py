"""Live activity events (what Exa and Gemini are doing), streamed to the UI by /chat/stream.

The current request's emitter lives in a ContextVar, so search code can report without passing it around.
"""

from __future__ import annotations

import contextvars
from typing import Callable

_emit: contextvars.ContextVar[Callable[[dict], None] | None] = contextvars.ContextVar("activity_emit", default=None)


def set_emitter(fn: Callable[[dict], None] | None):
    return _emit.set(fn)


def emit(event: dict) -> None:
    fn = _emit.get()
    if fn is not None:
        try:
            fn(event)
        except Exception:  # noqa: BLE001 - activity is best-effort, never break a request
            pass
