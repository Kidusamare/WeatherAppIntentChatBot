import time
import os
from fastapi import FastAPI
from pydantic import BaseModel
from nlu.intent_model import IntentClassifier
from nlu.entities import parse_location, parse_datetime, parse_units
from core.policy import respond
from metrics.log import log_interaction
from tools import geocode as gc
from tools import weather_nws as nws

app = FastAPI(title="Weather Chatbot")

clf = IntentClassifier()
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
        "ttl": {
            "geocode": gc._ttl_seconds(),
            "forecast": nws._forecast_ttl(),
            "alerts": nws._alerts_ttl(),
        },
    }


@app.post("/predict")
def predict(q: Query):
    t0 = time.time()
    intent, conf = clf.predict(q.text)
    entities = {
        "location": parse_location(q.text),
        "datetime": parse_datetime(q.text),
        "units": parse_units(q.text),
    }
    reply = respond(intent, conf, entities, q.session_id)
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
        # Logging must not impact API response
        pass
    return {"intent": intent, "confidence": conf, "entities": entities, "reply": reply, "latency_ms": latency_ms}
