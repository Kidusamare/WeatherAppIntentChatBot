from nlu.intent_model import IntentClassifier
from fastapi.testclient import TestClient
from api.app import app


def test_basic_training():
    clf = IntentClassifier()
    ex = clf.load_yaml("data/nlu.yml")
    clf.fit(ex)
    intent, conf = clf.predict("what's the weather in Austin, TX")
    assert conf > 0.3
    assert intent in {"get_current_weather","get_forecast","get_alerts","help","greet","fallback"}


def test_predict_smoke():
    client = TestClient(app)
    r = client.post(
        "/predict",
        json={
            "text": "forecast for tomorrow in San Marcos, TX",
            "session_id": "s1",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "intent" in data and "reply" in data
    assert isinstance(data["reply"], str)
    # Should mention the location and have some forecast text
    assert "San Marcos" in data["reply"]


def test_memory_reuse_location():
    client = TestClient(app)
    # First set location
    r1 = client.post(
        "/predict",
        json={
            "text": "forecast for tomorrow in Austin, TX",
            "session_id": "mem1",
        },
    )
    assert r1.status_code == 200
    # Now omit the location but ask for tonight; policy should reuse Austin
    r2 = client.post(
        "/predict",
        json={"text": "and tonight?", "session_id": "mem1"},
    )
    assert r2.status_code == 200
    assert "Austin" in r2.json().get("reply", "")


def test_alerts_no_error():
    client = TestClient(app)
    r = client.post(
        "/predict",
        json={
            "text": "any weather alerts for Austin, TX?",
            "session_id": "a1",
        },
    )
    assert r.status_code == 200
    reply = r.json().get("reply", "")
    # Should either list alerts or say no alerts
    assert ("Active alerts for" in reply) or ("No active alerts for" in reply)
