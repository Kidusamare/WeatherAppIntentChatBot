from __future__ import annotations

import os


def get_intent_classifier():
    """Factory returning the configured intent classifier.

    Default is the lightweight TF‑IDF pipeline. Set INTENT_BACKEND=bert to use
    the Hugging Face encoder + linear head (requires transformers + torch).
    """
    backend = (os.getenv("INTENT_BACKEND") or "tfidf").strip().lower()
    if backend == "bert":
        from .intent_hf import HFIntentClassifier
        return HFIntentClassifier()
    else:
        from .intent_model import IntentClassifier
        return IntentClassifier()

