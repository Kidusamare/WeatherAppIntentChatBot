from nlu.intent_model import IntentClassifier
def main():
    clf = IntentClassifier()
    examples = clf.load_yaml("data/nlu.yml")
    clf.fit(examples)
    print(f"Trained on {len(examples)} examples.")
if __name__ == "__main__":
    main()
