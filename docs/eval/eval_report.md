# ClaimTrace evaluation report

Synthetic claims: **200** (see `evaluation/synthetic.py`).

| Metric | Value |
|---|---:|
| decision_agreement_pct | 95.0 |
| false_approval_pct | 5.0 |
| false_rejection_pct | 0.0 |
| unsafe_straight_through_pct | 0.0 |
| straight_through_pct | 51.0 |
| human_review_pct | 49.0 |
| escalation_recall_pct | 100.0 |
| payable_exact_match_pct | 91.7 |
| payable_mae_inr | 1063.64 |
| citation_coverage_pct | 100.0 |
| anomaly_recall_pct | 100.0 |
| anomaly_precision_pct | 73.3 |

## Clause reasoner

| Metric | Value |
|---|---:|
| reasoner | none |
| models | [] |
| eligible_findings | 18 |
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
| ambiguous_covered | 8 | 100.0 | 0.0 |
| ambiguous_exclusion | 10 | 0.0 | 0.0 |
| clean | 53 | 100.0 | 100.0 |
| conflicting_dates | 9 | 100.0 | 0.0 |
| cosmetic_excluded | 9 | 100.0 | 0.0 |
| duplicate_line | 11 | 100.0 | 0.0 |
| initial_waiting | 14 | 100.0 | 0.0 |
| missing_document | 11 | 100.0 | 0.0 |
| ped_after_waiting | 12 | 100.0 | 91.7 |
| ped_within_waiting | 10 | 100.0 | 0.0 |
| room_rent_over_cap | 22 | 100.0 | 95.5 |
| senior_copay | 17 | 100.0 | 100.0 |
| specific_waiting | 14 | 100.0 | 0.0 |

## Disagreements (first 25)

| Claim | Scenario | Truth | Predicted | Route |
|---|---|---|---|---|
| CLM-0040 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0048 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0066 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0072 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0075 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0099 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0104 | ambiguous_exclusion | not_payable | pay | escalate |
| CLM-0138 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0149 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0192 | ambiguous_exclusion | not_payable | partial | escalate |
