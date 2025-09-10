import sys
from pathlib import Path

# Ensure project root (weather-bot) is on sys.path when run from repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nlu.intent_model import IntentClassifier
from nlu.entities import parse_location, parse_datetime, parse_units

def main():
    clf = IntentClassifier()
    examples = clf.load_yaml("data/nlu.yml")
    clf.fit(examples)
    print("Weather Chatbot NLU (Day 1). Type 'exit' to quit.")
    while True:
        text = input("> ")
        if text.strip().lower() in {"exit","quit"}:
            break
        intent, conf = clf.predict(text)
        loc = parse_location(text)
        dt = parse_datetime(text)
        units = parse_units(text)
        print(f"intent={intent} (conf={conf:.2f}), entities={{'location': {loc}, 'datetime': '{dt}', 'units': '{units}'}}")
if __name__ == "__main__":
    main()
