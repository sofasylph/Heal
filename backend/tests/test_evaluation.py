"""Regression guard on the safety properties of the decision system."""

from claimtrace.evaluation.run import evaluate
from claimtrace.evaluation.synthetic import generate_dataset
from claimtrace.ml.anomaly import get_anomaly_detector
from claimtrace.ml.doc_classifier import get_doc_classifier


def _default_stack(dataset, **kw):
    return evaluate(
        dataset,
        classifier=get_doc_classifier("tfidf_logreg"),
        detector=get_anomaly_detector("hybrid"),
        **kw,
    )


def test_safety_properties_hold_on_synthetic_benchmark():
    report = _default_stack(generate_dataset(n=120, seed=11))
    assert report["unsafe_straight_through_pct"] == 0.0
    assert report["false_rejection_pct"] == 0.0
    assert report["citation_coverage_pct"] == 100.0
    assert report["decision_agreement_pct"] >= 85.0
    assert report["escalation_recall_pct"] >= 90.0
    assert report["anomaly_recall_pct"] >= 80.0


def test_rules_only_detector_misses_padded_pharmacy():
    """Documents why the hybrid detector is the default: the rules cannot see a bill
    whose total is normal but whose mix is not."""
    dataset = [c for c in generate_dataset(n=200, seed=7) if c.scenario == "padded_pharmacy"]
    rules = evaluate(dataset, detector=get_anomaly_detector("rules"))
    hybrid = evaluate(dataset, detector=get_anomaly_detector("hybrid"))
    assert rules["anomaly_recall_pct"] < 20
    assert hybrid["anomaly_recall_pct"] >= 70
