"""Anomaly flags for investigation prioritisation (not fraud determination).

Each check is simple and explainable; the combined risk score is a noisy-OR of flag
severities, so any single strong signal dominates while weak signals accumulate.
"""

from __future__ import annotations

from collections import Counter

from claimtrace.anomaly.reference import profile_for
from claimtrace.domain.models import AnomalyFlag, ClaimFacts


def detect_anomalies(facts: ClaimFacts) -> list[AnomalyFlag]:
    flags: list[AnomalyFlag] = []

    keys = Counter((li.description.strip().lower(), round(li.amount, 2)) for li in facts.line_items)
    dupes = [f"{d} (INR {a:,.0f}) x{n}" for (d, a), n in keys.items() if n > 1]
    if dupes:
        flags.append(
            AnomalyFlag(
                code="DUPLICATE_LINE_ITEM",
                severity=0.5,
                message="Identical bill line items appear more than once.",
                evidence={"duplicates": dupes},
            )
        )

    if (
        facts.admission_date
        and facts.discharge_date
        and facts.discharge_date < facts.admission_date
    ):
        flags.append(
            AnomalyFlag(
                code="IMPOSSIBLE_CHRONOLOGY",
                severity=0.9,
                message="Discharge date is before admission date.",
                evidence={
                    "admission": str(facts.admission_date),
                    "discharge": str(facts.discharge_date),
                },
            )
        )

    if facts.claimed_amount and facts.line_items:
        diff = abs(facts.claimed_amount - facts.bill_total)
        if diff > max(0.01 * facts.claimed_amount, 1.0):
            flags.append(
                AnomalyFlag(
                    code="BILL_TOTAL_MISMATCH",
                    severity=0.5,
                    message="Claimed amount does not match itemised bill total.",
                    evidence={"claimed": facts.claimed_amount, "bill_total": facts.bill_total},
                )
            )

    profile = profile_for(f"{facts.procedure or ''} {facts.diagnosis or ''}")
    total = facts.bill_total or facts.claimed_amount or 0
    if total:
        z = (total - profile.mean_cost) / profile.std_cost
        if z > 3:
            sev = 0.6
        elif z > 2:
            sev = 0.35
        else:
            sev = 0.0
        if sev:
            flags.append(
                AnomalyFlag(
                    code="COST_OUTLIER",
                    severity=sev,
                    message=f"Bill is {z:.1f} std devs above typical cost for {profile.name}.",
                    evidence={
                        "bill_total": total,
                        "reference_mean": profile.mean_cost,
                        "z_score": round(z, 2),
                    },
                )
            )

    los = facts.length_of_stay
    if los and los > max(3 * profile.typical_los, profile.typical_los + 4):
        flags.append(
            AnomalyFlag(
                code="LENGTH_OF_STAY_OUTLIER",
                severity=0.4,
                message=f"Stay of {los} days vs typical {profile.typical_los} for {profile.name}.",
                evidence={"length_of_stay": los, "typical": profile.typical_los},
            )
        )

    if len(facts.line_items) >= 4:
        round_share = sum(1 for li in facts.line_items if li.amount % 1000 == 0) / len(
            facts.line_items
        )
        if round_share >= 0.8:
            flags.append(
                AnomalyFlag(
                    code="ROUND_AMOUNTS",
                    severity=0.2,
                    message="Most line items are round thousands.",
                    evidence={"round_share": round(round_share, 2)},
                )
            )
    return flags


def risk_score(flags: list[AnomalyFlag]) -> float:
    p = 1.0
    for f in flags:
        p *= 1 - f.severity
    return round(1 - p, 3)
