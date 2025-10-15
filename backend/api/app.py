import os
import time
from functools import lru_cache

try:
    from dotenv import load_dotenv as _load_dotenv

    _load_dotenv()
except Exception:
    pass

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Backend imports
from backend.nlu.intent_model import IntentClassifier
from backend.nlu.entities import parse_location, parse_datetime, parse_units
from backend.core.policy import respond
from backend.core.memory import set_mem
from backend.metrics.log import log_interaction
from backend.nlu.loc_extractor import _get_nlp as _loc_spacy
from backend.tools import geocode as gc
from backend.tools import speech
from backend.tools import weather_nws as nws

app = FastAPI(title="Weather Chatbot")

# Absolute path to the data folder
DATA_PATH = os.path.join(os.path.dirname(__file__), "../data/nlu.yml")


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


@lru_cache(maxsize=1)
def get_intent_classifier():
    clf = IntentClassifier()
    examples = clf.load_yaml(DATA_PATH)
    clf.fit(examples)
    return clf


clf = get_intent_classifier()


class Query(BaseModel):
    text: str
    session_id: str


class SpeechSynthesisPayload(BaseModel):
    text: str
    voice: str | None = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "geo_provider": gc._provider_name(),
        "location_backend": os.getenv("LOCATION_BACKEND") or "spacy",
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


def _tts_stream_response(text: str, voice: str | None):
    try:
        generator = speech.stream_speech(text, voice_id=voice)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - unexpected failures
        raise HTTPException(status_code=500, detail="Unable to synthesize speech.") from exc
    return StreamingResponse(generator, media_type="audio/wav", headers={"Cache-Control": "no-store"})


@app.get("/speech/synthesize")
def speech_synthesize_get(text: str, voice: str | None = None):
    return _tts_stream_response(text, voice)


@app.post("/speech/synthesize")
def speech_synthesize_post(payload: SpeechSynthesisPayload):
    return _tts_stream_response(payload.text, payload.voice)


@app.post("/speech/transcribe")
async def speech_transcribe(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Audio payload is empty.")

    try:
        transcript, language, duration = speech.transcribe_wav(audio_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - unexpected failures
        raise HTTPException(status_code=500, detail="Unable to transcribe audio.") from exc

    return {
        "text": transcript,
        "language": language,
        "audio_seconds": duration,
    }
