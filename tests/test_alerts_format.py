from fastapi.testclient import TestClient


def test_alerts_format_nonempty(monkeypatch):
    from api.app import app
    from core import policy

    def fake_alerts(loc: str):
        return [
            {"event": "Severe Thunderstorm Warning", "headline": "Storm approaching downtown"},
            {"event": "Flood Advisory", "headline": "Low-lying areas prone to flooding"},
        ]

    monkeypatch.setattr(policy, "get_alerts", fake_alerts)

    client = TestClient(app)
    r = client.post(
        "/predict",
        json={"text": "any weather alerts for Austin, TX?", "session_id": "al1"},
    )
    assert r.status_code == 200
    reply = r.json()["reply"]
    assert "Active alerts for Austin, TX:" in reply
    # Expect bullet list formatting
    assert "- Severe Thunderstorm Warning:" in reply
