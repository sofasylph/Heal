"""Combines rule findings and anomaly flags into a recommendation and review route.

Routing policy (the product decision, not the model's):
  * any REVIEW finding, confidence < 0.70 or risk >= 0.60  -> ESCALATE
  * confidence < 0.90, risk >= 0.30, or any denial           -> HUMAN_VERIFY
  * otherwise                                                -> AUTO_CANDIDATE
Denials are never auto-processed: a human signs off on every "not payable".
"""

from __future__ import annotations

from datetime import UTC, datetime

from claimtrace import ENGINE_VERSION
from claimtrace.anomaly.detector import detect_anomalies, risk_score
from claimtrace.domain.models import (
    ClaimDocument,
    ClaimFacts,
    Decision,
    FindingOutcome,
    Recommendation,
    ReviewRoute,
)
from claimtrace.policies.models import Policy
from claimtrace.rules.engine import run_rules

ESCALATE_CONFIDENCE = 0.70
VERIFY_CONFIDENCE = 0.90
ESCALATE_RISK = 0.60
VERIFY_RISK = 0.30


def decide(policy: Policy, facts: ClaimFacts, documents: list[ClaimDocument]) -> Decision:
    result = run_rules(policy, facts, documents)
    findings = result.findings
    anomalies = detect_anomalies(facts)
    risk = risk_score(anomalies)
    claimed = facts.claimed_amount if facts.claimed_amount is not None else facts.bill_total

    outcomes = {f.outcome for f in findings}
    payable = result.payable_amount
    if FindingOutcome.NEEDS_INFO in outcomes:
        rec, payable = Recommendation.NEEDS_INFO, 0.0
    elif FindingOutcome.DENY in outcomes:
        rec, payable = Recommendation.NOT_PAYABLE, 0.0
    elif payable >= claimed - 0.5:
        rec = Recommendation.PAY
    else:
        rec = Recommendation.PARTIAL

    confidence = round(min((f.confidence for f in findings), default=0.0), 3)

    if (
        FindingOutcome.REVIEW in outcomes
        or confidence < ESCALATE_CONFIDENCE
        or risk >= ESCALATE_RISK
    ):
        route = ReviewRoute.ESCALATE
    elif (
        confidence < VERIFY_CONFIDENCE
        or risk >= VERIFY_RISK
        or rec in (Recommendation.NOT_PAYABLE, Recommendation.NEEDS_INFO)
    ):
        route = ReviewRoute.HUMAN_VERIFY
    else:
        route = ReviewRoute.AUTO_CANDIDATE

    return Decision(
        recommendation=rec,
        route=route,
        claimed_amount=round(claimed, 2),
        payable_amount=round(payable, 2),
        confidence=confidence,
        risk_score=risk,
        findings=findings,
        anomalies=anomalies,
        payable_lines=result.payable_lines,
        summary=_summarise(rec, route, claimed, payable, findings),
        engine_version=ENGINE_VERSION,
        policy_version=f"{policy.policy_id}@{policy.version}",
        decided_at=datetime.now(UTC),
    )


def _summarise(rec, route, claimed, payable, findings) -> str:
    material = [f for f in findings if f.outcome not in (FindingOutcome.PASS,)]
    head = {
        Recommendation.PAY: f"Payable in full: INR {payable:,.0f}.",
        Recommendation.PARTIAL: f"Partially payable: INR {payable:,.0f} of INR {claimed:,.0f}.",
        Recommendation.NOT_PAYABLE: "Not payable.",
        Recommendation.NEEDS_INFO: "Cannot adjudicate: information missing.",
    }[rec]
    reasons = "; ".join(f.message.rstrip(".") for f in material[:3])
    reasons = f"{reasons}." if reasons else ""
    tail = {
        ReviewRoute.AUTO_CANDIDATE: "Eligible for straight-through processing.",
        ReviewRoute.HUMAN_VERIFY: "Reviewer verification required.",
        ReviewRoute.ESCALATE: "Escalated for senior review.",
    }[route]
    return " ".join(x for x in (head, reasons, tail) if x)
