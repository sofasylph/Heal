# Roadmap

v0.1 is a working skeleton. Each milestone below ships with an eval delta, so a feature isn't "done" until the benchmark says what it changed.

## v0.2: LLM clause reasoner (targets the ambiguous-exclusion failures)
- [ ] Implement `ClauseReasoner` (Claude API) for `REVIEW` findings only. Inputs: the clause text, diagnosis/procedure, and the matched term. Output: a schema-validated suggestion with rationale.
- [ ] Record model, prompt version, input hash and raw response in the audit log.
- [ ] The reasoner can only change routing or add a *suggested* outcome. It can never override a deterministic DENY/ADJUST.
- [ ] New eval metrics: suggestion accuracy on ambiguous cases, unsupported-claim rate, cost and latency per claim.

## v0.3: Real documents
- [ ] PDF/image ingestion (pdfplumber + OCR fallback).
- [ ] LLM extractor behind the `LLMExtractor` interface, merged with the heuristic extractor. Disagreements become conflicts.
- [ ] Noisy-document benchmark: OCR errors, handwritten claim forms, multi-page bills.

## v0.4: Policy ingestion and retrieval
- [ ] Parse policy wording PDFs into clauses and store embeddings in pgvector.
- [ ] Human-in-the-loop compilation of clauses into rule parameters (the engine never guesses silently).
- [ ] Retrieval metrics: Recall@k for the correct clause.

## v0.5: Production hygiene
- [ ] Auth + RBAC (reviewer, senior reviewer, auditor), with the reviewer identity taken from auth rather than the form.
- [ ] Alembic migrations, structured JSON logging, request IDs.
- [ ] Async processing queue for ingestion and extraction.
- [ ] Deploy to Render (API + Postgres + web).

## v0.6: Analytics and anomaly
- [ ] Reviewer agreement and override analytics per rule (which rules do humans disagree with?).
- [ ] Isolation Forest / provider-level patterns on historical claims.
- [ ] Turnaround-time metrics per route.

## Interoperability (India)
- [ ] Map `Claim`/`ClaimFacts` to NHCX / FHIR `Claim` and `ClaimResponse` resources.
- [ ] Pre-authorisation (cashless) workflow before final adjudication.

## Product research (runs in parallel with the engineering)
- [ ] 10 workflow interviews with TPA claims staff, hospital billing/insurance desks, insurer claims teams and brokers. The opening prompt is *"Walk me through the last difficult claim you handled"*, not "would you use this?".
- [ ] Map the current cashless and reimbursement workflow: time spent, exceptions, workarounds and highest-risk decisions.
- [ ] 3–5 pilot reviewers run the workbench on the synthetic queue. Measure review time and agreement, and collect "this isn't how it works" feedback.
- [ ] Replace synthetic ground truth with expert-labelled claims.
