"""Portfolio analytics over the claims store (computed in Python; fine at demo scale,
move to SQL aggregates when volumes grow)."""

from __future__ import annotations

from collections import Counter, defaultdict

from sqlalchemy.orm import Session

from claimtrace.claims.service import list_claims
from claimtrace.domain.models import Claim, FindingOutcome, ReviewRoute


def _bucket(conf: float) -> str:
    if conf < 0.7:
        return "< 70%"
    if conf < 0.9:
        return "70-90%"
    return ">= 90%"


def compute(session: Session) -> dict:
    claims = [Claim.model_validate(r.data) for r in list_claims(session)]
    decided = [c for c in claims if c.decision]
    n = len(decided)

    rec = Counter()
    route = Counter()
    conf = Counter()
    anomalies = Counter()
    models = defaultdict(Counter)
    deductions: dict[str, float] = defaultdict(float)
    by_policy: dict[str, dict] = defaultdict(lambda: {"claims": 0, "claimed": 0.0, "payable": 0.0})
    disagreements_by_rule = Counter()
    claimed_total = system_payable = final_payable = 0.0
    finalised = agreed = ai_assisted = 0

    for c in decided:
        d = c.decision
        final = c.override or d
        rec[final.recommendation.value] += 1
        route[d.route.value] += 1
        conf[_bucket(d.confidence)] += 1
        ai_assisted += d.ai_assisted
        claimed_total += d.claimed_amount
        system_payable += d.payable_amount
        final_payable += final.payable_amount
        p = by_policy[c.policy_id]
        p["claims"] += 1
        p["claimed"] += d.claimed_amount
        p["payable"] += final.payable_amount
        for a in d.anomalies:
            anomalies[a.code] += 1
        for k, v in d.models_used.items():
            models[k][v] += 1
        for f in d.findings:
            if f.outcome is FindingOutcome.ADJUST and f.amount_impact < 0:
                deductions[f.title] += -f.amount_impact
        if c.override:
            finalised += 1
            agrees = (
                c.override.recommendation == d.recommendation
                and abs(c.override.payable_amount - d.payable_amount) < 1
            )
            agreed += agrees
            if not agrees:
                for f in d.findings:
                    if f.outcome is not FindingOutcome.PASS:
                        disagreements_by_rule[f.title] += 1

    def pct(a: float, b: float) -> float | None:
        return round(100 * a / b, 1) if b else None

    return {
        "claims": len(claims),
        "decided": n,
        "totals": {
            "claimed": round(claimed_total, 2),
            "system_payable": round(system_payable, 2),
            "final_payable": round(final_payable, 2),
            "not_paid": round(claimed_total - final_payable, 2),
        },
        "straight_through_pct": pct(route[ReviewRoute.AUTO_CANDIDATE.value], n),
        "ai_assisted_claims": ai_assisted,
        "by_recommendation": dict(rec),
        "by_route": dict(route),
        "by_confidence": dict(conf),
        "by_policy": {
            k: {**v, "claimed": round(v["claimed"], 2), "payable": round(v["payable"], 2)}
            for k, v in by_policy.items()
        },
        "deductions_by_rule": {
            k: round(v, 2) for k, v in sorted(deductions.items(), key=lambda kv: -kv[1])
        },
        "anomalies_by_code": dict(anomalies.most_common()),
        "reviewer": {
            "finalised": finalised,
            "agreement_pct": pct(agreed, finalised),
            "overridden": finalised - agreed,
            "disagreements_by_rule": dict(disagreements_by_rule.most_common()),
        },
        "models_used": {k: dict(v) for k, v in models.items()},
    }
