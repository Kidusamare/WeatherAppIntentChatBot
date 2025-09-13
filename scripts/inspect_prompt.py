from __future__ import annotations

import json
import sys
from pathlib import Path

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


def main() -> None:
    clf = get_intent_classifier()
    examples = clf.load_yaml("data/nlu.yml")
    clf.fit(examples)

    import os
    print("Inspector — type text; outputs parsed entities, intent, and geocode.")
    print("Ctrl-D or empty line to exit.")
    print("Provider:", _geo_provider())
    print("Location backend:", (os.getenv("LOCATION_BACKEND") or "spacy"))
    while True:
        try:
            text = input("> ")
        except EOFError:
            print()
            break
        if not text.strip():
            break

        intent, conf = clf.predict(text)
        loc_raw = parse_location(text) or ""
        loc_canon = canonicalize_location(loc_raw) if loc_raw else ""
        coords = geocode(loc_canon or loc_raw) if (loc_canon or loc_raw) else None
        dt = parse_datetime(text)
        units = parse_units(text)

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
        }
        print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
