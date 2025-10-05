from __future__ import annotations

import os
import sys
import uuid
import json
from pathlib import Path
from typing import Dict, Any

# Ensure project path for local imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv()
except Exception:
    pass
from backend.nlu import get_intent_classifier
from backend.tools.geocode import _provider_name as _geo_provider_name
from backend.nlu.entities import parse_location, parse_datetime, parse_units
from backend.core.policy import respond
from backend.core.memory import get_prompt_cache


HELP_TEXT = (
    "Commands: /help, /units [metric|imperial], /cache, /reset, /quit\n"
    "Examples: 'weather now in Austin, TX', 'and tonight?', 'any alerts for Dallas, TX?'"
)


def suggest_followups(intent: str) -> str:
    if intent in {"get_current_weather", "get_forecast"}:
        return "(try: 'any weather alerts for City, ST?')"
    if intent == "get_alerts":
        return "(try: 'forecast for tomorrow in City, ST')"
    if intent == "greet":
        return "(try: 'weather now in City, ST')"
    return ""


def interactive_loop(session_id: str) -> None:
    clf = get_intent_classifier()
    examples = clf.load_yaml("data/nlu.yml")
    clf.fit(examples)

    units_pref = "imperial"
    print("Weather Chatbot — interactive demo. Type /help for commands.")

    while True:
        try:
            text = input("> ")
        except EOFError:
            print()
            break
        if not text.strip():
            continue
        low = text.strip().lower()

        # Commands
        if low in {"/quit", "/exit"}:
            break
        if low == "/help":
            print(HELP_TEXT)
            continue
        if low == "/cache":
            history = get_prompt_cache(session_id)
            if not history:
                print("Prompt cache is empty.")
            else:
                # Show the five most recent turns
                for item in history[-5:]:
                    print(json.dumps(item, ensure_ascii=False, indent=2))
            continue
        if low.startswith("/units"):
            parts = low.split()
            if len(parts) == 2 and parts[1] in {"metric", "imperial"}:
                units_pref = parts[1]
                print(f"OK. Units set to {units_pref}.")
            else:
                print("Usage: /units metric|imperial")
            continue
        if low == "/reset":
            # New session id to clear server-side memory semantics
            session_id = f"demo-{uuid.uuid4().hex[:6]}"
            print("Session reset.")
            continue

        # NLU
        intent, conf = clf.predict(text)
        entities: Dict[str, Any] = {
            "location": parse_location(text),
            "datetime": parse_datetime(text),
            "units": parse_units(text),
        }
        # Honor user-set units preference if no explicit units provided
        if entities.get("units") == "imperial" and units_pref == "metric":
            entities["units"] = "metric"
        if entities.get("units") == "metric" and units_pref == "imperial":
            entities["units"] = units_pref

        reply = respond(intent, conf, entities, session_id)
        print(reply)
        tip = suggest_followups(intent)
        if tip:
            print(tip)


def main() -> None:
    sid = f"demo-{uuid.uuid4().hex[:6]}"
    print("Starting demo. New session:", sid)
    print("Geocoder provider:", _geo_provider_name())
    print("Location backend:", (os.getenv("LOCATION_BACKEND") or "spacy"))
    print("Intent backend:", (os.getenv("INTENT_BACKEND") or "tfidf"))
    interactive_loop(sid)


if __name__ == "__main__":
    main()
