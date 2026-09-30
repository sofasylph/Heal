"""Regression guard on the safety properties of the decision system."""

from claimtrace.evaluation.run import evaluate
from claimtrace.evaluation.synthetic import generate_dataset


def test_safety_properties_hold_on_synthetic_benchmark():
    report = evaluate(generate_dataset(n=120, seed=11))
    assert report["unsafe_straight_through_pct"] == 0.0
    assert report["escalation_recall_pct"] == 100.0
    assert report["false_rejection_pct"] == 0.0
    assert report["citation_coverage_pct"] == 100.0
    assert report["decision_agreement_pct"] >= 85.0
