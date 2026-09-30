# ClaimTrace evaluation report

Synthetic claims: **200** (see `evaluation/synthetic.py`).

| Metric | Value |
|---|---:|
| decision_agreement_pct | 93.5 |
| false_approval_pct | 6.5 |
| false_rejection_pct | 0.0 |
| unsafe_straight_through_pct | 0.0 |
| straight_through_pct | 53.0 |
| human_review_pct | 47.0 |
| escalation_recall_pct | 100.0 |
| payable_exact_match_pct | 91.6 |
| payable_mae_inr | 714.63 |
| citation_coverage_pct | 100.0 |
| anomaly_recall_pct | 100.0 |
| anomaly_precision_pct | 80.0 |

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
| ambiguous_exclusion | 13 | 0.0 | 0.0 |
| clean | 55 | 100.0 | 100.0 |
| conflicting_dates | 11 | 100.0 | 0.0 |
| cosmetic_excluded | 11 | 100.0 | 0.0 |
| duplicate_line | 12 | 100.0 | 0.0 |
| initial_waiting | 13 | 100.0 | 0.0 |
| missing_document | 8 | 100.0 | 0.0 |
| ped_after_waiting | 16 | 100.0 | 87.5 |
| ped_within_waiting | 10 | 100.0 | 0.0 |
| room_rent_over_cap | 21 | 100.0 | 100.0 |
| senior_copay | 16 | 100.0 | 100.0 |
| specific_waiting | 14 | 100.0 | 0.0 |

## Disagreements (first 25)

| Claim | Scenario | Truth | Predicted | Route |
|---|---|---|---|---|
| CLM-0008 | ambiguous_exclusion | not_payable | pay | escalate |
| CLM-0034 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0067 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0073 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0087 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0123 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0130 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0134 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0140 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0157 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0162 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0168 | ambiguous_exclusion | not_payable | partial | escalate |
| CLM-0179 | ambiguous_exclusion | not_payable | partial | escalate |
