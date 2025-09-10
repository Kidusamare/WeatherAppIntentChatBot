from __future__ import annotations

import os
from typing import Optional, Tuple
import time
import requests


# Keep a tiny demo map for offline/dev usage
DEMO_GEOCODES: dict[str, tuple[float, float]] = {
    "Austin, TX": (30.2672, -97.7431),
    "San Marcos, TX": (29.8833, -97.9414),
    "San Antonio, TX": (29.4241, -98.4936),
    "Dallas, TX": (32.7767, -96.7970),
    # A couple more for convenience
    "Baltimore, MD": (39.2904, -76.6122),
    "Orlando, FL": (28.5383, -81.3792),
}

# Optional hints to expand city-only queries to City, ST (US-only convenience)
CITY_TO_STATE = {
    "baltimore": "MD",
    "orlando": "FL",
    "austin": "TX",
    "dallas": "TX",
    "san antonio": "TX",
    "san marcos": "TX",
}


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

    def resolve(self, loc: str) -> Optional[Tuple[float, float]]:
        if not loc:
            return None
        # Expand city-only using hints as a nicety (still works without)
        key = loc.strip()
        low = key.lower()
        if "," not in key and low in CITY_TO_STATE:
            key = f"{key.title()}, {CITY_TO_STATE[low]}"
        params = {
            "address": key,
            "benchmark": self.BENCHMARK,
            "format": "json",
        }
        url = f"{self.BASE}/geocoder/locations/onelineaddress"
        headers = {
            "User-Agent": os.getenv("USER_AGENT", "weather-bot/0.1 (demo@example.com)"),
            "Accept": "application/json",
        }
        try:
            r = requests.get(url, params=params, headers=headers, timeout=10)
            r.raise_for_status()
            data = r.json()  # type: ignore[assignment]
            matches = (
                (data or {}).get("result", {}).get("addressMatches", []) or []
            )
            if not matches:
                return None
            coord = (matches[0].get("coordinates") or {})
            lon = coord.get("x")
            lat = coord.get("y")
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                return float(lat), float(lon)
            return None
        except requests.RequestException:
            return None


def _provider_name() -> str:
    return (os.getenv("GEO_PROVIDER") or "demo").strip().lower()


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
    now = time.time()
    ttl = _ttl_seconds()
    hit = _CACHE.get(key)
    if hit and hit[1] > now:
        return hit[0]
    prov = _provider()
    val = prov.resolve(key)
    _CACHE[key] = (val, now + ttl)
    return val
