import re
from typing import Optional

WEEKDAYS = {"monday","tuesday","wednesday","thursday","friday","saturday","sunday"}

def parse_location(text: str) -> Optional[str]:
    # "City, ST" or ZIP
    m = re.search(r"\b([A-Za-z]+(?:\s[A-Za-z]+)*),\s*([A-Z]{2})\b", text)
    if m:
        return f"{m.group(1).title()}, {m.group(2)}"
    z = re.search(r"\b(\d{5})\b", text)
    if z:
        return z.group(1)
    return None

def parse_datetime(text: str) -> str:
    t = text.lower()
    if "tomorrow" in t or "tmrw" in t: return "tomorrow"
    if "tonight" in t: return "tonight"
    if "weekend" in t: return "weekend"
    for d in WEEKDAYS:
        if d in t:
            return d
    return "today"

def parse_units(text: str) -> str:
    t = text.lower()
    if "celsius" in t or re.search(r"\b(c|metric)\b", t):
        return "metric"
    return "imperial"
