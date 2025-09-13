from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Tuple, Dict

import torch
from transformers import AutoTokenizer, AutoModel
import yaml
from sklearn.linear_model import LogisticRegression


def normalize(s: str) -> str:
    # Keep light normalization; tokenizer handles casing/punctuation
    return s.strip()


@dataclass
class IntentExample:
    text: str
    intent: str


class HFIntentClassifier:
    """BERT-powered intent classifier using frozen embeddings + linear head.

    - Uses a Hugging Face encoder (default: distilbert-base-uncased)
    - Extracts mean-pooled token embeddings
    - Trains LogisticRegression on embeddings for our small dataset
    - Keeps inference fast and avoids heavy fine-tuning
    """

    def __init__(self, model_name: str | None = None, device: str | None = None):
        self.model_name = model_name or os.getenv("HF_MODEL_NAME", "distilbert-base-uncased")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.encoder = AutoModel.from_pretrained(self.model_name)
        self.encoder.eval()
        if device:
            self.device = device
        else:
            # Prefer CPU for portability in small projects
            self.device = os.getenv("HF_DEVICE", "cpu")
        self.encoder.to(self.device)
        self.clf = LogisticRegression(max_iter=2000, class_weight="balanced", C=3.0)
        self.trained = False

    def load_yaml(self, path: str) -> List[IntentExample]:
        with open(path, "r") as f:
            y = yaml.safe_load(f)
        examples: List[IntentExample] = []
        for intent, samples in (y.get("intents", {}) or {}).items():
            for s in (samples or []):
                examples.append(IntentExample(text=normalize(s), intent=intent))
        return examples

    @torch.no_grad()
    def _embed(self, texts: List[str]) -> torch.Tensor:
        # Tokenize with truncation for safety
        toks = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=int(os.getenv("HF_MAX_LEN", "128")),
            return_tensors="pt",
        )
        toks = {k: v.to(self.device) for k, v in toks.items()}
        outputs = self.encoder(**toks)
        hidden = outputs.last_hidden_state  # [B, T, H]
        mask = toks["attention_mask"].unsqueeze(-1)  # [B, T, 1]
        masked = hidden * mask
        lengths = mask.sum(dim=1).clamp(min=1)
        mean_pooled = masked.sum(dim=1) / lengths  # [B, H]
        return mean_pooled.cpu()

    def fit(self, examples: List[IntentExample]):
        X = self._embed([e.text for e in examples]).numpy()
        y = [e.intent for e in examples]
        self.clf.fit(X, y)
        self.trained = True

    def predict(self, text: str) -> Tuple[str, float]:
        if not self.trained:
            raise RuntimeError("Model not trained. Call fit() first.")
        X = self._embed([normalize(text)]).numpy()
        proba = self.clf.predict_proba(X)[0]
        idx = int(proba.argmax())
        return self.clf.classes_[idx], float(proba[idx])

