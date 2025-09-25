from __future__ import annotations

import argparse
import json
from typing import List, Tuple

from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from nlu import get_intent_classifier


def load_eval_yaml(path: str) -> Tuple[List[str], List[str]]:
    import yaml
    with open(path, "r") as f:
        y = yaml.safe_load(f)
    ex = y.get("examples", []) or []
    texts = [e.get("text", "") for e in ex]
    labels = [e.get("intent", "") for e in ex]
    return texts, labels


def run_eval(train_path: str, eval_path: str) -> dict:
    clf = get_intent_classifier()
    examples = clf.load_yaml(train_path)
    clf.fit(examples)

    X_texts, y_true = load_eval_yaml(eval_path)
    y_pred = []
    y_conf = []
    for t in X_texts:
        intent, conf = clf.predict(t)
        y_pred.append(intent)
        y_conf.append(conf)

    acc = accuracy_score(y_true, y_pred)
    cm = confusion_matrix(y_true, y_pred)
    report = classification_report(y_true, y_pred, zero_division=0)

    return {
        "accuracy": float(acc),
        "texts": X_texts,
        "true": y_true,
        "pred": y_pred,
        "conf": y_conf,
        "confusion_matrix": cm,
        "classification_report": report,
    }


def main():
    ap = argparse.ArgumentParser(description="Evaluate intent classifier")
    ap.add_argument("--train", default="data/nlu.yml", help="Training YAML path")
    ap.add_argument("--eval", default="data/eval.yml", help="Eval YAML path")
    ap.add_argument("--min-accuracy", type=float, default=None, help="Optional minimum accuracy threshold")
    ap.add_argument("--json", default=None, help="Optional path to write summary JSON")
    args = ap.parse_args()

    results = run_eval(args.train, args.eval)
    acc = results["accuracy"]

    print("\nOverall accuracy: {:.3f}".format(acc))
    print("\nClassification Report:\n")
    print(results["classification_report"])
    print("Confusion Matrix:")
    print(results["confusion_matrix"])
    print("\nPredictions with confidence:")
    for t, p, c in zip(results["texts"], results["pred"], results["conf"]):
        print(json.dumps({"text": t, "pred": p, "conf": round(float(c), 3)}, ensure_ascii=False))

    if args.json:
        summary = {
            "accuracy": float(acc),
            "confusion_matrix": results["confusion_matrix"].tolist(),
            "labels": sorted(set(results["true"]) | set(results["pred"])),
        }
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, ensure_ascii=False, indent=2)

    if args.min_accuracy is not None and acc < args.min_accuracy:
        raise SystemExit(f"Accuracy {acc:.3f} < required threshold {args.min_accuracy:.3f}")


if __name__ == "__main__":
    main()
