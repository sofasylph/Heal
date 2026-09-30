# ClaimTrace evaluation report

Synthetic claims: **200** (see `evaluation/synthetic.py`).
Components: `{'doc_classifier': 'tfidf_logreg', 'anomaly_detector': 'hybrid'}`

| Metric | Value |
|---|---:|
| decision_agreement_pct | 93.5 |
| false_approval_pct | 6.5 |
| false_rejection_pct | 0.0 |
| unsafe_straight_through_pct | 0.0 |
| straight_through_pct | 38.5 |
| human_review_pct | 61.5 |
| escalation_recall_pct | 95.5 |
| payable_exact_match_pct | 91.8 |
| payable_mae_inr | 733.18 |
| citation_coverage_pct | 100.0 |
| anomaly_recall_pct | 90.0 |
| anomaly_precision_pct | 54.0 |

## Clause reasoner

| Metric | Value |
|---|---:|
| reasoner | none |
| models | [] |
| eligible_findings | 25 |
| suggestions | 0 |
| suggestion_accuracy_pct | None |
| uncertain_pct | None |
| ai_assisted_claims | 0 |
| replayed_from_cache | 0 |
| input_tokens | 0 |
| cache_read_input_tokens | 0 |
| output_tokens | 0 |
| mean_latency_ms | 0 |
| estimated_cost_usd | None |

## Extraction field accuracy (%)

| Field | Accuracy |
|---|---:|
| patient_name | 100.0 |
| patient_age | 100.0 |
| policy_start_date | 100.0 |
| admission_date | 100.0 |
| discharge_date | 100.0 |
| diagnosis | 100.0 |
| procedure | 100.0 |
| claimed_amount | 100.0 |

## By scenario

| Scenario | n | Agreement % | Straight-through % |
|---|---:|---:|---:|
| ambiguous_covered | 12 | 100.0 | 0.0 |
| ambiguous_exclusion | 13 | 0.0 | 0.0 |
| clean | 41 | 100.0 | 97.6 |
| conflicting_dates | 12 | 100.0 | 0.0 |
| cosmetic_excluded | 14 | 100.0 | 0.0 |
| duplicate_line | 14 | 100.0 | 0.0 |
| initial_waiting | 10 | 100.0 | 0.0 |
| missing_document | 11 | 100.0 | 0.0 |
| padded_pharmacy | 16 | 100.0 | 18.8 |
| ped_after_waiting | 11 | 100.0 | 90.9 |
| ped_within_waiting | 6 | 100.0 | 0.0 |
| room_rent_over_cap | 16 | 100.0 | 81.2 |
| senior_copay | 12 | 100.0 | 91.7 |
| specific_waiting | 12 | 100.0 | 0.0 |

## Disagreements (first 25)

| Claim | Scenario | Truth | Predicted | Route |
|---|---|---|---|---|
| CLM-0020 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0027 | ambiguous_exclusion | not_payable | pay | escalate |
| CLM-0033 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0087 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0088 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0106 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0107 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0113 | ambiguous_exclusion | not_payable | pay | escalate |
| CLM-0145 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0164 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0166 | ambiguous_exclusion | not_payable | pay | escalate |
| CLM-0181 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0186 | ambiguous_exclusion | not_payable | partial | escalate |
