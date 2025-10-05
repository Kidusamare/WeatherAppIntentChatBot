from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path


SESSION_PREFIX = "inspect"

try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv()
except Exception:
    pass

# Ensure project path for local imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nlu import get_intent_classifier
from nlu.entities import parse_location, parse_datetime, parse_units
from tools.geocode import geocode, canonicalize_location, _provider_name as _geo_provider
from core.memory import append_prompt_snapshot, get_mem, get_prompt_cache, set_mem


def main() -> None:
    clf = get_intent_classifier()
    examples = clf.load_yaml("data/nlu.yml")
    clf.fit(examples)

    import os

    session_id = f"{SESSION_PREFIX}-{uuid.uuid4().hex[:6]}"
    print("Inspector — type text; outputs parsed entities, intent, and geocode.")
    print("Commands: /cache, /session [id], /reset, /quit")
    print("Ctrl-D or empty line to exit.")
    print("Provider:", _geo_provider())
    print("Location backend:", (os.getenv("LOCATION_BACKEND") or "spacy"))
    print("Session:", session_id)
    while True:
        try:
            text = input("> ")
        except EOFError:
            print()
            break
        if not text.strip():
            break

        low = text.strip().lower()
        if low in {"/quit", "/exit"}:
            break
        if low == "/reset":
            session_id = f"{SESSION_PREFIX}-{uuid.uuid4().hex[:6]}"
            print("Session reset ->", session_id)
            continue
        if low.startswith("/session"):
            parts = text.split()
            if len(parts) == 2:
                session_id = parts[1]
                print("Session set ->", session_id)
            else:
                print("Usage: /session <id>")
            continue
        if low == "/cache":
            history = get_prompt_cache(session_id)
            if not history:
                print("Prompt cache is empty for", session_id)
            else:
                for item in history[-5:]:
                    print(json.dumps(item, ensure_ascii=False, indent=2))
            continue

        intent, conf = clf.predict(text)
        loc_raw = parse_location(text) or ""
        loc_canon = canonicalize_location(loc_raw) if loc_raw else ""
        last_entities = get_mem(session_id, "last_entities") or {}
        used_cache_loc = False
        if not (loc_canon or loc_raw):
            fallback_loc = (last_entities.get("location") or "") if last_entities else ""
            if fallback_loc:
                loc_raw = fallback_loc
                loc_canon = canonicalize_location(loc_raw)
                used_cache_loc = True
        coords = geocode(loc_canon or loc_raw) if (loc_canon or loc_raw) else None
        dt = parse_datetime(text)
        units = parse_units(text)

        resolved_entities = {
            "location": loc_canon or loc_raw or None,
            "datetime": dt,
            "units": units,
        }

        out = {
            "text": text,
            "intent": intent,
            "confidence": round(float(conf), 3),
            "location_raw": loc_raw,
            "location_canonical": loc_canon,
            "geocode_provider": _geo_provider(),
            "geocode_coords": coords,
            "datetime": dt,
            "units": units,
            "session": session_id,
            "location_from_cache": used_cache_loc,
        }
        print(json.dumps(out, ensure_ascii=False))

        append_prompt_snapshot(
            session_id,
            intent=intent,
            confidence=float(conf),
            entities=resolved_entities,
            extras={"text": text},
        )
        set_mem(session_id, "last_entities", resolved_entities)
        if resolved_entities.get("location"):
            set_mem(session_id, "last_location", resolved_entities["location"])


if __name__ == "__main__":
    main()
