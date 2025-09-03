# Weather Chatbot — Minimal, Production‑Shaped

Intent-driven chatbot that fetches forecasts and alerts from the US National Weather Service (api.weather.gov), with tiny dialogue policy and in-process session memory.

## Features
- TF‑IDF + Logistic Regression intent classifier
- Regex/keyword entities: location (City, ST or demo ZIPs), datetime (today/tonight/tomorrow/weekday/weekend), units (no conversion yet)
- Session memory: remembers last location per `session_id`
- NWS client: points → forecast periods; active alerts by lat/lon
- FastAPI API: `/health`, `/predict` returns intent, confidence, entities, and a user-ready reply

## Setup
```bash
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn api.app:app --reload
```

## Example cURL
```bash
curl -s http://127.0.0.1:8000/health

curl -s -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text":"weather now in Austin, TX","session_id":"u1"}'

curl -s -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text":"forecast for tomorrow in San Marcos, TX","session_id":"u1"}'

curl -s -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text":"and tonight?","session_id":"u1"}'

curl -s -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text":"any weather alerts for Austin, TX?","session_id":"u2"}'
```

## How it works
- Demo geocoding maps a few Texas cities: Austin, San Marcos, San Antonio, Dallas; and a couple of ZIP codes.
- Forecast selection chooses a period by datetime entity (today/tonight/tomorrow/weekday/weekend) with sensible fallbacks.
- Confidence gating: if intent confidence < 0.55, returns a clarifying prompt.
- Alerts reply with a bullet list or “No active alerts for {loc}.”

## Known limitations
- Demo geocoding only (no external geocoder). If a location is unknown, the bot asks for a City, ST.
- Temperature units are what NWS provides (usually °F). The units entity is parsed but not used for conversion yet.
- In‑process memory only; swap to Redis later for multi-instance deployments.

## Docker
```bash
docker build -t weather-bot .
docker run --rm -p 8000:8000 weather-bot
```
