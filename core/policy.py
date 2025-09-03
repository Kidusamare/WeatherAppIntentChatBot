"""Simple dialogue policy that uses NLU outputs to craft user replies.

Handles memory of last location per session and calls NWS client for
forecasts and alerts.
"""

from __future__ import annotations

from typing import Dict, Any

from core.memory import get_mem, set_mem
from tools.weather_nws import get_forecast, get_alerts


def _need_location_reply() -> str:
    return "What city and state? (e.g., Austin, TX)"


def respond(intent: str, conf: float, entities: Dict[str, Any], session_id: str) -> str:
    # Confidence gating
    if conf < 0.55:
        return "Do you want current weather, a forecast, or alerts?"

    intent = intent or "fallback"

    # Greeting/help
    if intent == "greet":
        return (
            "Hi! Ask me about current weather, a forecast, or alerts. "
            "Example: 'forecast for tomorrow in Austin, TX'"
        )
    if intent == "help":
        return (
            "You can ask for current weather, forecasts (today, tonight, tomorrow, weekday), "
            "or alerts. Include a city like 'San Marcos, TX'."
        )

    # Common location resolution for weather/alerts
    loc = entities.get("location") if entities else None
    if loc:
        set_mem(session_id, "last_location", loc)
    else:
        loc = get_mem(session_id, "last_location")

    if intent in {"get_current_weather", "get_forecast"}:
        if not loc:
            return _need_location_reply()
        when = (entities.get("datetime") if entities else None) or "today"
        # Treat current weather as 'today' first period
        if intent == "get_current_weather":
            when = "today"
        fc = get_forecast(loc, when)
        if "error" in fc:
            return f"Sorry, I couldn't fetch the forecast for {loc}. {fc['error']}"
        period = fc.get("period") or when.title()
        short = fc.get("shortForecast") or "Forecast unavailable"
        temp = fc.get("temperature")
        unit = fc.get("unit") or "F"
        temp_part = f" Around {temp}°{unit}." if temp is not None else ""
        return f"{period} in {loc}: {short}.{temp_part}".strip()

    if intent == "get_alerts":
        if not loc:
            return _need_location_reply()
        alerts = get_alerts(loc)
        if not alerts:
            return f"No active alerts for {loc}."
        lines = [f"- {a.get('event') or 'Alert'}: {a.get('headline') or ''}" for a in alerts]
        return f"Active alerts for {loc}:\n" + "\n".join(lines)

    # Fallback/help
    return (
        "I can help with current weather, forecasts (today/tonight/tomorrow/weekday), "
        "and weather alerts. Try: 'weather now in Austin, TX'"
    )

