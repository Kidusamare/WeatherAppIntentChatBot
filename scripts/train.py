import sys
from pathlib import Path

# Ensure project root (weather-bot) is on sys.path when run from repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nlu.intent_model import IntentClassifier
def main():
    clf = IntentClassifier()
    examples = clf.load_yaml("data/nlu.yml")
    clf.fit(examples)
    print(f"Trained on {len(examples)} examples.")
if __name__ == "__main__":
    main()
