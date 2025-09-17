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


def test_geocode_ttl_cache(tmp_path, monkeypatch):
    import pandas as pd
    from tools import geocode as gc

    # Use a temp CSV for the local geocoder
    csv = tmp_path / "us_places.csv"
    df = pd.DataFrame({
        "USPS": ["TX"],
        "name": ["Austin city"],
        "lat": [30.2672],
        "long": [-97.7431],
    })
    df.to_csv(csv, index=False)

    monkeypatch.setenv("US_PLACES_CSV", str(csv))
    monkeypatch.setenv("GEOCODE_TTL_SECONDS", "3600")
    # Clear cache
    try:
        gc._CACHE.clear()  # type: ignore[attr-defined]
    except Exception:
        pass

    # Count loads by patching LocalGeocoder._load
    from tools.geocode import LocalGeocoder

    loads = {"n": 0}
    real_load = LocalGeocoder._load

    def counted_load(self):
        loads["n"] += 1
        return real_load(self)

    monkeypatch.setattr(LocalGeocoder, "_load", counted_load, raising=True)

    a = gc.geocode("Austin, TX")
    b = gc.geocode("Austin, TX")
    assert a == b == (30.2672, -97.7431)
    # Only one load due to cache hit
    assert loads["n"] == 1


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
