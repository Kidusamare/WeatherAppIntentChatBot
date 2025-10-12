"""Dialogue policy that turns intents + entities into user-facing replies.

Capabilities
- Greeting/help replies with lightweight on-rails guidance.
- Current weather and forecast replies via NWS tools with TTL caching upstream.
- Alerts listing with friendly nudge; bullet formatting preserved for tests.
- Session memory of last location (canonical City, ST if available).
- Deterministic reply variants to keep tone lively but predictable per session.
"""

from __future__ import annotations

from typing import Dict, Any, List
import re
import hashlib

from backend.core.memory import append_prompt_snapshot, get_mem, set_mem
from backend.tools.weather_nws import get_forecast, get_alerts
from backend.tools.geocode import canonicalize_location


def _need_location_reply() -> str:
    return "What city and state? (e.g., Austin, TX)"


def _is_zip(loc: str) -> bool:
    return bool(loc and loc.isdigit() and len(loc) == 5)


def _is_city_state(loc: str) -> bool:
    # Accept letters, spaces and dots/hyphens in city names, and a 2-letter state
    return bool(re.match(r"^[A-Za-z][A-Za-z .-]*,\s*[A-Z]{2}$", loc or ""))


def respond(intent: str, conf: float, entities: Dict[str, Any], session_id: str) -> str:
    # Confidence gating with light contextual override
    # If confidence is low but we have a remembered location and a datetime cue,
    # we proceed for weather-related intents to enable simple follow-ups like
    # "and tonight?".
    low_conf = conf < 0.55

    intent = intent or "fallback"

    # Work on a copy so caller retains raw extraction
    entities = dict(entities or {})

    explicit_when_requested = bool(entities.get("datetime"))

    # Track resolved context so we can cache it for future turns
    resolved_loc = entities.get("location")
    resolved_when = entities.get("datetime")
    resolved_units = entities.get("units")

    # Warm-start missing pieces from prior turn memory if available
    last_entities = get_mem(session_id, "last_entities") or {}
    if not resolved_loc and last_entities.get("location"):
        resolved_loc = last_entities.get("location")
        entities.setdefault("location", resolved_loc)
    if not resolved_when and last_entities.get("datetime"):
        resolved_when = last_entities.get("datetime")
        entities.setdefault("datetime", resolved_when)
    if not resolved_units and last_entities.get("units"):
        resolved_units = last_entities.get("units")
        entities.setdefault("units", resolved_units)

    # Check for pending intent context (e.g., user provided location after a prompt)
    pending_intent = get_mem(session_id, "pending_intent")
    pending_when = get_mem(session_id, "pending_when")

    # Small deterministic variant picker to keep replies lively but stable per session
    def _pick(options: List[str], key: str = "") -> str:
        if not options:
            return ""
        h = hashlib.md5(f"{session_id}|{key}".encode()).hexdigest()
        idx = int(h, 16) % len(options)
        return options[idx]

    def _capture(
        reply_text: str,
        *,
        used_intent: str | None = None,
        remember: bool = True,
    ) -> str:
        payload = {
            "location": resolved_loc,
            "datetime": resolved_when,
            "units": resolved_units,
        }
        append_prompt_snapshot(
            session_id,
            intent=used_intent or intent,
            confidence=conf,
            entities=payload,
            extras={"reply": reply_text},
        )
        if remember:
            set_mem(session_id, "last_entities", payload)
            if payload.get("location"):
                set_mem(session_id, "last_location", payload["location"])
        return reply_text

    def _time_label(when_value: str | None, period_name: str | None, explicit: bool) -> str:
        if not explicit:
            return "Right now"
        w = (when_value or "").lower()
        mapping = {
            "today": "Today",
            "today_morning": "This morning",
            "today_afternoon": "This afternoon",
            "today_evening": "This evening",
            "tonight": "Tonight",
            "tomorrow": "Tomorrow",
            "tomorrow_morning": "Tomorrow morning",
            "tomorrow_night": "Tomorrow night",
            "weekend": "This weekend",
        }
        weekdays = {
            "monday": "Monday",
            "tuesday": "Tuesday",
            "wednesday": "Wednesday",
            "thursday": "Thursday",
            "friday": "Friday",
            "saturday": "Saturday",
            "sunday": "Sunday",
        }
        if w in mapping:
            return mapping[w]
        if w in weekdays:
            return weekdays[w]
        if when_value:
            return when_value.replace("_", " ").strip().title()
        if period_name:
            return period_name.strip()
        return "Today"

    def _format_forecast_reply(
        loc_text: str,
        when_value: str,
        period_name: str,
        description: str,
        temp_detail: str,
        explicit: bool,
    ) -> str:
        label = _time_label(when_value, period_name, explicit)
        summary = (description or "Forecast unavailable").strip()
        if summary:
            label_norm = label.lower().rstrip(":")
            summary_norm = summary.lower()
            if label_norm and summary_norm.startswith(label_norm):
                trimmed = summary[len(label) :].lstrip(" :,-") or summary
                if trimmed != summary:
                    summary = trimmed
            if summary and summary[0].islower():
                summary = summary[0].upper() + summary[1:]
        if summary and summary[-1] not in ".!?":
            summary = summary + "."
        detail = temp_detail.strip()
        if detail:
            if detail[-1] not in ".!?":
                detail = detail + "."
            summary = f"{summary} {detail}".strip()
        return f"{label} in {loc_text}: {summary}".strip()

    # Greeting/help
    if intent == "greet":
        variants = [
            "Hi! Ask me about current weather, a forecast, or alerts. Example: 'forecast for tomorrow in Austin, TX'",
            "Hello! I can check weather now, forecasts, and alerts. Try: 'weather now in Austin, TX'",
            "Hey there! I can give you current conditions, a forecast, or alerts. For example: 'any alerts for Dallas, TX?'",
        ]
        reply = _pick(variants, key="greet")
        return _capture(reply, remember=False)
    if intent == "help":
        options = [
            "You can ask for current weather, forecasts (today/tonight/tomorrow/weekday), or alerts. Include a city like 'San Marcos, TX'.",
            "Try things like: 'weather now in Austin, TX', 'and tonight?', or 'any weather alerts for Dallas, TX?'",
        ]
        reply = _pick(options, key="help")
        return _capture(reply, remember=False)

    # Common location resolution for weather/alerts
    loc = entities.get("location") if entities else None
    if loc:
        can_loc = canonicalize_location(loc) or (loc.strip().title() if isinstance(loc, str) else loc)
        # Store canonical location if it includes a state, otherwise keep raw
        if _is_city_state(can_loc):
            set_mem(session_id, "last_location", can_loc)
        loc = can_loc
        resolved_loc = loc
    else:
        loc = get_mem(session_id, "last_location")
        resolved_loc = loc

    if intent in {"get_current_weather", "get_forecast"}:
        if low_conf and not (loc and entities and entities.get("datetime")):
            # Remember pending ask so a follow-up location can complete the request
            set_mem(session_id, "pending_intent", intent)
            when_hint = (entities.get("datetime") if entities else None) or "today"
            set_mem(session_id, "pending_when", when_hint)
            resolved_when = resolved_when or when_hint
            reply = "Do you want current weather, a forecast, or alerts?"
            return _capture(reply, remember=False)
        if not loc:
            # Remember what we're after and ask for City, ST
            set_mem(session_id, "pending_intent", intent)
            when_hint = (entities.get("datetime") if entities else None) or "today"
            set_mem(session_id, "pending_when", when_hint)
            resolved_when = resolved_when or when_hint
            reply = _need_location_reply()
            return _capture(reply, remember=False)
        when = (entities.get("datetime") if entities else None) or "today"
        # Treat current weather as 'today' first period
        if intent == "get_current_weather":
            when = "today"
        resolved_when = when
        when_key = (when or "").lower()
        explicit_when = explicit_when_requested or when_key not in {"today"}
        requested_units = (entities.get("units") if entities else None) or "imperial"
        fc = get_forecast(loc, when, requested_units)
        if "error" in fc:
            reply = f"Sorry, I couldn't fetch the forecast for {loc}. {fc['error']}"
            return _capture(reply)
        period = fc.get("period") or when.title()
        short = fc.get("shortForecast") or "Forecast unavailable"
        temp = fc.get("temperature")
        display_unit = (fc.get("unit") or "F").upper()
        temp_part = f"Around {temp} degrees {display_unit}" if temp is not None else ""
        base = _format_forecast_reply(loc, when, period, short, temp_part, explicit_when)
        # Add a gentle, deterministic suggestion variant
        suffix = _pick([
            "",
            " You can ask for alerts, too.",
            " Want the weekend outlook as well?",
            " Need it in Celsius or Fahrenheit?",
        ], key="wx_suffix")
        # Clear pending upon success
        set_mem(session_id, "pending_intent", None)
        set_mem(session_id, "pending_when", None)
        resolved_loc = loc
        resolved_when = when
        resolved_units = requested_units
        reply = (base + suffix).strip()
        return _capture(reply)

    if intent == "get_alerts":
        if low_conf and not loc:
            reply = "Do you want current weather, a forecast, or alerts?"
            return _capture(reply, remember=False)
        if not loc:
            reply = _need_location_reply()
            return _capture(reply, remember=False)
        alerts = get_alerts(loc)
        if not alerts:
            resolved_loc = loc
            reply = f"No active alerts for {loc}."
            return _capture(reply)
        lines = [f"- {a.get('event') or 'Alert'}: {a.get('headline') or ''}" for a in alerts]
        # Keep the header stable for tests, add a friendly nudge afterwards
        body = f"Active alerts for {loc}:\n" + "\n".join(lines)
        tail = _pick(["", "\nStay safe. Ask for a forecast if you need details."], key="alerts_tail")
        # Clear pending upon success
        set_mem(session_id, "pending_intent", None)
        set_mem(session_id, "pending_when", None)
        resolved_loc = loc
        reply = body + tail
        return _capture(reply)

    # If the user supplied a location but classifier didn't catch intent,
    # use any pending intent from the previous turn
    if pending_intent and loc:
        # Re-enter with the pending intent and hint
        if pending_intent == "get_forecast" or pending_intent == "get_current_weather":
            when = pending_when or ((entities.get("datetime") if entities else None) or "today")
            if pending_intent == "get_current_weather":
                when = "today"
            when_key = (when or "").lower()
            explicit_when = explicit_when_requested or bool(pending_when) or when_key not in {"today"}
            requested_units = (entities.get("units") if entities else None) or "imperial"
            fc = get_forecast(loc, when, requested_units)
            if "error" in fc:
                resolved_loc = loc
                resolved_when = when
                reply = f"Sorry, I couldn't fetch the forecast for {loc}. {fc['error']}"
                return _capture(reply, used_intent=pending_intent)
            period = fc.get("period") or str(when).title()
            short = fc.get("shortForecast") or "Forecast unavailable"
            temp = fc.get("temperature")
            display_unit = (fc.get("unit") or "F").upper()
            temp_part = f"Around {temp} degrees {display_unit}" if temp is not None else ""
            base = _format_forecast_reply(loc, when, period, short, temp_part, explicit_when)
            suffix = _pick([
                "",
                " You can ask for alerts, too.",
                " Want the weekend outlook as well?",
                " Need it in Celsius or Fahrenheit?",
            ], key="wx_suffix")
            set_mem(session_id, "pending_intent", None)
            set_mem(session_id, "pending_when", None)
            resolved_loc = loc
            resolved_when = when
            resolved_units = requested_units
            reply = (base + suffix).strip()
            return _capture(reply, used_intent=pending_intent)
        if pending_intent == "get_alerts":
            alerts = get_alerts(loc)
            if not alerts:
                set_mem(session_id, "pending_intent", None)
                set_mem(session_id, "pending_when", None)
                resolved_loc = loc
                reply = f"No active alerts for {loc}."
                return _capture(reply, used_intent=pending_intent)
            lines = [f"- {a.get('event') or 'Alert'}: {a.get('headline') or ''}" for a in alerts]
            body = f"Active alerts for {loc}:\n" + "\n".join(lines)
            tail = _pick(["", "\nStay safe. Ask for a forecast if you need details."], key="alerts_tail")
            set_mem(session_id, "pending_intent", None)
            set_mem(session_id, "pending_when", None)
            resolved_loc = loc
            reply = body + tail
            return _capture(reply, used_intent=pending_intent)

    # Fallback/help
    reply = _pick([
        "I can help with current weather, forecasts (today/tonight/tomorrow/weekday), and weather alerts. Try: 'weather now in Austin, TX'",
        "Ask me for current conditions, a forecast (like 'tomorrow in Dallas, TX'), or alerts.",
    ], key="fallback")
    return _capture(reply, remember=False)
