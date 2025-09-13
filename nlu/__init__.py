from __future__ import annotations

import os


def get_intent_classifier():
    """Factory returning the configured intent classifier.

    Default backend is Hugging Face (bert). Set INTENT_BACKEND=tfidf to use the
    scikit‑learn pipeline for offline/dev.
    """
    backend = (os.getenv("INTENT_BACKEND") or "bert").strip().lower()
    if backend == "bert":
        from .intent_hf import HFIntentClassifier
        return HFIntentClassifier()
    else:
        from .intent_model import IntentClassifier
        return IntentClassifier()
