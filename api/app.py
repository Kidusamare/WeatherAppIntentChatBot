from fastapi import FastAPI
from pydantic import BaseModel
from nlu.intent_model import IntentClassifier
from nlu.entities import parse_location, parse_datetime, parse_units
from core.policy import respond

app = FastAPI(title="Weather Chatbot")

clf = IntentClassifier()
examples = clf.load_yaml("data/nlu.yml")
clf.fit(examples)


class Query(BaseModel):
    text: str
    session_id: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/predict")
def predict(q: Query):
    intent, conf = clf.predict(q.text)
    entities = {
        "location": parse_location(q.text),
        "datetime": parse_datetime(q.text),
        "units": parse_units(q.text),
    }
    reply = respond(intent, conf, entities, q.session_id)
    return {"intent": intent, "confidence": conf, "entities": entities, "reply": reply}
