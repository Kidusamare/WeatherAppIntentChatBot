# Weather Chatbot — Minimal, Production‑Shaped

Intent-driven chatbot that fetches forecasts and alerts from the US National Weather Service (api.weather.gov), with tiny dialogue policy and in-process session memory.

## Features
- TF‑IDF + Logistic Regression intent classifier
- Regex/keyword entities: location (City, ST or demo ZIPs), datetime (today/tonight/tomorrow/weekday/weekend), units (no conversion yet)
- Session memory: remembers last location per `session_id`
- NWS client: points → forecast periods; active alerts by lat/lon
- FastAPI API: `/health`, `/predict` returns intent, confidence, entities, and a user-ready reply
- Pluggable geocoding: demo static map (offline) or US Census Geocoder

## Setup
```bash
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn api.app:app --reload
```

Important: Do not `pip install nlu` — this project’s `nlu` is a local package under `weather-bot/nlu`. The demo and CLI scripts now ensure the correct import path automatically.

For tests and coverage:
```bash
pip install -r requirements-dev.txt
pytest -q --cov=weather-bot --cov-report=term-missing
```

### Evaluation
- Add examples to `data/eval.yml` (a starter file is included).
- Run:
```bash
python scripts/eval.py --train data/nlu.yml --eval data/eval.yml
```
This prints a classification report, confusion matrix, and per‑example confidences.

### Geocoding Providers
- US Census (default, US-only, online): resolves arbitrary US addresses/cities.
- Demo (offline): a tiny static map good for quick tests; not recommended for real usage.

Select provider with an env var:
```bash
# default: census
export GEO_PROVIDER=census

# offline demo map
export GEO_PROVIDER=demo
export USER_AGENT="weather-bot/0.1 (you@example.com)"  # polite header
```

Notes:
- Entity parsing is pure and returns a normalized location string (e.g., "Austin, TX", "Baltimore").
- The geocoder resolves that string to lat/lon; results are cached in‑process.

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

# Examples that rely on geocoder behavior
curl -s -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text":"forecast in Baltimore","session_id":"u3"}'

curl -s -X POST http://127.0.0.1:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text":"weather now in Orlando, FL in celsius","session_id":"u4"}'
```

## How it works
- Demo geocoding maps a few Texas cities: Austin, San Marcos, San Antonio, Dallas; and a couple of ZIP codes.
- Forecast selection chooses a period by datetime entity (today/tonight/tomorrow/weekday/weekend) with sensible fallbacks.
- Confidence gating: if intent confidence < 0.55, returns a clarifying prompt.
- Alerts reply with a bullet list or “No active alerts for {loc}.”

Geocoding details:
- Entity parsing only extracts a location string; it does not hit the network.
- `tools/geocode.py` resolves the string to lat/lon via provider selection:
  - `GEO_PROVIDER=demo` (default): small static map, offline-friendly.
  - `GEO_PROVIDER=census`: US Census Geocoder (online). Include a polite `USER_AGENT`.
  - Results are cached in-process with an LRU cache.
  - TTL caching: geocode, forecast, and alerts responses use TTLs (env-configurable)
    - `GEOCODE_TTL_SECONDS` (default 3600s)
    - `FORECAST_TTL_SECONDS` (default 600s)
    - `ALERTS_TTL_SECONDS` (default 120s)
  - Datetime parsing enhanced: supports phrases like “this afternoon/evening/morning”, “later today”, and “tomorrow morning/night”.

## Known limitations
- Demo geocoding (offline) or US Census (online). If a location is unknown, the bot asks for a City, ST.
- Temperature units are what NWS provides (usually °F). The units entity is parsed but not used for conversion yet.
- In‑process memory only; swap to Redis later for multi-instance deployments.

Testing notes:
- Tests are offline-first and monkeypatch network calls (NWS, geocoder parsing).
- Run with: `pytest -q weather-bot/tests`

## Docker
```bash
docker build -t weather-bot .
docker run --rm -p 8000:8000 weather-bot
```

## Demo Script
Interactive terminal chat that uses the same NLU + policy as the API:
```bash
python scripts/chat_demo.py
```
Tip: You can also run from the repo root via `python weather-bot/scripts/chat_demo.py`. The scripts add the project path so local `nlu` is used.

Inspector and spaCy parser test:
```bash
# Inspect how a prompt is parsed and geocoded (no reply policy)
python scripts/inspect_prompt.py

# Test only the spaCy location parser interactively or with args
python scripts/test_spacy_location.py
python scripts/test_spacy_location.py "tomorrow in silver spring maryland" "forecast for new york"
```

## Health Metadata
`/health` also returns provider and TTL details to aid debugging, for example:
```json
{
  "status": "ok",
  "geo_provider": "demo",
  "ttl": {"geocode": 3600, "forecast": 600, "alerts": 120}
}
```

## Next Steps
- Metrics: log each `/predict` call to SQLite (timestamp, intent, confidence, latency, entities, reply snippet).
- Cache polish: add an optional TTL around geocoding cache; consider simple forecast caching by location+period.
- Tests: add coverage reporting (`pytest-cov`) and a non-empty alerts test case.
- UX: tiny web chat page or screenshots; curated demo script (6–8 turns) showing memory and units.
- Config: minimal logging with request IDs and provider selection echo in `/health`.
### Environment (.env)
- A `.env` file with sensible defaults is included. The app and chat demo load it automatically.
- Replace `USER_AGENT` with your contact info to comply with NWS/Census policies.
- Common variables:
  - `INTENT_BACKEND` (tfidf|bert)
  - `GEO_PROVIDER` (demo|census)
  - `USER_AGENT` (e.g., `weather-bot/0.1 (you@example.com)`)
  - `GEOCODE_TTL_SECONDS`, `FORECAST_TTL_SECONDS`, `ALERTS_TTL_SECONDS`
  - `WEATHER_BOT_DB_PATH`
  - `HF_MODEL_NAME`, `HF_DEVICE`, `CENSUS_GEOCODER_URL`, `CENSUS_BENCHMARK`
  - `GEOCODE_DEBUG=1` (optional) to print provider, cache hits, and results
