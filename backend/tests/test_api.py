from fastapi.testclient import TestClient

from backend.api.app import app
from backend.core import memory


def test_update_location_success(monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv("US_PLACES_CSV", "data/us_places.csv")

    sid = "test-session"
    resp = client.post(
        "/session/location",
        json={"session_id": sid, "location": "Austin, TX"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["location"] == "Austin, TX"
    cached = memory.get_mem(sid, "last_location")
    assert cached == "Austin, TX"


def test_update_location_rejects_invalid():
    client = TestClient(app)
    resp = client.post(
        "/session/location",
        json={"session_id": "sid", "location": ""},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "error"
