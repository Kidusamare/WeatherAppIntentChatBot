# Weather Chatbot — Minimal, Production‑Shaped

Intent-driven chatbot that fetches forecasts and alerts from the US National Weather Service (api.weather.gov), with tiny dialogue policy and in-process session memory.

## Features
- TF‑IDF + Logistic Regression intent classifier
- Regex/keyword entities: location (City, ST), datetime (today/tonight/tomorrow/weekday/weekend), units (no conversion yet)
- Session memory: remembers last location per `session_id`
- NWS client: points → forecast periods; active alerts by lat/lon
- FastAPI API: `/health`, `/predict` returns intent, confidence, entities, and a user-ready reply
- Local CSV geocoder with fuzzy matching for US places
- Hardened in-memory session cache with TTL and caps (production-safe)
- Optional `/session/location` endpoint to seed geolocation from clients

## Setup
```bash
python -m venv .venv && source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn api.app:app --reload
```

Important: Do not `pip install nlu` — this project’s `nlu` is a local package under `weather-bot/nlu`. The demo and CLI scripts now ensure the correct import path automatically.

Recommended workflow:
```bash
make install-dev  # installs pinned runtime + dev dependencies
make test         # executes pytest suite
make eval         # prints intent accuracy summary
```

### Evaluation-only run
- Add examples to `data/eval.yml` (a starter file is included).
- Run `python scripts/eval.py --train data/nlu.yml --eval data/eval.yml` for a one-off report.

Notes:
- Entity parsing is pure and returns a normalized location string (e.g., "Austin, TX", "Baltimore").
- The geocoder resolves that string to lat/lon; results are cached in‑process.

## Example cURL
```bash
curl -s http://127.0.0.1:8000/health

curl -s -X POST http://127.0.0.1:8000/session/location \
  -H "Content-Type: application/json" \
  -d '{"session_id":"u1","location":"Austin, TX"}'

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

## Production deployment
- Build the hardened image with `make docker-build` (multi-stage base, non-root, gunicorn worker with uvicorn).
- Run locally with `make docker-run` or deploy the image to your orchestrator. The container exposes port `8000` and includes an OS healthcheck that hits `/health`.
- Provide environment overrides for cache/session bounds as traffic scales (`SESSION_TTL_SECONDS`, `SESSION_MAX_ENTRIES`, `GEOCODE_CACHE_MAX`, `FORECAST_CACHE_MAX`, `ALERTS_CACHE_MAX`).
- When a frontend captures browser/device location, call `POST /session/location` to seed the cache, then use `/predict` for natural-language follow-ups.

## How it works
- Local geocoding loads `data/us_places.csv` (override with `US_PLACES_CSV`) and uses substring/fuzzy matching to find City, ST entries.
- Forecast selection chooses a period by datetime entity (today/tonight/tomorrow/weekday/weekend) with sensible fallbacks.
- Confidence gating: if intent confidence < 0.55, returns a clarifying prompt.
- Alerts reply with a bullet list or “No active alerts for {loc}.”

Geocoding details:
- Entity parsing only extracts a location string; it does not hit the network.
- `tools/geocode.py` resolves the string to lat/lon using the CSV-backed local geocoder.
- Results are cached in-process with a TTL cache.
- TTL caching: geocode, forecast, and alerts responses use TTLs (env-configurable)
  - `GEOCODE_TTL_SECONDS` (default 3600s)
  - `FORECAST_TTL_SECONDS` (default 600s)
  - `ALERTS_TTL_SECONDS` (default 120s)
- Datetime parsing enhanced: supports phrases like “this afternoon/evening/morning”, “later today”, and “tomorrow morning/night”.

## Known limitations
- Local geocoding relies on the CSV catalog (US-only). If a location is unknown, the bot asks for a City, ST.
- Temperature units are what NWS provides (usually °F). The units entity is parsed but not used for conversion yet.
- In‑process memory only; swap to Redis later for multi-instance deployments.

Testing notes:
- Tests are offline-first and monkeypatch network calls (NWS, geocoder parsing).
- Run with `make test` (pytest -q) or `make eval` for accuracy snapshot.

## Docker
The Makefile wraps the recommended commands:
```bash
make docker-build
make docker-run
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
  "geo_provider": "local",
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
- Replace `USER_AGENT` with your contact info to comply with NWS policies.
- Common variables:
  - `INTENT_BACKEND` (tfidf|bert)
  - `INTENT_CONF_TEMPERATURE` (default `0.75`) — <1 sharpens intent confidence; >1 smooths it
  - When using the `bert` backend be sure `torch` and `transformers` are installed (included in `requirements*.txt`)
  - `USER_AGENT` (e.g., `weather-bot/0.1 (you@example.com)`)
  - `GEOCODE_TTL_SECONDS`, `FORECAST_TTL_SECONDS`, `ALERTS_TTL_SECONDS`
  - `GEOCODE_CACHE_MAX`, `FORECAST_CACHE_MAX`, `ALERTS_CACHE_MAX` (cap cache entries; defaults 1000/5000/5000)
  - `WEATHER_BOT_DB_PATH`
  - `HF_MODEL_NAME`, `HF_DEVICE`
  - `SESSION_TTL_SECONDS` (default 1800) and `SESSION_MAX_ENTRIES` (default 5000) for in-process memory bounds
  - `GEOCODE_DEBUG=1` (optional) to print provider, cache hits, and results
