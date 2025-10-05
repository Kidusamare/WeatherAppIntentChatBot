from __future__ import annotations

import os
from typing import Optional
import re

from .entities import STATE_ABBR

_NLP = None


def _normalize_city_state(text: str) -> str:
    t = text.strip()
    # If "City, ST"
    m = re.match(r"^\s*([A-Za-z .-]+)\s*,\s*([A-Za-z]{2})\s*$", t)
    if m:
        return f"{(m.group(1) or '').strip().title()}, {(m.group(2) or '').upper()}"
    # If "City StateName"
    low = t.lower()
    for fullname, abbr in STATE_ABBR.items():
        pattern = rf"^\s*([A-Za-z .-]+)\s*,?\s+{fullname}\s*$"
        if re.search(pattern, t, flags=re.IGNORECASE):
            city = re.sub(rf"\s*,?\s+{fullname}\s*$", "", t, flags=re.IGNORECASE)
            return f"{city.strip().title()}, {abbr}"
    return t.title()


def _get_nlp():
    global _NLP
    if _NLP is not None:
        return _NLP
    try:
        import spacy
        model = os.getenv("SPACY_MODEL", "en_core_web_sm")
        _NLP = spacy.load(model)
        return _NLP
    except Exception:
        return None


def extract_location_spacy(text: str) -> Optional[str]:
    """Extract a location using spaCy NER (GPE/LOC) if spaCy is available.

    Default backend tries spaCy first for robustness; gracefully returns None if
    spaCy or the model is missing, so regex parsing can take over.
    """
    nlp = _get_nlp()
    if nlp is None:
        return None
    doc = nlp(text)
    # Prefer longest GPE/LOC span
    ents = [e for e in doc.ents if e.label_ in {"GPE", "LOC"}]
    if not ents:
        return None
    ent = max(ents, key=lambda e: len(e.text))
    return _normalize_city_state(ent.text)
