import json
from tools.geocode import geocode, DEMO_GEOCODES


def test_demo_geocode(monkeypatch):
    monkeypatch.setenv("GEO_PROVIDER", "demo")
    # Use a known demo city
    latlon = geocode("Austin")
    assert latlon == DEMO_GEOCODES["Austin, TX"]


def test_census_geocode_parsing(monkeypatch):
    import requests

    class FakeResp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, params=None, headers=None, timeout=None):
        # Return a minimal valid payload with an address match
        payload = {
            "result": {
                "addressMatches": [
                    {"coordinates": {"x": -97.7431, "y": 30.2672}}
                ]
            }
        }
        return FakeResp(payload)

    monkeypatch.setenv("GEO_PROVIDER", "census")
    monkeypatch.setattr(requests, "get", fake_get)

    latlon = geocode("Austin, TX")
    assert latlon == (30.2672, -97.7431)

