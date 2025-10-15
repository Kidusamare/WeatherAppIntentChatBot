import re
from typing import Optional
import os

WEEKDAYS = {"monday","tuesday","wednesday","thursday","friday","saturday","sunday"}
LOCATION_STOPWORDS = {
    "weather","forecast","alerts","alert","warning","warnings","advisory","now",
    "today","tonight","tomorrow","weekend","celsius","fahrenheit","metric","imperial",
    "please","thanks","thank","you","and","or","for","on","at","near","in",
    "right","currently","presently"
}

# US state full names to USPS abbreviations (for simple geocoding parsing)
STATE_ABBR = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
}


def parse_location(text: str) -> Optional[str]:
    # Try spaCy NER by default; fall back to regex/ZIP if unavailable
    backend = (os.getenv("LOCATION_BACKEND") or "spacy").strip().lower()
    if backend != "regex":
        try:
            from .loc_extractor import extract_location_spacy
            loc = extract_location_spacy(text)
            if loc:
                # If spaCy yielded only a state (full name or USPS), fall back to regex
                low = loc.strip().lower()
                up = loc.strip().upper()
                if (low in STATE_ABBR.keys()) or (up in STATE_ABBR.values()) or low.startswith("state of "):
                    loc = None
                else:
                    return loc
        except Exception:
            # fall back to regex parsing
            pass
    # "City, ST" or ZIP
    # Prefer common prepositions before the city to avoid capturing
    # preceding words like "what's weather".
    # Accept "in City, ST" (restrict to 'in' to avoid greedy captures like 'for tomorrow in City, ST')
    m_in = re.search(r"\bin\s+([A-Za-z]+(?:\s[A-Za-z]+)*)\s*,\s*([A-Za-z]{2})\b", text, flags=re.IGNORECASE)
    if m_in:
        city = (m_in.group(1) or "").strip()
        state = (m_in.group(2) or "").upper()
        return f"{city.title()}, {state}"

    # Accept "in City ST" (no comma) where ST is a separate 2-letter token (restrict to 'in')
    m_in_abbr = re.search(r"\bin\s+([A-Za-z][A-Za-z .-]*?)\s+([A-Za-z]{2})\b", text, flags=re.IGNORECASE)
    if m_in_abbr:
        city = (m_in_abbr.group(1) or "").strip()
        state = (m_in_abbr.group(2) or "").upper()
        return f"{city.title()}, {state}"

    # Support "in City StateName" (no comma), US-only.
    low = text.lower()
    for fullname, abbr in STATE_ABBR.items():
        # Build a regex that looks for "in <city> <state full name>"
        # Accept optional comma before state name.
        # Use IGNORECASE to match mixed-case user input.
        pattern = rf"\bin\s+([A-Za-z]+(?:\s[A-Za-z]+)*)\s*,?\s+{re.escape(fullname)}\b"
        m_full = re.search(pattern, text, flags=re.IGNORECASE)
        if m_full:
            city = (m_full.group(1) or "").strip()
            return f"{city.title()}, {abbr}"

    # Accept free-form "... City ST" anywhere (no leading preposition), where ST is a valid USPS code.
    # Pick the last such occurrence to avoid earlier words.
    st_set = set(STATE_ABBR.values()) | {"DC"}
    m_any = None
    st = None
    # Only accept two-letter state if it appears at the end (optionally followed by punctuation)
    for m in re.finditer(r"([A-Za-z][A-Za-z .-]*?)\s*,?\s+([A-Za-z]{2})(?=\s*$|[?.,!]\s*$)", text, flags=re.IGNORECASE):
        cand_st = (m.group(2) or "").upper()
        if cand_st in st_set:
            m_any = m
            st = cand_st
    if m_any and st:
        city = (m_any.group(1) or "").strip()
        # Keep only the trailing word group as city (avoid capturing preceding words like 'in'/'for')
        city = re.sub(r".*\b(in|for|near|at)\s+", "", city, flags=re.IGNORECASE)
        if city:
            return f"{city.title()}, {st}"

    # Support "in City" with no state when clearly delimited.
    m_in_city_only = re.search(
        r"\b(?:in|for|near|at)\s+([A-Za-z]+(?:\s[A-Za-z]+)*)\b(?=\s+(?:for|please|now|today|tonight|tomorrow|this|next|and|right|currently|presently)\b|[?.,!]|$)",
        text,
        flags=re.IGNORECASE,
    )
    if m_in_city_only:
        cand = (m_in_city_only.group(1) or "").strip()
        low_cand = cand.lower()
        if low_cand and low_cand not in LOCATION_STOPWORDS and low_cand not in WEEKDAYS:
            return cand.title()
    # Find all city/state patterns and pick the last one to avoid greedy matches
    # across earlier words (e.g., "what's weather in Austin, TX").
    # Try to find the last occurrence of ", ST" and then capture the
    # immediate word sequence before that comma as the city.
    last_state = None
    for m in re.finditer(r",\s*([A-Za-z]{2})\b", text):
        last_state = m
    if last_state:
        state = (last_state.group(1) or "").upper()
        before = text[: last_state.start()]
        cm = re.search(r"([A-Za-z]+(?:\s[A-Za-z]+)*)\s*$", before)
        if cm:
            city = (cm.group(1) or "").strip()
            return f"{city.title()}, {state}"
    z = re.search(r"\b(\d{5})\b", text)
    if z:
        return z.group(1)
    # As a last resort, if the entire text looks like a simple place name
    # (1-3 words, letters only) and isn't an obvious stopword, treat it as a city.
    simple = text.strip()
    if re.fullmatch(r"[A-Za-z]+(?:\s[A-Za-z]+){0,2}", simple):
        low_simple = simple.lower()
        words = {w.strip() for w in low_simple.split() if w.strip()}
        if (
            low_simple not in LOCATION_STOPWORDS
            and low_simple not in WEEKDAYS
            and not words.intersection(LOCATION_STOPWORDS)
            and not words.intersection(WEEKDAYS)
        ):
            return simple.title()
    return None

def parse_datetime(text: str) -> str:
    t = text.lower()
    # Fine-grained phrases
    if re.search(r"\b(later today|this afternoon|afternoon)\b", t):
        return "today_afternoon"
    if re.search(r"\b(this morning|morning)\b", t):
        return "today_morning"
    if re.search(r"\b(this evening)\b", t):
        return "today_evening"

    # Tomorrow variants (accept common misspellings)
    if re.search(r"\btomm?o?r?row\b", t):  # matches tomorrow, tommorow, tommorrow, tomorow
        # refine morning/night if present
        if re.search(r"\bmorning\b", t):
            return "tomorrow_morning"
        if re.search(r"\b(night|evening)\b", t):
            return "tomorrow_night"
        return "tomorrow"
    if re.search(r"\b(tomorrow morning)\b", t):
        return "tomorrow_morning"
    if re.search(r"\b(tomorrow night|tomorrow evening)\b", t):
        return "tomorrow_night"
    if "tomorrow" in t or "tmrw" in t:
        return "tomorrow"

    # Night/evening synonyms
    if "tonight" in t or re.search(r"\bevening\b", t):
        return "tonight"

    if "weekend" in t:
        return "weekend"

    # Weekday names and "next <weekday>" treated as the weekday
    for d in WEEKDAYS:
        if d in t or re.search(rf"\bnext\s+{d}\b", t):
            return d

    return "today"

def parse_units(text: str) -> str:
    t = text.lower()
    if "celsius" in t or re.search(r"\b(c|metric)\b", t):
        return "metric"
    return "imperial"
