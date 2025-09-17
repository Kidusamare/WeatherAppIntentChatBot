from collections import defaultdict
from typing import Any, Dict, List
import time

# SESSION holds per-session arbitrary keys like last_location
SESSION = defaultdict(dict)

# PROMPTS keeps a rolling cache of recent intent/entity pairs per session
_PROMPTS: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
_PROMPT_LIMIT = 20


def get_mem(sid, key, default=None):
    return SESSION[sid].get(key, default)


def set_mem(sid, key, val):
    SESSION[sid][key] = val


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
    buf = _PROMPTS[sid]
    buf.append(payload)
    if len(buf) > _PROMPT_LIMIT:
        del buf[0]
    # Expose rolling cache via session dict for convenience
    SESSION[sid]["prompt_cache"] = list(buf)
    return payload


def get_prompt_cache(sid: str) -> List[Dict[str, Any]]:
    return list(_PROMPTS.get(sid, []))

