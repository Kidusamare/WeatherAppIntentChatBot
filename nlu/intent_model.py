from dataclasses import dataclass
from typing import List, Tuple
import os
import re

import numpy as np
import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

def normalize(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s

@dataclass
class IntentExample:
    text: str
    intent: str

class IntentClassifier:
    def __init__(self):
        # Slightly richer features to improve confidence on varied phrasings
        self.vectorizer = TfidfVectorizer(ngram_range=(1,3), min_df=1)
        self.clf = LogisticRegression(max_iter=2000, class_weight="balanced", C=3.0)
        self.trained = False
        # Temperature < 1 sharpens probabilities, > 1 smooths them
        temp = float(os.getenv("INTENT_CONF_TEMPERATURE", "0.75"))
        # Clamp to avoid degenerate behaviour; 1e-3 lower bound is plenty
        self.temperature = max(temp, 1e-3)

    def load_yaml(self, path: str) -> List[IntentExample]:
        with open(path, "r") as f:
            y = yaml.safe_load(f)
        examples: List[IntentExample] = []
        for intent, samples in y.get("intents", {}).items():
            for s in samples or []:
                examples.append(IntentExample(text=normalize(s), intent=intent))
        return examples

    def fit(self, examples: List[IntentExample]):
        X = self.vectorizer.fit_transform([e.text for e in examples])
        y = [e.intent for e in examples]
        self.clf.fit(X, y)
        self.trained = True

    def predict(self, text: str) -> Tuple[str, float]:
        if not self.trained:
            raise RuntimeError("Model not trained. Call fit() first.")
        x = self.vectorizer.transform([normalize(text)])
        proba = self.clf.predict_proba(x)[0]
        if self.temperature != 1.0:
            # Convert to log space to emulate softmax temperature scaling
            logits = np.log(np.clip(proba, 1e-9, 1.0)) / self.temperature
            exp = np.exp(logits - logits.max())
            proba = exp / exp.sum()
        idx = int(proba.argmax())
        return self.clf.classes_[idx], float(proba[idx])
