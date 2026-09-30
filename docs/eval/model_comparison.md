# Model comparison

Benchmark: 200 synthetic claims (seed 7). Document classifiers are scored on a separate held-out set (seed 202); 'degraded' drops all-caps headers and 30% of lines to mimic poor scans.

## Document classifiers

| classifier | documents | clean_accuracy_pct | degraded_accuracy_pct |
|---|---|---|---|
| keyword | 480 | 100.0 | 85.2 |
| tfidf_logreg | 480 | 100.0 | 99.8 |

## Anomaly detectors (keyword classifier, no clause reasoner)

| detector | decision_agreement_pct | unsafe_straight_through_pct | escalation_recall_pct | straight_through_pct | anomaly_recall_pct | anomaly_precision_pct |
|---|---|---|---|---|---|---|
| rules | 93.5 | 0.0 | 77.6 | 46.5 | 50.0 | 71.4 |
| isolation_forest | 93.5 | 4.5 | 80.6 | 43.5 | 56.7 | 45.9 |
| hybrid | 93.5 | 0.0 | 95.5 | 38.5 | 90.0 | 54.0 |

## Clause reasoners (hybrid anomaly detector)

| reasoner | decision_agreement_pct | unsafe_straight_through_pct | escalation_recall_pct | straight_through_pct | suggestions | suggestion_accuracy_pct | uncertain_pct | mean_latency_ms | estimated_cost_usd | skipped |
|---|---|---|---|---|---|---|---|---|---|---|
| none | 93.5 | 0.0 | 95.5 | 38.5 | 0 | None | None | 0 | None |  |
| claude:claude-haiku-4-5 |  |  |  |  |  |  |  |  |  | no Anthropic credentials |
| claude:claude-sonnet-5-5 |  |  |  |  |  |  |  |  |  | no Anthropic credentials |
| claude:claude-opus-5-5 |  |  |  |  |  |  |  |  |  | no Anthropic credentials |
| ollama:qwen3:8b |  |  |  |  |  |  |  |  |  | Ollama not reachable on localhost:11434 |
