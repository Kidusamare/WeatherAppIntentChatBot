from __future__ import annotations

import os
import time
from collections import deque
from threading import Lock
from typing import Any, Deque, Dict, List


_SESSION: Dict[str, Dict[str, Any]] = {}
_SESSION_EXPIRY: Dict[str, float] = {}
_PROMPTS: Dict[str, Deque[Dict[str, Any]]] = {}
_LOCK = Lock()

_PROMPT_LIMIT = 20
_SESSION_TTL_SECONDS = max(int(os.getenv("SESSION_TTL_SECONDS", "1800")), 60)
_SESSION_MAX = max(int(os.getenv("SESSION_MAX_ENTRIES", "5000")), 1)


def _purge_expired(now: float) -> None:
    """Remove expired or excess sessions to avoid unbounded memory."""

    expired = [sid for sid, expiry in _SESSION_EXPIRY.items() if expiry <= now]
    for sid in expired:
        _SESSION.pop(sid, None)
        _SESSION_EXPIRY.pop(sid, None)
        _PROMPTS.pop(sid, None)

    if len(_SESSION) <= _SESSION_MAX:
        return

    survivors = sorted(_SESSION_EXPIRY.items(), key=lambda item: item[1])
    for sid, _ in survivors:
        if len(_SESSION) <= _SESSION_MAX:
            break
        _SESSION.pop(sid, None)
        _SESSION_EXPIRY.pop(sid, None)
        _PROMPTS.pop(sid, None)


def _touch_session(sid: str, now: float) -> Dict[str, Any]:
    sess = _SESSION.setdefault(sid, {})
    _SESSION_EXPIRY[sid] = now + _SESSION_TTL_SECONDS
    return sess


def get_mem(sid, key, default=None):
    now = time.time()
    with _LOCK:
        _purge_expired(now)
        sess = _SESSION.get(str(sid))
        if not sess:
            return default
        _SESSION_EXPIRY[str(sid)] = now + _SESSION_TTL_SECONDS
        return sess.get(key, default)


def set_mem(sid, key, val):
    now = time.time()
    sid = str(sid)
    with _LOCK:
        _purge_expired(now)
        sess = _touch_session(sid, now)
        sess[key] = val


def append_prompt_snapshot(
    sid: str,
    *,
    intent: str,
    confidence: float,
    entities: Dict[str, Any] | None = None,
    extras: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Persist a lightweight record of the latest turn for follow-up context."""

    payload: Dict[str, Any] = {
        "intent": intent,
        "confidence": float(confidence),
        "entities": dict(entities or {}),
        "timestamp": time.time(),
    }
    if extras:
        payload.update(extras)

    now = payload["timestamp"]
    sid = str(sid)
    with _LOCK:
        _purge_expired(now)
        sess = _touch_session(sid, now)
        buf = _PROMPTS.get(sid)
        if buf is None:
            buf = deque(maxlen=_PROMPT_LIMIT)
            _PROMPTS[sid] = buf
        buf.append(payload)
        sess["prompt_cache"] = list(buf)
    return payload


def get_prompt_cache(sid: str) -> List[Dict[str, Any]]:
    now = time.time()
    sid = str(sid)
    with _LOCK:
        _purge_expired(now)
        buf = _PROMPTS.get(sid)
        if not buf:
            return []
        _SESSION_EXPIRY[sid] = now + _SESSION_TTL_SECONDS
        return list(buf)
