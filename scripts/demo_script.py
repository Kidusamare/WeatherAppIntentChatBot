from __future__ import annotations

import uuid
import sys
from pathlib import Path

# Ensure project root (weather-bot) is on sys.path when run from repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nlu.intent_model import IntentClassifier
from nlu.entities import parse_location, parse_datetime, parse_units
from core.policy import respond


SCRIPT = [
    "hello",
    "weather now in Austin, TX",
    "and tonight?",
    "how about tomorrow?",
    "any weather alerts for Austin, TX?",
    "weather now in Orlando, FL in celsius",
]


def run_script(session_id: str) -> None:
    clf = IntentClassifier()
    examples = clf.load_yaml("data/nlu.yml")
    clf.fit(examples)

    print("Weather Chatbot Demo — scripted run")
    for text in SCRIPT:
        intent, conf = clf.predict(text)
        entities = {
            "location": parse_location(text),
            "datetime": parse_datetime(text),
            "units": parse_units(text),
        }
        reply = respond(intent, conf, entities, session_id)
        print(
            f"\n> {text}\nintent={intent} conf={conf:.2f} entities={entities}\n{reply}"
        )


def interactive(session_id: str) -> None:
    print("\nInteractive mode. Type 'exit' to quit.")
    clf = IntentClassifier()
    examples = clf.load_yaml("data/nlu.yml")
    clf.fit(examples)
    while True:
        try:
            text = input("> ")
        except EOFError:
            break
        if text.strip().lower() in {"exit", "quit"}:
            break
        intent, conf = clf.predict(text)
        entities = {
            "location": parse_location(text),
            "datetime": parse_datetime(text),
            "units": parse_units(text),
        }
        reply = respond(intent, conf, entities, session_id)
        print(reply)


def main():
    sid = f"demo-{uuid.uuid4().hex[:6]}"
    run_script(sid)
    interactive(sid)


if __name__ == "__main__":
    main()
