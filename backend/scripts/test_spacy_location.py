from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv()
except Exception:
    pass

# Force spaCy backend for this test script
os.environ["LOCATION_BACKEND"] = "spacy"

# Ensure project path for local imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nlu.entities import parse_location  # noqa: E402


def ensure_spacy() -> bool:
    try:
        import spacy  # noqa: F401
        return True
    except Exception:
        return False


def run_interactive():
    print("spaCy location parsing test (backend forced to spaCy)")
    if not ensure_spacy():
        print("ERROR: spaCy not installed. Run 'pip install spacy' and 'python -m spacy download en_core_web_sm'.")
        return
    print("Type a sentence; I'll print the parsed location. Empty line to exit.")
    while True:
        try:
            text = input("> ")
        except EOFError:
            print()
            break
        if not text.strip():
            break
        loc = parse_location(text)
        print(f"location={loc}")


def run_batch(args: list[str]):
    if not ensure_spacy():
        print("ERROR: spaCy not installed. Run 'pip install spacy' and 'python -m spacy download en_core_web_sm'.")
        return 1
    for phrase in args:
        loc = parse_location(phrase)
        print(f"{phrase}\t{loc}")
    return 0


def main():
    if len(sys.argv) > 1:
        raise SystemExit(run_batch(sys.argv[1:]))
    run_interactive()


if __name__ == "__main__":
    main()

