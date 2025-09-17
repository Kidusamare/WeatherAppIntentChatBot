from __future__ import annotations

import os
from typing import Optional, Tuple
import time
import re
import sys
try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover
    pd = None  # type: ignore
try:
    from rapidfuzz import process as rf_process, fuzz as rf_fuzz  # type: ignore
except Exception:  # pragma: no cover
    rf_process = None  # type: ignore
    rf_fuzz = None  # type: ignore




# Optional hints to expand city-only queries to City, ST (US-only convenience)
CITY_TO_STATE = {
    "baltimore": "MD",
    "orlando": "FL",
    "austin": "TX",
    "dallas": "TX",
    "san antonio": "TX",
    "san marcos": "TX",
    "new york": "NY",
    "los angeles": "CA",
    "chicago": "IL",
    "silver spring": "MD",
    "denver": "CO",
    "seattle": "WA",
    "phoenix": "AZ",
    "boston": "MA",
    "san francisco": "CA",
    "san diego": "CA",
    "san jose": "CA",
    "houston": "TX",
    "philadelphia": "PA",
    "washington": "DC",
    "boulder": "CO",
    "jacksonville": "FL",
    "waco": "TX",
    "kyle": "TX",
}

# Common misspellings → canonical city names (scoped by state when needed)
# This list can be extended over time as we observe user input.
MISSPELLINGS: dict[tuple[str, str], str] = {
    ("anapolis", "MD"): "Annapolis",
    ("silverspring", "MD"): "Silver Spring",
    ("dalls", "TX"): "Dallas",
    ("orlanndo", "FL"): "Orlando",
    ("houstan", "TX"): "Houston",
}


def canonicalize_location(loc: str) -> str:
    """Return a display-friendly location string.

    - If already "City, ST" → title/uppercased appropriately
    - If only city and we have a hint → "City, ST"
    - Otherwise → Title-cased input
    """
    if not loc:
        return ""
    key = loc.strip()
    m = re.match(r"^\s*([A-Za-z .-]+)\s*,\s*([A-Za-z]{2})\s*$", key)
    if m:
        city = (m.group(1) or "").strip().title()
        st = (m.group(2) or "").upper()
        # Apply misspelling correction when known
        corr = MISSPELLINGS.get((city.replace(" ", "").lower(), st))
        if corr:
            city = corr
        return f"{city}, {st}"
    low = key.lower()
    if "," not in key and low in CITY_TO_STATE:
        return f"{key.title()}, {CITY_TO_STATE[low]}"
    return key.title()


# DemoGeocoder removed.


# CensusGeocoder removed.


class LocalGeocoder:
    """Local CSV-backed geocoder using fuzzy matching on place names.

    Expects a CSV with columns (case-insensitive):
      - USPS (two-letter state)
      - name (place name; may include type like 'city', 'township', etc.)
      - lat (latitude)
      - long (longitude)

    Config:
      - US_PLACES_CSV: path to CSV (default: data/us_places.csv)
      - LOCAL_FUZZY_SCORE_CUTOFF: minimal score (default 80)
    """

    def __init__(self) -> None:
        self.csv_path = os.getenv("US_PLACES_CSV", str(os.path.join(os.path.dirname(__file__), "..", "data", "us_places.csv")))
        self._df: Optional[pd.DataFrame] = None

    def _load(self) -> Optional[pd.DataFrame]:
        if self._df is not None:
            return self._df
        if pd is None:
            if _debug_enabled():
                print("[geocode-local] pandas not available; cannot load local CSV", file=sys.stderr)
            return None
        try:
            df = pd.read_csv(self.csv_path)
        except Exception as e:
            if _debug_enabled():
                print(f"[geocode-local] failed to read CSV at {self.csv_path}: {e}", file=sys.stderr)
            return None
        cols = {c.lower(): c for c in df.columns}
        def pick(*names: str) -> Optional[str]:
            for n in names:
                if n.lower() in cols:
                    return cols[n.lower()]
            return None
        st_col = pick("usps", "state", "state_abbr", "st")
        name_col = pick("name", "place", "city")
        lat_col = pick("lat", "latitude")
        lon_col = pick("long", "lon", "lng", "longitude")
        if not all([st_col, name_col, lat_col, lon_col]):
            if _debug_enabled():
                print(f"[geocode-local] missing required columns in {self.csv_path}", file=sys.stderr)
            return None
        work = pd.DataFrame()
        work["state"] = df[st_col].astype(str).str.upper()
        work["name"] = df[name_col].astype(str)
        work["lat"] = pd.to_numeric(df[lat_col], errors="coerce")
        work["lon"] = pd.to_numeric(df[lon_col], errors="coerce")
        work = work.dropna(subset=["lat", "lon"])  # keep rows with coords
        # Normalized name for substring/fuzzy matching
        def norm(s: str) -> str:
            s = s.lower()
            s = re.sub(r"[^a-z0-9 ]+", " ", s)
            s = re.sub(r"\s+", " ", s).strip()
            return s
        work["norm"] = work["name"].map(norm)
        self._df = work
        if _debug_enabled():
            print(f"[geocode-local] loaded {len(work)} places from {self.csv_path}", file=sys.stderr)
        return self._df

    def resolve(self, loc: str) -> Optional[Tuple[float, float]]:
        df = self._load()
        if df is None or not loc:
            return None
        key = loc.strip()
        m = re.match(r"^\s*([A-Za-z .-]+)\s*,\s*([A-Za-z]{2})\s*$", key)
        state = None
        city = key
        if m:
            city = (m.group(1) or "").strip()
            state = (m.group(2) or "").upper()
        # Normalize search key
        def norm(s: str) -> str:
            s = s.lower()
            s = re.sub(r"[^a-z0-9 ]+", " ", s)
            s = re.sub(r"\s+", " ", s).strip()
            return s
        city_norm = norm(city)
        if not city_norm:
            return None
        # Restrict by state if provided
        subset = df
        if state is not None:
            subset = df[df["state"] == state]
            if subset.empty:
                subset = df
        # Try substring match first
        mask = subset["norm"].str.contains(city_norm, na=False)
        cand = subset[mask]
        if not cand.empty:
            row = cand.iloc[0]
            return float(row["lat"]), float(row["lon"])
        # Fuzzy match using rapidfuzz partial ratio
        cutoff = int(os.getenv("LOCAL_FUZZY_SCORE_CUTOFF", "80"))
        choices = list(subset["name"].values)
        if not choices or rf_process is None or rf_fuzz is None:
            return None
        best = rf_process.extractOne(city, choices, scorer=rf_fuzz.partial_ratio, score_cutoff=cutoff)
        if best is None:
            # widen to full dataset
            best = rf_process.extractOne(city, list(df["name"].values), scorer=rf_fuzz.partial_ratio, score_cutoff=cutoff)
            if best is None:
                return None
            match_name = best[0]
            row = df[df["name"] == match_name].iloc[0]
            return float(row["lat"]), float(row["lon"])
        match_name = best[0]
        row = subset[subset["name"] == match_name].iloc[0]
        return float(row["lat"]), float(row["lon"])



def _provider_name() -> str:
    # Only local provider backed by CSV
    return "local"


def _debug_enabled() -> bool:
    val = (os.getenv("GEOCODE_DEBUG") or os.getenv("WEATHER_BOT_DEBUG") or "").strip().lower()
    return val in {"1", "true", "yes", "on"}


def _provider():
    name = _provider_name()
    return LocalGeocoder()


_CACHE: dict[str, tuple[Optional[Tuple[float, float]], float]] = {}


def _ttl_seconds() -> int:
    try:
        return int(os.getenv("GEOCODE_TTL_SECONDS", "3600"))
    except ValueError:
        return 3600


def geocode(loc: str) -> Optional[Tuple[float, float]]:
    """Return (lat, lon) for a location string using the local CSV geocoder.

    Caches successful lookups to minimize repeated lookups against the CSV data.
    """
    if not loc:
        return None
    key = loc.strip()
    # Apply misspelling correction for City, ST inputs
    m = re.match(r"^\s*([A-Za-z .-]+)\s*,\s*([A-Za-z]{2})\s*$", key)
    if m:
        city = (m.group(1) or "").strip()
        st = (m.group(2) or "").upper()
        corr = MISSPELLINGS.get((city.replace(" ", "").lower(), st))
        if corr:
            key = f"{corr}, {st}"
            if _debug_enabled():
                print(f"[geocode] corrected misspelling -> '{key}'", file=sys.stderr)
    provider = _provider_name()
    if _debug_enabled():
        print(f"[geocode] provider={provider} query='{key}'", file=sys.stderr)
    now = time.time()
    ttl = _ttl_seconds()
    # Include provider in cache key to stay forward-compatible with future backends
    cache_key = f"{provider}::{key.lower()}"
    hit = _CACHE.get(cache_key)
    if hit and hit[1] > now:
        if _debug_enabled():
            print(f"[geocode] cache_hit key='{cache_key}' -> {hit[0]}", file=sys.stderr)
        return hit[0]
    prov = _provider()
    val = prov.resolve(key)
    _CACHE[cache_key] = (val, now + ttl)
    if _debug_enabled():
        print(f"[geocode] cache_store key='{cache_key}' -> {val}", file=sys.stderr)
    return val
