"""Minimal National Weather Service (NWS) client utilities.

Geocoding is delegated to ``tools.geocode.geocode`` (demo or Census provider).
Fetches point metadata, forecast periods, and active alerts with basic error
handling and lightweight caching (forecast/alerts TTLs).
"""

from __future__ import annotations

from typing import Optional, Tuple, List, Dict, Any
import os
import time
import sys
import requests

from backend.tools.geocode import geocode


"""Geocoding now delegated to tools.geocode.geocode(provider=demo|census)."""


def _get_json(url: str) -> dict:
    ua = os.getenv("USER_AGENT", "weather-bot/0.1 (demo@example.com)")
    headers = {
        # NWS requires a User-Agent with contact per policy
        "User-Agent": ua,
        "Accept": "application/geo+json, application/json",
    }
    if os.getenv("WEATHER_BOT_DEBUG") in {"1", "true", "yes", "on"}:
        print(f"[nws] GET {url}", file=sys.stderr)
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

    # Today morning/afternoon/evening variants
    if w in {"today_morning", "today_afternoon", "today_evening"}:
        targets = {
            "today_morning": ["morning"],
            "today_afternoon": ["afternoon"],
            "today_evening": ["evening", "tonight"],
        }[w]
        for i, n in enumerate(lower[:4]):  # typically within first few periods
            if any(t in n for t in targets):
                return periods[i]
        # fallback to today first period or tonight
        if w == "today_evening":
            for i, n in enumerate(lower):
                if "tonight" in n:
                    return periods[i]
        return periods[0]

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

    # Tomorrow morning/night specificity
    if w in {"tomorrow_morning", "tomorrow_night"}:
        # Start after any Today periods; pick first suitable for morning (non-night) or night
        start = 1 if lower and (lower[0] == "today" or lower[0].startswith("today")) else 0
        # Find first non-night (morning/day)
        if w == "tomorrow_morning":
            for i in range(start, len(periods)):
                n = lower[i]
                if ("night" not in n and "tonight" not in n) and n not in {"today"}:
                    return periods[i]
        else:  # tomorrow_night
            for i in range(start, len(periods)):
                n = lower[i]
                if "night" in n or "evening" in n:
                    return periods[i]

    # Fallback to first period if no match
    return periods[0]


_FORECAST_CACHE: dict[tuple[str, str], tuple[dict, float]] = {}
_ALERTS_CACHE: dict[str, tuple[List[Dict[str, Any]], float]] = {}
_FORECAST_CACHE_MAX = max(int(os.getenv("FORECAST_CACHE_MAX", "5000")), 1)
_ALERTS_CACHE_MAX = max(int(os.getenv("ALERTS_CACHE_MAX", "5000")), 1)


def _purge_forecast_cache(now: float) -> None:
    expired = [key for key, (_, expiry) in _FORECAST_CACHE.items() if expiry <= now]
    for key in expired:
        _FORECAST_CACHE.pop(key, None)
    if len(_FORECAST_CACHE) <= _FORECAST_CACHE_MAX:
        return
    victims = sorted(_FORECAST_CACHE.items(), key=lambda item: item[1][1])
    for key, _ in victims:
        if len(_FORECAST_CACHE) <= _FORECAST_CACHE_MAX:
            break
        _FORECAST_CACHE.pop(key, None)


def _purge_alert_cache(now: float) -> None:
    expired = [key for key, (_, expiry) in _ALERTS_CACHE.items() if expiry <= now]
    for key in expired:
        _ALERTS_CACHE.pop(key, None)
    if len(_ALERTS_CACHE) <= _ALERTS_CACHE_MAX:
        return
    victims = sorted(_ALERTS_CACHE.items(), key=lambda item: item[1][1])
    for key, _ in victims:
        if len(_ALERTS_CACHE) <= _ALERTS_CACHE_MAX:
            break
        _ALERTS_CACHE.pop(key, None)


def _forecast_ttl() -> int:
    try:
        return int(os.getenv("FORECAST_TTL_SECONDS", "1800"))
    except ValueError:
        return 600


def _alerts_ttl() -> int:
    try:
        return int(os.getenv("ALERTS_TTL_SECONDS", "120"))
    except ValueError:
        return 120


def _resolve_unit(unit: str | None) -> Tuple[str, str]:
    code = (unit or "imperial").strip().lower()
    if code in {"metric", "c", "celsius"}:
        return "metric", "C"
    return "imperial", "F"


def _cast_temperature(temp: Optional[int], source_unit: str, desired_unit: str) -> Optional[int]:
    if temp is None:
        return None
    source = source_unit.upper()
    desired = desired_unit.upper()
    if source == desired:
        return temp
    if source == "F" and desired == "C":
        return round((temp - 32) * 5 / 9)
    if source == "C" and desired == "F":
        return round((temp * 9 / 5) + 32)
    return temp


def _forecast_cache_key(loc: str, when: str, unit: str, signature: str | None = None) -> Tuple[str, str, str, str | None]:
    norm_loc = str(loc).strip().title()
    when_norm = (when or "today").lower()
    unit_key = unit.upper()
    sig = (signature or "").strip() or None
    return norm_loc, when_norm, unit_key, sig


def get_forecast(loc: str, when: str = "today", units: str = "imperial") -> dict:
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
        _, unit_symbol = _resolve_unit(units)
        norm_loc = str(loc).strip().title()
        when_norm = (when or "today").lower()
        now = time.time()
        ttl = _forecast_ttl()
        _purge_forecast_cache(now)
        candidate_value: Optional[dict] = None
        for cache_key, (payload, expiry) in list(_FORECAST_CACHE.items()):
            if expiry <= now:
                continue
            key_loc, key_when, key_unit, _ = cache_key
            if key_loc == norm_loc and key_when == when_norm and key_unit == unit_symbol:
                candidate_value = payload
                break
        if candidate_value is not None:
            return candidate_value
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
        source_unit = (period.get("temperatureUnit") or "F").upper()
        converted_temp = _cast_temperature(temp, source_unit, unit_symbol)
        # Update cache key with resolved startTime signature now that we have it.
        key_signature = None
        start_time = period.get("startTime")
        if isinstance(start_time, str) and start_time:
            key_signature = start_time[:16]  # include date + hour for uniqueness
        key = _forecast_cache_key(loc, when, unit_symbol, key_signature)
        # Remove stale entries for same loc/when/unit before storing refreshed data.
        for existing_key in list(_FORECAST_CACHE.keys()):
            if existing_key[:3] == (norm_loc, when_norm, unit_symbol):
                _FORECAST_CACHE.pop(existing_key, None)
        result = {
            "location": loc,
            "period": name,
            "shortForecast": short,
            "temperature": converted_temp,
            "unit": unit_symbol,
            "sourceUnit": source_unit,
            "startTime": period.get("startTime"),
            "endTime": period.get("endTime"),
            "cacheKey": f"weather:{str(loc).strip().title()}:{(key_signature or (when or 'today').lower())}:{unit_symbol}",
        }
        _FORECAST_CACHE[key] = (result, now + ttl)
        _purge_forecast_cache(now)
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
        _purge_alert_cache(now)
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
        _purge_alert_cache(now)
        return out
    except requests.RequestException:
        return []
    except Exception:
        return []
