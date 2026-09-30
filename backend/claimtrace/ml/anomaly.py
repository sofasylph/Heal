"""Anomaly detectors behind one interface: detect(facts) -> list[AnomalyFlag].

rules             explainable checks (duplicates, chronology, cost z-score, ...)
isolation_forest  unsupervised model over bill-shape features, trained on normal
                  synthetic claims; flags claims that look unlike them
hybrid            both: rules for known patterns, the model for unknown ones
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Protocol

from claimtrace.anomaly.detector import detect_anomalies
from claimtrace.anomaly.reference import profile_for
from claimtrace.domain.models import AnomalyFlag, BillCategory, ClaimFacts

SHARE_CATEGORIES = [
    BillCategory.ROOM,
    BillCategory.PROCEDURE,
    BillCategory.SURGEON_FEE,
    BillCategory.NURSING,
    BillCategory.MEDICINES,
    BillCategory.DIAGNOSTICS,
    BillCategory.CONSUMABLES,
    BillCategory.IMPLANTS,
]
FEATURE_NAMES = [
    "log_bill_total",
    "cost_vs_reference",
    "stay_vs_typical",
    "line_count",
    "duplicate_lines",
    "claimed_vs_bill_gap",
    *[f"share_{c.value}" for c in SHARE_CATEGORIES],
]


def features(facts: ClaimFacts) -> list[float]:
    total = facts.bill_total or 1.0
    profile = profile_for(f"{facts.procedure or ''} {facts.diagnosis or ''}")
    keys = [(li.description.strip().lower(), round(li.amount, 2)) for li in facts.line_items]
    shares = {c: 0.0 for c in SHARE_CATEGORIES}
    for li in facts.line_items:
        if li.category in shares:
            shares[li.category] += li.amount / total
    claimed = facts.claimed_amount or total
    return [
        math.log(total),
        total / profile.mean_cost,
        (facts.length_of_stay or profile.typical_los) / profile.typical_los,
        float(len(facts.line_items)),
        float(len(keys) - len(set(keys))),
        abs(claimed - total) / claimed,
        *[shares[c] for c in SHARE_CATEGORIES],
    ]


class AnomalyDetector(Protocol):
    name: str

    def detect(self, facts: ClaimFacts) -> list[AnomalyFlag]: ...


class RulesAnomalyDetector:
    name = "rules"

    def detect(self, facts: ClaimFacts) -> list[AnomalyFlag]:
        return detect_anomalies(facts)


# Tuned on a validation set (seed 303, separate from training and the benchmark):
# bill-mix shares alone gave the best recall on padded bills (95%) at ~6.5% false alarms
# on normal claims; adding cost/stay features diluted the signal. Cost and stay outliers
# are left to the rules, which is what the hybrid detector combines.
MODEL_FEATURES = [FEATURE_NAMES.index(f"share_{c.value}") for c in SHARE_CATEGORIES]


class IsolationForestDetector:
    name = "isolation_forest"

    def __init__(self, n_claims: int = 300, contamination: float = 0.03):
        import numpy as np
        from sklearn.ensemble import IsolationForest

        from claimtrace.ml.data import normal_claim_facts

        X = np.array([features(f) for f in normal_claim_facts(n_claims) if f.line_items])
        X = X[:, MODEL_FEATURES]
        self.mean = X.mean(axis=0)
        self.std = X.std(axis=0) + 1e-9
        self.model = IsolationForest(
            n_estimators=300, contamination=contamination, random_state=0
        ).fit(X)
        self.n_train = len(X)

    def detect(self, facts: ClaimFacts) -> list[AnomalyFlag]:
        if not facts.line_items:
            return []
        x = [features(facts)[i] for i in MODEL_FEATURES]
        names = [FEATURE_NAMES[i] for i in MODEL_FEATURES]
        score = float(self.model.decision_function([x])[0])  # < 0 means outlier
        if score >= 0:
            return []
        z = [(n, (v - m) / s) for n, v, m, s in zip(names, x, self.mean, self.std, strict=True)]
        top = sorted(z, key=lambda t: abs(t[1]), reverse=True)[:3]
        drivers = ", ".join(f"{n} ({'+' if v > 0 else ''}{v:.1f} sd)" for n, v in top)
        return [
            AnomalyFlag(
                code="STATISTICAL_OUTLIER",
                severity=round(min(0.8, 0.35 + 3 * -score), 2),
                message=f"Bill shape is unlike normal claims; main drivers: {drivers}.",
                evidence={
                    "isolation_score": round(score, 4),
                    "top_drivers": {n: round(v, 2) for n, v in top},
                },
            )
        ]


class HybridDetector:
    name = "hybrid"

    def __init__(self):
        self.rules = RulesAnomalyDetector()
        self.model = get_anomaly_detector("isolation_forest")

    def detect(self, facts: ClaimFacts) -> list[AnomalyFlag]:
        return self.rules.detect(facts) + self.model.detect(facts)


ANOMALY_DETECTORS = {
    "rules": ("Rules", "Explainable checks: duplicates, chronology, cost and stay outliers."),
    "isolation_forest": (
        "Isolation Forest",
        "Unsupervised scikit-learn model over bill-shape features; catches unusual mixes.",
    ),
    "hybrid": ("Rules + Isolation Forest", "Known patterns from rules, unknown ones from ML."),
}


@lru_cache
def get_anomaly_detector(name: str = "rules") -> AnomalyDetector:
    if name == "rules":
        return RulesAnomalyDetector()
    if name == "isolation_forest":
        return IsolationForestDetector()
    if name == "hybrid":
        return HybridDetector()
    raise ValueError(f"Unknown anomaly detector '{name}'")
