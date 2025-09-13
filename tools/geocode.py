from __future__ import annotations

import os
import difflib
from typing import Optional, Tuple
import time
import requests
import re
import sys


# Keep a tiny demo map for offline/dev usage
DEMO_GEOCODES: dict[str, tuple[float, float]] = {
    "Austin, TX": (30.2672, -97.7431),
    "San Marcos, TX": (29.8833, -97.9414),
    "San Antonio, TX": (29.4241, -98.4936),
    "Dallas, TX": (32.7767, -96.7970),
    # A couple more for convenience
    "Baltimore, MD": (39.2904, -76.6122),
    "Orlando, FL": (28.5383, -81.3792),
    "New York, NY": (40.7128, -74.0060),
    "Los Angeles, CA": (34.0522, -118.2437),
    "Chicago, IL": (41.8781, -87.6298),
    "Silver Spring, MD": (38.9907, -77.0261),
    "Denver, CO": (39.7392, -104.9903),
    "Seattle, WA": (47.6062, -122.3321),
    "Phoenix, AZ": (33.4484, -112.0740),
    "Boston, MA": (42.3601, -71.0589),
    "San Francisco, CA": (37.7749, -122.4194),
    "San Diego, CA": (32.7157, -117.1611),
    "San Jose, CA": (37.3382, -121.8863),
    "Houston, TX": (29.7604, -95.3698),
    "Philadelphia, PA": (39.9526, -75.1652),
    "Washington, DC": (38.9072, -77.0369),
    "Boulder, CO": (40.0150, -105.2705),
    "Jacksonville, FL": (30.3322, -81.6557),
    "Waco, TX": (31.5493, -97.1467),
    "Kyle, TX": (29.9897, -97.8731),
}

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


class DemoGeocoder:
    def resolve(self, loc: str) -> Optional[Tuple[float, float]]:
        if not loc:
            return None
        key = loc.strip()
        # Expand city-only using hints, if applicable
        low = key.lower()
        if "," not in key and low in CITY_TO_STATE:
            key = f"{key.title()}, {CITY_TO_STATE[low]}"
        for name, coords in DEMO_GEOCODES.items():
            if name.lower() == key.lower():
                return coords
        # Fuzzy match city within same-state demo entries when spelled close
        m = re.match(r"^\s*([A-Za-z .-]+)\s*,\s*([A-Za-z]{2})\s*$", key)
        if m:
            city = (m.group(1) or "").strip().lower()
            st = (m.group(2) or "").upper()
            # Candidate demo city names for this state
            candidates = [
                name.split(",")[0].strip()
                for name in DEMO_GEOCODES.keys()
                if name.upper().endswith(", " + st)
            ]
            # Try close match
            if candidates:
                match = difflib.get_close_matches(city.title(), candidates, n=1, cutoff=0.8)
                if match:
                    canon = f"{match[0]}, {st}"
                    coords = DEMO_GEOCODES.get(canon)
                    if coords:
                        return coords
        # Minimal ZIP mapping to closest demo city
        if key.isdigit() and len(key) == 5:
            zip_to_city = {
                "78701": "Austin, TX",
                "78705": "Austin, TX",
                "78666": "San Marcos, TX",
                "78205": "San Antonio, TX",
                "75201": "Dallas, TX",
            }
            city = zip_to_city.get(key)
            if city:
                return DEMO_GEOCODES[city]
        return None


class CensusGeocoder:
    """US Census Geocoder (oneline address to lat/lon).

    Docs: https://geocoding.geo.census.gov/
    Endpoint: /geocoder/locations/onelineaddress
    Response: addressMatches[0].coordinates {x: lon, y: lat}
    """

    BASE = os.getenv("CENSUS_GEOCODER_URL", "https://geocoding.geo.census.gov")
    BENCHMARK = os.getenv("CENSUS_BENCHMARK", "Public_AR_Current")

    def _headers(self) -> dict:
        return {
            "User-Agent": os.getenv("USER_AGENT", "weather-bot/0.1 (demo@example.com)"),
            "Accept": "application/json",
        }

    def _req(self, path: str, params: dict) -> Optional[dict]:
        url = f"{self.BASE}{path}"
        try:
            if _debug_enabled():
                print(f"[geocode] census_request url={url} params={params}", file=sys.stderr)
            r = requests.get(url, params=params, headers=self._headers(), timeout=10)
            r.raise_for_status()
            return r.json()  # type: ignore[return-value]
        except requests.RequestException as e:
            if _debug_enabled():
                print(f"[geocode] census_error: {e}", file=sys.stderr)
            return None

    def _onelineaddress(self, address: str) -> Optional[Tuple[float, float]]:
        data = self._req(
            "/geocoder/locations/onelineaddress",
            {"address": address, "benchmark": self.BENCHMARK, "format": "json"},
        )
        if not data:
            return None
        matches = (data.get("result", {}).get("addressMatches", []) or [])
        if _debug_enabled():
            print(f"[geocode] census_matches(onelineaddress)={len(matches)} for '{address}'", file=sys.stderr)
        if not matches:
            return None
        coord = (matches[0].get("coordinates") or {})
        lon = coord.get("x")
        lat = coord.get("y")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            return float(lat), float(lon)
        return None

    def _geographies_onelineaddress(self, address: str) -> Optional[Tuple[float, float]]:
        # Some place names resolve better via the geographies endpoint
        data = self._req(
            "/geocoder/geographies/onelineaddress",
            {
                "address": address,
                "benchmark": self.BENCHMARK,
                "vintage": os.getenv("CENSUS_VINTAGE", "Current_Census"),
                "format": "json",
            },
        )
        if not data:
            return None
        matches = (data.get("result", {}).get("addressMatches", []) or [])
        if _debug_enabled():
            print(f"[geocode] census_matches(geographies)={len(matches)} for '{address}'", file=sys.stderr)
        if not matches:
            return None
        coord = (matches[0].get("coordinates") or {})
        lon = coord.get("x")
        lat = coord.get("y")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            return float(lat), float(lon)
        return None

    def resolve(self, loc: str) -> Optional[Tuple[float, float]]:
        if not loc:
            return None
        # Expand city-only using hints as a nicety (still works without)
        key = loc.strip()
        low = key.lower()
        if "," not in key and low in CITY_TO_STATE:
            key = f"{key.title()}, {CITY_TO_STATE[low]}"

        # Prefer exact City, ST formatting
        address = key
        m = re.match(r"^\s*([A-Za-z .-]+)\s*,\s*([A-Za-z]{2})\s*$", key)
        if m:
            city = (m.group(1) or "").strip().title()
            st = (m.group(2) or "").upper()
            address = f"{city}, {st}"

        # Try standard onelineaddress
        val = self._onelineaddress(address)
        if val is not None:
            return val

        # Try geographies onelineaddress
        val = self._geographies_onelineaddress(address)
        if val is not None:
            return val

        # Last resort: if we had City, ST tokens, try the 'locations/address' endpoint with city/state
        if m:
            data = self._req(
                "/geocoder/locations/address",
                {
                    "city": city,
                    "state": st,
                    "benchmark": self.BENCHMARK,
                    "format": "json",
                },
            )
            matches = (data or {}).get("result", {}).get("addressMatches", []) if data else []
            if _debug_enabled():
                print(f"[geocode] census_matches(address city/state)={len(matches)} for '{city}, {st}'", file=sys.stderr)
            if matches:
                coord = (matches[0].get("coordinates") or {})
                lon = coord.get("x")
                lat = coord.get("y")
                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                    return float(lat), float(lon)
        return None


def _provider_name() -> str:
    # Default to census to avoid demo interfering in real usage
    return (os.getenv("GEO_PROVIDER") or "census").strip().lower()


def _debug_enabled() -> bool:
    val = (os.getenv("GEOCODE_DEBUG") or os.getenv("WEATHER_BOT_DEBUG") or "").strip().lower()
    return val in {"1", "true", "yes", "on"}


def _provider():
    name = _provider_name()
    if name == "census":
        return CensusGeocoder()
    # default
    return DemoGeocoder()


_CACHE: dict[str, tuple[Optional[Tuple[float, float]], float]] = {}


def _ttl_seconds() -> int:
    try:
        return int(os.getenv("GEOCODE_TTL_SECONDS", "3600"))
    except ValueError:
        return 3600


def geocode(loc: str) -> Optional[Tuple[float, float]]:
    """Return (lat, lon) for a location string using the selected provider.

    Providers:
      - demo (default): small static map
      - census: US Census Geocoder

    Caches successful lookups to minimize repeated calls.
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
    # Scope cache by provider to avoid demo/census collisions
    cache_key = f"{provider}::{key.lower()}"
    hit = _CACHE.get(cache_key)
    if hit and hit[1] > now:
        if _debug_enabled():
            print(f"[geocode] cache_hit key='{cache_key}' -> {hit[0]}", file=sys.stderr)
        return hit[0]
    prov = _provider()
    val = prov.resolve(key)
    # If Census fails to resolve, try guarded fallbacks:
    if val is None and provider == "census":
        demo = DemoGeocoder()
        # 1) Demo fallback for exact key
        fallback = demo.resolve(key)
        if _debug_enabled():
            print(f"[geocode] census_miss key='{key}', demo_fallback -> {fallback}", file=sys.stderr)
        if fallback is not None:
            val = fallback
        else:
            # 2) If input is city-only with multiple tokens (no comma), try two-word then one-word fallbacks.
            if "," not in key and " " in key:
                tokens = [t for t in key.split() if t]
                # Build two-word candidate like "New York" -> prefer hint mapping if available
                two = " ".join(tokens[:2]).title() if len(tokens) >= 2 else None
                cand_two = None
                if two and two.lower() in CITY_TO_STATE:
                    cand_two = f"{two}, {CITY_TO_STATE[two.lower()]}"
                # Try two-word candidate(s) first
                for cand in [c for c in [cand_two, two] if c]:
                    v = prov.resolve(cand)
                    if v is None:
                        v = demo.resolve(cand)
                    if _debug_enabled():
                        print(f"[geocode] two-word attempt cand='{cand}' -> {v}", file=sys.stderr)
                    if v is not None:
                        val = v
                        break
                # If still not found, consider first-token fallback with guard prefixes
                if val is None:
                    first = tokens[0].title()
                    forbidden_first = {"New", "Los", "Las", "San", "Santa", "Saint", "St", "Fort", "North", "South", "East", "West", "Rio"}
                    if first not in forbidden_first:
                        alt = None
                        if first.lower() in CITY_TO_STATE:
                            alt = f"{first}, {CITY_TO_STATE[first.lower()]}"
                        if _debug_enabled():
                            print(f"[geocode] trying first-token fallback: first='{first}', alt='{alt}'", file=sys.stderr)
                        for cand in [c for c in [alt, first] if c]:
                            v = prov.resolve(cand)
                            if v is None:
                                v = demo.resolve(cand)
                            if _debug_enabled():
                                print(f"[geocode] first-token attempt cand='{cand}' -> {v}", file=sys.stderr)
                            if v is not None:
                                val = v
                                break
    _CACHE[cache_key] = (val, now + ttl)
    if _debug_enabled():
        print(f"[geocode] cache_store key='{cache_key}' -> {val}", file=sys.stderr)
    return val
