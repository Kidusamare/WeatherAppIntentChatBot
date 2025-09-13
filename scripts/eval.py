from __future__ import annotations

import argparse
import json
from typing import List, Tuple

from sklearn.metrics import classification_report, confusion_matrix

from nlu import get_intent_classifier


def load_eval_yaml(path: str) -> Tuple[List[str], List[str]]:
    import yaml
    with open(path, "r") as f:
        y = yaml.safe_load(f)
    ex = y.get("examples", []) or []
    texts = [e.get("text", "") for e in ex]
    labels = [e.get("intent", "") for e in ex]
    return texts, labels


def main():
    ap = argparse.ArgumentParser(description="Evaluate intent classifier")
    ap.add_argument("--train", default="data/nlu.yml", help="Training YAML path")
    ap.add_argument("--eval", default="data/eval.yml", help="Eval YAML path")
    args = ap.parse_args()

    clf = get_intent_classifier()
    examples = clf.load_yaml(args.train)
    clf.fit(examples)

    X_texts, y_true = load_eval_yaml(args.eval)
    y_pred = []
    y_conf = []
    for t in X_texts:
        intent, conf = clf.predict(t)
        y_pred.append(intent)
        y_conf.append(conf)

    print("\nClassification Report:\n")
    print(classification_report(y_true, y_pred, zero_division=0))
    print("Confusion Matrix:")
    print(confusion_matrix(y_true, y_pred))
    print("\nPredictions with confidence:")
    for t, p, c in zip(X_texts, y_pred, y_conf):
        print(json.dumps({"text": t, "pred": p, "conf": round(float(c), 3)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

