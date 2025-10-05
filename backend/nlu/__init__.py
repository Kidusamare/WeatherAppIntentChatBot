from __future__ import annotations

import os
import sys


def get_intent_classifier():
    """Factory returning the configured intent classifier.

    Default is the lightweight TF‑IDF pipeline. Set INTENT_BACKEND=bert to use
    the Hugging Face encoder + linear head (requires transformers + torch).
    Gracefully falls back to TF‑IDF if the BERT stack is unavailable.
    """
    backend = (os.getenv("INTENT_BACKEND") or "tfidf").strip().lower()
    if backend == "bert":
        try:
            from .intent_hf import HFIntentClassifier  # type: ignore
            return HFIntentClassifier()
        except Exception as e:  # pragma: no cover
            print(
                f"[nlu] WARN: BERT backend requested but unavailable ({e}); falling back to TF‑IDF",
                file=sys.stderr,
            )
    from .intent_model import IntentClassifier
    return IntentClassifier()
