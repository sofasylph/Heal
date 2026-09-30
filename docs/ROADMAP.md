# Roadmap

v0.1 was a working skeleton. Each milestone below ships with an eval delta, so a feature isn't "done" until the benchmark says what it changed.

## v0.2: LLM clause reasoner (targets the ambiguous-exclusion failures)
- [x] `ClaudeReasoner` for `REVIEW` findings only: full policy wording (prompt-cached) plus claim facts in, schema-constrained verdict / rationale / quotes / confidence out.
- [x] Model, prompt version, input hash, tokens and latency recorded as an `llm_suggested` audit event.
- [x] Suggestions never change amounts and never allow straight-through. Fails closed on any error or refusal.
- [x] Eval metrics (suggestion accuracy, uncertain share, tokens, latency, cost) plus a JSONL response cache for reproducible reruns.
- [x] New "ambiguous but covered" scenario, so the eval penalises an over-eager "applies".
- [ ] **Record the first real run** (`make eval-llm`), commit `docs/eval/llm_cache.jsonl`, and publish the before/after.
- [ ] Effort sweep (low / medium / high) and prompt iteration against the cached eval.
- [ ] Calibrate the 0.80 confidence gate against reviewer overrides.

## v0.3: Switchable models, roles, submission, dashboard
- [x] Settings page with versioned model settings. Every decision records the models used.
- [x] Clause reasoner on Claude Haiku 4.5 / Sonnet 5.5 / Opus 5.5 or a local open-weights model via Ollama, sharing one fail-closed pipeline.
- [x] Document classifier: keyword rules vs TF-IDF + logistic regression (99.8% vs 85.2% on degraded documents).
- [x] Anomaly detector: rules vs Isolation Forest vs hybrid, plus a new padded-pharmacy scenario the rules can't see.
- [x] `make compare`: one report comparing every model option.
- [x] Roles (reviewer / senior reviewer / auditor) enforced by the API; escalated claims need a senior.
- [x] Claim submission in the UI: paste, PDF upload (text layer), synthetic samples with expected outcomes.
- [x] Analytics dashboard: routes, recommendations, deductions by rule, anomalies, reviewer disagreement by rule, models used.
- [ ] Record the Claude and Ollama rows of the model comparison.

## Own open-weights model (planned)
The goal is a small model (1-8B parameters) that answers the clause question on-premises, as well as the hosted models do, at a fraction of the cost.
- [ ] **Training data from the product itself.** Every senior-reviewer decision on an escalated clause is a labelled example, already in the hash-chained audit log (clause, facts, verdict, reason). Build an export plus a de-identification step.
- [ ] Only train on data we have the rights to use: reviewer labels and synthetic cases. Check the terms of any model whose outputs we'd consider using.
- [ ] LoRA fine-tune an open-weights base (e.g. Qwen or Llama family) on that data. Serve it through Ollama or vLLM so it plugs into the existing `ollama` provider unchanged.
- [ ] Benchmark with `make compare` against Claude and the base model: suggestion accuracy, over-eager "applies" rate, latency, cost per claim. Ship only if it's no worse on the safety metrics.
- [ ] Model card: training data provenance, eval results, known failure modes.

## v0.4: Real documents
- [ ] OCR for scanned PDFs and images (the upload already handles PDFs with a text layer).
- [ ] LLM extractor behind the `LLMExtractor` interface, merged with the heuristic extractor. Disagreements become conflicts.
- [ ] Noisy-document benchmark: OCR errors, handwritten claim forms, multi-page bills.

## v0.5: Policy ingestion and retrieval
- [ ] Parse policy wording PDFs into clauses and store embeddings in pgvector.
- [ ] Human-in-the-loop compilation of clauses into rule parameters (the engine never guesses silently).
- [ ] Retrieval metrics: Recall@k for the correct clause.

## v0.6: Production hygiene
- [ ] Authentication: replace the header-based demo identity with real login. The roles and permission checks from v0.3 stay as they are.
- [ ] Alembic migrations, structured JSON logging, request IDs.
- [ ] Async processing queue for ingestion and extraction.
- [ ] Deploy to Render (API + Postgres + web).

## v0.7: Analytics and anomaly
- [x] Reviewer agreement and disagreement-by-rule on the dashboard (v0.3).
- [x] Isolation Forest on bill-shape features (v0.3).
- [ ] Provider-level patterns across historical claims.
- [ ] Turnaround-time metrics per route.

## Interoperability (India)
- [ ] Map `Claim`/`ClaimFacts` to NHCX / FHIR `Claim` and `ClaimResponse` resources.
- [ ] Pre-authorisation (cashless) workflow before final adjudication.

## Product research (runs in parallel with the engineering)
- [ ] 10 workflow interviews with TPA claims staff, hospital billing/insurance desks, insurer claims teams and brokers. The opening prompt is *"Walk me through the last difficult claim you handled"*, not "would you use this?".
- [ ] Map the current cashless and reimbursement workflow: time spent, exceptions, workarounds and highest-risk decisions.
- [ ] 3–5 pilot reviewers run the workbench on the synthetic queue. Measure review time and agreement, and collect "this isn't how it works" feedback.
- [ ] Replace synthetic ground truth with expert-labelled claims.
