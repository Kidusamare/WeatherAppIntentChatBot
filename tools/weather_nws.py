"""Minimal National Weather Service (NWS) client utilities.

Demo-only geocoding for a few Texas cities. Fetches point metadata,
forecast periods, and active alerts with basic error handling.
"""

from __future__ import annotations

from typing import Optional, Tuple, List, Dict, Any
import os
import time
import requests

from tools.geocode import geocode


"""Geocoding now delegated to tools.geocode.geocode(provider=demo|census)."""


def _get_json(url: str) -> dict:
    headers = {
        # NWS requires a User-Agent with contact per policy; using generic demo.
        "User-Agent": "weather-bot/0.1 (demo@example.com)",
        "Accept": "application/geo+json, application/json",
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()  # type: ignore[return-value]


def nws_points(lat: float, lon: float) -> dict:
    """Fetch NWS points metadata for the given coordinate."""
    url = f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}"
    return _get_json(url)


def _choose_period(periods: List[Dict[str, Any]], when: str) -> Optional[Dict[str, Any]]:
    if not periods:
        return None
    w = (when or "today").lower()
    # Normalize names
    named = [(p.get("name", "") or "").strip() for p in periods]
    lower = [n.lower() for n in named]

    # today → first period
    if w == "today":
        return periods[0]

    # tonight → first name containing 'tonight'
    if w == "tonight":
        for i, n in enumerate(lower):
            if "tonight" in n:
                return periods[i]

    # weekend → first Saturday/Sunday mention
    if w == "weekend":
        for i, n in enumerate(lower):
            if "saturday" in n or "sunday" in n:
                return periods[i]

    # Weekday by name
    weekdays = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    if w in weekdays:
        for i, n in enumerate(lower):
            if w in n and "night" not in n:
                return periods[i]

    # tomorrow → prefer first daytime period after "today" or the first that isn't night
    if w == "tomorrow":
        # If first is Today, look past any Night period to next daytime
        if lower and (lower[0] == "today" or lower[0].startswith("today")):
            # Find the first period after index 0 that is not a night
            for i in range(1, len(periods)):
                n = lower[i]
                if "night" not in n and "tonight" not in n:
                    return periods[i]
        # Otherwise, find the first daytime period
        for i, n in enumerate(lower):
            if "night" not in n and "tonight" not in n and n not in {"today"}:
                return periods[i]

    # Fallback to first period if no match
    return periods[0]


_FORECAST_CACHE: dict[tuple[str, str], tuple[dict, float]] = {}
_ALERTS_CACHE: dict[str, tuple[List[Dict[str, Any]], float]] = {}


def _forecast_ttl() -> int:
    try:
        return int(os.getenv("FORECAST_TTL_SECONDS", "600"))
    except ValueError:
        return 600


def _alerts_ttl() -> int:
    try:
        return int(os.getenv("ALERTS_TTL_SECONDS", "120"))
    except ValueError:
        return 120


def get_forecast(loc: str, when: str = "today") -> dict:
    """Return a dict with selected forecast period info for the location.

    On success:
      {"location": loc, "period": period_name, "shortForecast": str, "temperature": int, "unit": "F"}
    On error: {"error": "..."}
    """
    coords = geocode(loc)
    if not coords:
        return {"error": f"Unknown location: {loc}"}
    lat, lon = coords
    try:
        # Cache by (normalized location, when)
        key = (str(loc).strip().title(), (when or "today").lower())
        now = time.time()
        ttl = _forecast_ttl()
        hit = _FORECAST_CACHE.get(key)
        if hit and hit[1] > now:
            return hit[0]
        pts = nws_points(lat, lon)
        forecast_url = (
            pts.get("properties", {}).get("forecast")
        )
        if not forecast_url:
            return {"error": "Forecast URL not available"}
        data = _get_json(forecast_url)
        periods = data.get("properties", {}).get("periods", []) or []
        period = _choose_period(periods, when)
        if not period:
            return {"error": "No forecast periods available"}
        name = period.get("name") or when.title()
        short = period.get("shortForecast") or "Forecast unavailable"
        temp = period.get("temperature")
        unit = period.get("temperatureUnit") or "F"
        result = {
            "location": loc,
            "period": name,
            "shortForecast": short,
            "temperature": temp,
            "unit": unit,
        }
        _FORECAST_CACHE[key] = (result, now + ttl)
        return result
    except requests.RequestException as e:
        return {"error": f"HTTP error: {e}"}
    except Exception as e:  # defensive
        return {"error": f"Unexpected error: {e}"}


def get_alerts(loc: str) -> List[Dict[str, Any]]:
    """Return a list of {event, headline} for active alerts near location.

    Returns empty list on error or if none found.
    """
    coords = geocode(loc)
    if not coords:
        return []
    lat, lon = coords
    try:
        key = str(loc).strip().title()
        now = time.time()
        ttl = _alerts_ttl()
        hit = _ALERTS_CACHE.get(key)
        if hit and hit[1] > now:
            return hit[0]
        url = f"https://api.weather.gov/alerts/active?point={lat:.4f},{lon:.4f}"
        data = _get_json(url)
        feats = data.get("features", []) or []
        out: List[Dict[str, Any]] = []
        for f in feats:
            props = f.get("properties", {})
            ev = props.get("event")
            hl = props.get("headline")
            if ev or hl:
                out.append({"event": ev, "headline": hl})
        _ALERTS_CACHE[key] = (out, now + ttl)
        return out
    except requests.RequestException:
        return []
    except Exception:
        return []
