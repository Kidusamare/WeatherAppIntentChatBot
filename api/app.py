import time
import os
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv()
except Exception:
    pass
from fastapi import FastAPI
from pydantic import BaseModel
from nlu.intent_model import IntentClassifier
from nlu.entities import parse_location, parse_datetime, parse_units
from core.policy import respond
from core.memory import set_mem
from metrics.log import log_interaction
from nlu.loc_extractor import _get_nlp as _loc_spacy
from tools import geocode as gc
from tools import weather_nws as nws
from functools import lru_cache

app = FastAPI(title="Weather Chatbot")

@app.on_event("startup")
async def startup_event():
    print("🔹 Starting Weather Chatbot API...")
    # Preload NLP and geocoding models
    _ = _loc_spacy()
    _ = gc._provider_name()
    print("✅ Startup complete.")

@app.on_event("shutdown")
async def shutdown_event():
    print("🔻 Shutting down Weather Chatbot API...")


clf = IntentClassifier()

@lru_cache(maxsize=1)
def get_intent_classifier():
    clf = IntentClassifier()
    examples = clf.load_yaml("data/nlu.yml")
    clf.fit(examples)
    return clf

clf = get_intent_classifier()

examples = clf.load_yaml("data/nlu.yml")
clf.fit(examples)


class Query(BaseModel):
    text: str
    session_id: str


@app.get("/health")
def health():
    # Expose provider and TTLs for quick diagnostics
    return {
        "status": "ok",
        "geo_provider": gc._provider_name(),
        "location_backend": (os.getenv("LOCATION_BACKEND") or "spacy"),
        "spacy_loaded": bool(_loc_spacy()),
        "ttl": {
            "geocode": gc._ttl_seconds(),
            "forecast": nws._forecast_ttl(),
            "alerts": nws._alerts_ttl(),
        },
    }


@app.post("/predict")
def predict(q: Query):
    t0 = time.time()
    try:
        intent, conf = clf.predict(q.text)
        entities = {
            "location": parse_location(q.text),
            "datetime": parse_datetime(q.text),
            "units": parse_units(q.text),
        }
        reply = respond(intent, conf, entities, q.session_id)
    except Exception as e:
        reply = "Sorry, something went wrong while processing your request."
        intent, conf, entities = "error", 0.0, {}
        print("❌ Prediction error:", e)

    latency_ms = int((time.time() - t0) * 1000)
    try:
        log_interaction(
            session_id=q.session_id,
            text=q.text,
            intent=intent,
            confidence=conf,
            latency_ms=latency_ms,
            entities=entities,
            reply=reply,
        )
    except Exception:
        pass

    return {
        "intent": intent,
        "confidence": conf,
        "entities": entities,
        "reply": reply,
        "latency_ms": latency_ms,
    }

class LocationUpdate(BaseModel):
    session_id: str
    location: str


@app.post("/session/location")
def update_location(update: LocationUpdate):
    loc = (update.location or "").strip()
    if not loc:
        return {"status": "error", "message": "location must be provided"}
    if len(loc) > 120:
        return {"status": "error", "message": "location is too long"}

    canonical = gc.canonicalize_location(loc)
    if not canonical:
        return {"status": "error", "message": "unable to interpret location"}

    coords = gc.geocode(canonical)
    if not coords:
        return {"status": "error", "message": "location not recognized"}

    set_mem(update.session_id, "last_location", canonical)
    set_mem(update.session_id, "last_entities", {"location": canonical})
    return {
        "status": "ok",
        "location": canonical,
        "coordinates": {"lat": coords[0], "lon": coords[1]},
    }
