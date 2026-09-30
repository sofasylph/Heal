"""Evaluation harness.

    python -m claimtrace.evaluation.run [--n 200] [--seed 7] [--out DIR]
    python -m claimtrace.evaluation.run --reasoner claude --cache ../docs/eval/llm_cache.jsonl

The second form enables the LLM clause reasoner (needs Anthropic credentials the first
time; afterwards responses replay from the cache, so reruns are free and deterministic).

Metrics
  extraction  : per-field accuracy against ground-truth facts
  decision    : recommendation agreement, payable-amount error
  safety      : false approvals, and false approvals that would go straight-through
  routing     : review rate, escalation recall on cases that require a human
  evidence    : share of adjustments/denials carrying a policy clause citation
  anomaly     : precision / recall of anomaly flags on seeded anomalies
  reasoner    : suggestion accuracy on ambiguous clauses, tokens, latency, cost
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from claimtrace.decision.engine import decide
from claimtrace.decision.reasoner import (
    ClaudeReasoner,
    ClauseReasoner,
    NullReasoner,
    ResponseCache,
    is_eligible,
)
from claimtrace.domain.models import (
    ClauseVerdict,
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
# USD per million tokens, for the cost estimate only (cache writes not itemised).
PRICING = {"claude-opus-5-5": {"input": 4.0, "cache_read": 0.20, "output": 20.0}}


def evaluate(dataset: list[SyntheticClaim], reasoner: ClauseReasoner | None = None) -> dict:
    reasoner = reasoner or NullReasoner()
    llm = Counter()
    field_hits: Counter = Counter()
    field_total: Counter = Counter()
    rows = []
    for sc in dataset:
        docs = ingest_documents(sc.documents)
        facts = extract(docs)
        decision = decide(get_policy(sc.policy_id), facts, docs, reasoner=reasoner)
        expected = (
            ClauseVerdict.APPLIES
            if sc.truth.recommendation is Recommendation.NOT_PAYABLE
            else ClauseVerdict.DOES_NOT_APPLY
        )
        for f in decision.findings:
            if not is_eligible(f):
                continue
            llm["eligible"] += 1
            s = f.suggestion
            if s is None:
                continue
            llm["suggestions"] += 1
            llm["correct"] += s.verdict is expected
            llm["uncertain"] += s.verdict is ClauseVerdict.UNCERTAIN
            llm["cached"] += s.cached_response
            llm["input_tokens"] += s.input_tokens
            llm["cache_read_input_tokens"] += s.cache_read_input_tokens
            llm["output_tokens"] += s.output_tokens
            llm["latency_ms"] += s.latency_ms
            llm[f"model:{s.model}"] += 1
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
                "ai_assisted": decision.ai_assisted,
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

    models = [k.split(":", 1)[1] for k in llm if k.startswith("model:")]
    price = PRICING.get(models[0]) if len(models) == 1 else None
    cost = (
        (
            llm["input_tokens"] * price["input"]
            + llm["cache_read_input_tokens"] * price["cache_read"]
            + llm["output_tokens"] * price["output"]
        )
        / 1e6
        if price
        else None
    )
    reasoner_report = {
        "reasoner": reasoner.name,
        "models": models,
        "eligible_findings": llm["eligible"],
        "suggestions": llm["suggestions"],
        "suggestion_accuracy_pct": pct(llm["correct"], llm["suggestions"]),
        "uncertain_pct": pct(llm["uncertain"], llm["suggestions"]),
        "ai_assisted_claims": sum(1 for r in rows if r["ai_assisted"]),
        "replayed_from_cache": llm["cached"],
        "input_tokens": llm["input_tokens"],
        "cache_read_input_tokens": llm["cache_read_input_tokens"],
        "output_tokens": llm["output_tokens"],
        "mean_latency_ms": round(llm["latency_ms"] / max(llm["suggestions"] - llm["cached"], 1)),
        "estimated_cost_usd": round(cost, 4) if cost is not None else None,
    }

    return {
        "n_claims": n,
        "reasoner": reasoner_report,
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


def pct(a: int, b: int) -> float | None:
    return round(100 * a / b, 1) if b else None


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
    lines += ["", "## Clause reasoner", "", "| Metric | Value |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in report["reasoner"].items()]
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
    ap.add_argument("--reasoner", choices=["none", "claude"], default="none")
    ap.add_argument("--cache", type=Path, default=None, help="JSONL response cache")
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--effort", default="high")
    args = ap.parse_args()
    reasoner: ClauseReasoner = NullReasoner()
    if args.reasoner == "claude":
        cache = ResponseCache(args.cache) if args.cache else None
        reasoner = ClaudeReasoner(model=args.model, effort=args.effort, cache=cache)
    report = evaluate(generate_dataset(args.n, args.seed), reasoner)
    md = to_markdown(report)
    print(md)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "eval_report.json").write_text(json.dumps(report, indent=2, default=str))
        (args.out / "eval_report.md").write_text(md)


if __name__ == "__main__":
    main()
