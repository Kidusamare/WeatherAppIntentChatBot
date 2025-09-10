import os
import sqlite3
from fastapi.testclient import TestClient


def test_metrics_logging(tmp_path, monkeypatch):
    # Use a temp DB path
    db_path = tmp_path / "metrics.sqlite"
    monkeypatch.setenv("WEATHER_BOT_DB_PATH", str(db_path))

    # Import after env set so app uses it
    from api.app import app
    from core import policy

    # Avoid network: stub forecast
    def fake_forecast(loc: str, when: str = "today"):
        return {
            "location": loc,
            "period": when.title(),
            "shortForecast": "Sunny",
            "temperature": 72,
            "unit": "F",
        }

    monkeypatch.setattr(policy, "get_forecast", fake_forecast)

    client = TestClient(app)
    r = client.post(
        "/predict",
        json={"text": "weather now in Austin, TX", "session_id": "m1"},
    )
    assert r.status_code == 200

    # Verify one row logged
    with sqlite3.connect(str(db_path)) as conn:
        cur = conn.execute("SELECT count(*) FROM interactions")
        (count,) = cur.fetchone()
        assert count == 1


def test_geocode_ttl_cache(monkeypatch):
    import requests
    from tools import geocode as gc

    monkeypatch.setenv("GEO_PROVIDER", "census")
    monkeypatch.setenv("GEOCODE_TTL_SECONDS", "3600")
    # Clear any previous cache state
    try:
        gc._CACHE.clear()  # type: ignore[attr-defined]
    except Exception:
        pass

    calls = {"n": 0}

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"result": {"addressMatches": [{"coordinates": {"x": -97.7431, "y": 30.2672}}]}}

    def fake_get(url, params=None, headers=None, timeout=None):
        calls["n"] += 1
        return FakeResp()

    monkeypatch.setattr(requests, "get", fake_get)

    a = gc.geocode("Austin, TX")
    b = gc.geocode("Austin, TX")
    assert a == b == (30.2672, -97.7431)
    assert calls["n"] == 1  # second call served from cache


def test_forecast_cache(monkeypatch):
    from tools import weather_nws as nws

    # Stub geocode so we don't depend on providers
    monkeypatch.setattr(nws, "geocode", lambda loc: (30.2672, -97.7431))

    # Provide a fake points and forecast response; count calls
    calls = {"points": 0, "forecast": 0}

    def fake_points(lat, lon):
        calls["points"] += 1
        return {"properties": {"forecast": "https://api.weather.gov/gridpoints/FOO/1,1/forecast"}}

    def fake_get_json(url):
        calls["forecast"] += 1
        return {
            "properties": {
                "periods": [
                    {"name": "Today", "shortForecast": "Sunny", "temperature": 70, "temperatureUnit": "F"},
                    {"name": "Tonight", "shortForecast": "Clear", "temperature": 55, "temperatureUnit": "F"},
                ]
            }
        }

    monkeypatch.setattr(nws, "nws_points", fake_points)
    monkeypatch.setattr(nws, "_get_json", fake_get_json)

    r1 = nws.get_forecast("Austin, TX", "today")
    r2 = nws.get_forecast("Austin, TX", "today")
    assert r1 == r2
    # points+forecast should only be called once for the same (loc, when)
    assert calls["points"] == 1
    assert calls["forecast"] == 1
