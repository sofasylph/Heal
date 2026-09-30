"""Compare switchable models on the benchmark.

    python -m claimtrace.evaluation.compare --out ../docs/eval
    python -m claimtrace.evaluation.compare --reasoners none,claude:claude-haiku-4-5,ollama:qwen3:8b

Writes model_comparison.md / .json. Reasoners that cannot run (no credentials, Ollama not
running) are reported as skipped rather than silently scored as "none".
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from claimtrace.decision.reasoner import (
    ClaudeReasoner,
    NullReasoner,
    OllamaReasoner,
    ResponseCache,
    ollama_models,
)
from claimtrace.evaluation.run import evaluate
from claimtrace.evaluation.synthetic import generate_dataset
from claimtrace.ml.anomaly import ANOMALY_DETECTORS, get_anomaly_detector
from claimtrace.ml.data import TEST_SEED, degrade, labelled_documents
from claimtrace.ml.doc_classifier import DOC_CLASSIFIERS, get_doc_classifier
from claimtrace.settings.components import claude_credentials_present


def compare_classifiers(n_claims: int = 80) -> list[dict]:
    test = labelled_documents(n_claims, TEST_SEED, degraded_share=0)
    rows = []
    for name in DOC_CLASSIFIERS:
        clf = get_doc_classifier(name)
        clean = sum(clf.classify(t)[0] is label for t, label in test)
        degraded = sum(
            clf.classify(degrade(t, random.Random(i)))[0] is label
            for i, (t, label) in enumerate(test)
        )
        rows.append(
            {
                "classifier": name,
                "documents": len(test),
                "clean_accuracy_pct": round(100 * clean / len(test), 1),
                "degraded_accuracy_pct": round(100 * degraded / len(test), 1),
            }
        )
    return rows


BENCH_KEYS = [
    "decision_agreement_pct",
    "unsafe_straight_through_pct",
    "escalation_recall_pct",
    "straight_through_pct",
    "anomaly_recall_pct",
    "anomaly_precision_pct",
]


def compare_detectors(dataset) -> list[dict]:
    rows = []
    for name in ANOMALY_DETECTORS:
        r = evaluate(dataset, detector=get_anomaly_detector(name))
        rows.append({"detector": name, **{k: r[k] for k in BENCH_KEYS}})
    return rows


def _reasoner(spec: str, cache: ResponseCache | None):
    provider, _, model = spec.partition(":")
    if provider == "none":
        return NullReasoner(), None
    if provider == "claude":
        if not claude_credentials_present() and cache is None:
            return None, "no Anthropic credentials"
        return ClaudeReasoner(model=model or "claude-opus-5-5", cache=cache), None
    if provider == "ollama":
        if ollama_models() is None:
            return None, "Ollama not reachable on localhost:11434"
        return OllamaReasoner(model=model, cache=cache), None
    return None, f"unknown provider '{provider}'"


def compare_reasoners(dataset, specs: list[str], cache: ResponseCache | None) -> list[dict]:
    rows = []
    detector = get_anomaly_detector("hybrid")
    for spec in specs:
        reasoner, skip = _reasoner(spec, cache)
        if reasoner is None:
            rows.append({"reasoner": spec, "skipped": skip})
            continue
        r = evaluate(dataset, reasoner, detector=detector)
        rr = r["reasoner"]
        rows.append(
            {
                "reasoner": spec,
                **{k: r[k] for k in BENCH_KEYS[:4]},
                "suggestions": rr["suggestions"],
                "suggestion_accuracy_pct": rr["suggestion_accuracy_pct"],
                "uncertain_pct": rr["uncertain_pct"],
                "mean_latency_ms": rr["mean_latency_ms"],
                "estimated_cost_usd": rr["estimated_cost_usd"],
            }
        )
    return rows


def _table(rows: list[dict]) -> list[str]:
    if not rows:
        return []
    cols = list(dict.fromkeys(k for r in rows for k in r))
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows]
    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument(
        "--reasoners",
        default="none,claude:claude-haiku-4-5,claude:claude-sonnet-5-5,"
        "claude:claude-opus-5-5,ollama:qwen3:8b",
    )
    ap.add_argument("--cache", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    dataset = generate_dataset(args.n, args.seed)
    cache = ResponseCache(args.cache) if args.cache else None
    result = {
        "document_classifiers": compare_classifiers(),
        "anomaly_detectors": compare_detectors(dataset),
        "clause_reasoners": compare_reasoners(dataset, args.reasoners.split(","), cache),
    }
    md = [
        "# Model comparison",
        "",
        f"Benchmark: {args.n} synthetic claims (seed {args.seed}). Document classifiers are "
        f"scored on a separate held-out set (seed {TEST_SEED}); 'degraded' drops all-caps "
        "headers and 30% of lines to mimic poor scans.",
        "",
        "## Document classifiers",
        "",
        *_table(result["document_classifiers"]),
        "",
        "## Anomaly detectors (keyword classifier, no clause reasoner)",
        "",
        *_table(result["anomaly_detectors"]),
        "",
        "## Clause reasoners (hybrid anomaly detector)",
        "",
        *_table(result["clause_reasoners"]),
        "",
    ]
    text = "\n".join(md)
    print(text)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "model_comparison.md").write_text(text)
        (args.out / "model_comparison.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
