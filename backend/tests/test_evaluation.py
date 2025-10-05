from backend.scripts import eval as eval_script


def test_intent_classifier_accuracy():
    results = eval_script.run_eval("data/nlu.yml", "data/eval.yml")
    assert results["accuracy"] >= 0.9
