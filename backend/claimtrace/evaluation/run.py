"""Evaluation harness: python -m claimtrace.evaluation.run [--n 200] [--seed 7] [--out DIR]

Metrics
  extraction  : per-field accuracy against ground-truth facts
  decision    : recommendation agreement, payable-amount error
  safety      : false approvals, and false approvals that would go straight-through
  routing     : review rate, escalation recall on cases that require a human
  evidence    : share of adjustments/denials carrying a policy clause citation
  anomaly     : precision / recall of anomaly flags on seeded anomalies
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from claimtrace.decision.engine import decide
from claimtrace.domain.models import (
    FindingOutcome,
    Recommendation,
    ReviewRoute,
)
from claimtrace.evaluation.synthetic import SyntheticClaim, generate_dataset
from claimtrace.extraction.pipeline import extract, ingest_documents
from claimtrace.policies.registry import get_policy

FIELDS = [
    "patient_name",
    "patient_age",
    "policy_start_date",
    "admission_date",
    "discharge_date",
    "diagnosis",
    "procedure",
    "claimed_amount",
]
APPROVE = {Recommendation.PAY, Recommendation.PARTIAL}


def evaluate(dataset: list[SyntheticClaim]) -> dict:
    field_hits: Counter = Counter()
    field_total: Counter = Counter()
    rows = []
    for sc in dataset:
        docs = ingest_documents(sc.documents)
        facts = extract(docs)
        decision = decide(get_policy(sc.policy_id), facts, docs)
        tf = sc.truth_facts
        present_types = {d.doc_type for d in docs}
        for f in FIELDS:
            truth_val = getattr(tf, f)
            if f in ("diagnosis", "procedure") and len(present_types) < 3:
                continue  # field's source document intentionally withheld
            field_total[f] += 1
            if getattr(facts, f) == truth_val:
                field_hits[f] += 1
        rows.append(
            {
                "claim_id": sc.claim_id,
                "policy_id": sc.policy_id,
                "scenario": sc.scenario.value,
                "truth": sc.truth.recommendation.value,
                "pred": decision.recommendation.value,
                "truth_payable": sc.truth.payable_amount,
                "pred_payable": decision.payable_amount,
                "route": decision.route.value,
                "requires_human": sc.truth.requires_human,
                "should_flag": sc.truth.should_flag_anomaly,
                "flagged": bool(decision.anomalies),
                "confidence": decision.confidence,
                "cited": sum(
                    1
                    for f in decision.findings
                    if f.outcome in (FindingOutcome.ADJUST, FindingOutcome.DENY)
                    and f.clause is not None
                ),
                "citable": sum(
                    1
                    for f in decision.findings
                    if f.outcome in (FindingOutcome.ADJUST, FindingOutcome.DENY)
                ),
            }
        )

    n = len(rows)
    agree = [r for r in rows if r["truth"] == r["pred"]]
    false_approvals = [r for r in rows if r["pred"] in APPROVE and r["truth"] not in APPROVE]
    false_rejections = [r for r in rows if r["truth"] in APPROVE and r["pred"] not in APPROVE]
    straight_through = [r for r in rows if r["route"] == ReviewRoute.AUTO_CANDIDATE]
    unsafe_auto = [
        r
        for r in straight_through
        if r["truth"] != r["pred"] or abs(r["truth_payable"] - r["pred_payable"]) > 1
    ]
    payable_rows = [r for r in rows if r["truth"] in APPROVE and r["pred"] in APPROVE]
    abs_err = [abs(r["truth_payable"] - r["pred_payable"]) for r in payable_rows]
    need_human = [r for r in rows if r["requires_human"]]
    flag_truth = [r for r in rows if r["should_flag"]]
    flagged = [r for r in rows if r["flagged"]]

    by_scenario: dict[str, dict] = defaultdict(lambda: {"n": 0, "agree": 0, "auto": 0})
    for r in rows:
        s = by_scenario[r["scenario"]]
        s["n"] += 1
        s["agree"] += r["truth"] == r["pred"]
        s["auto"] += r["route"] == ReviewRoute.AUTO_CANDIDATE

    def pct(a: int, b: int) -> float | None:
        return round(100 * a / b, 1) if b else None

    return {
        "n_claims": n,
        "extraction_field_accuracy": {f: pct(field_hits[f], field_total[f]) for f in FIELDS},
        "decision_agreement_pct": pct(len(agree), n),
        "false_approval_pct": pct(len(false_approvals), n),
        "false_rejection_pct": pct(len(false_rejections), n),
        "unsafe_straight_through_pct": pct(len(unsafe_auto), n),
        "straight_through_pct": pct(len(straight_through), n),
        "human_review_pct": pct(n - len(straight_through), n),
        "escalation_recall_pct": pct(
            sum(1 for r in need_human if r["route"] != ReviewRoute.AUTO_CANDIDATE), len(need_human)
        ),
        "payable_exact_match_pct": pct(sum(1 for e in abs_err if e <= 1), len(abs_err)),
        "payable_mae_inr": round(statistics.mean(abs_err), 2) if abs_err else None,
        "citation_coverage_pct": pct(
            sum(r["cited"] for r in rows), sum(r["citable"] for r in rows)
        ),
        "anomaly_recall_pct": pct(sum(1 for r in flag_truth if r["flagged"]), len(flag_truth)),
        "anomaly_precision_pct": pct(sum(1 for r in flagged if r["should_flag"]), len(flagged)),
        "by_scenario": {
            k: {
                "n": v["n"],
                "agreement_pct": pct(v["agree"], v["n"]),
                "straight_through_pct": pct(v["auto"], v["n"]),
            }
            for k, v in sorted(by_scenario.items())
        },
        "disagreements": [r for r in rows if r["truth"] != r["pred"]][:25],
    }


def to_markdown(report: dict) -> str:
    lines = [
        "# ClaimTrace evaluation report",
        "",
        f"Synthetic claims: **{report['n_claims']}** (see `evaluation/synthetic.py`).",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    keys = [
        "decision_agreement_pct",
        "false_approval_pct",
        "false_rejection_pct",
        "unsafe_straight_through_pct",
        "straight_through_pct",
        "human_review_pct",
        "escalation_recall_pct",
        "payable_exact_match_pct",
        "payable_mae_inr",
        "citation_coverage_pct",
        "anomaly_recall_pct",
        "anomaly_precision_pct",
    ]
    for k in keys:
        lines.append(f"| {k} | {report[k]} |")
    lines += ["", "## Extraction field accuracy (%)", "", "| Field | Accuracy |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in report["extraction_field_accuracy"].items()]
    lines += [
        "",
        "## By scenario",
        "",
        "| Scenario | n | Agreement % | Straight-through % |",
        "|---|---:|---:|---:|",
    ]
    lines += [
        f"| {k} | {v['n']} | {v['agreement_pct']} | {v['straight_through_pct']} |"
        for k, v in report["by_scenario"].items()
    ]
    lines += [
        "",
        "## Disagreements (first 25)",
        "",
        "| Claim | Scenario | Truth | Predicted | Route |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {r['claim_id']} | {r['scenario']} | {r['truth']} | {r['pred']} | {r['route']} |"
        for r in report["disagreements"]
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    report = evaluate(generate_dataset(args.n, args.seed))
    md = to_markdown(report)
    print(md)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "eval_report.json").write_text(json.dumps(report, indent=2, default=str))
        (args.out / "eval_report.md").write_text(md)


if __name__ == "__main__":
    main()
