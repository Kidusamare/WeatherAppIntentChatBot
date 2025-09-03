from dataclasses import dataclass
from typing import List, Tuple
import re
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
        self.vectorizer = TfidfVectorizer(ngram_range=(1,2), min_df=1)
        self.clf = LogisticRegression(max_iter=1000, class_weight="balanced")
        self.trained = False

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
        idx = int(proba.argmax())
        return self.clf.classes_[idx], float(proba[idx])
