from datetime import date

import pytest
from factories import docs, facts

from claimtrace.decision.engine import decide
from claimtrace.domain.models import (
    BillCategory,
    BillLineItem,
    DocumentType,
    FindingOutcome,
    Recommendation,
    ReviewRoute,
)
from claimtrace.policies.registry import get_policy
from claimtrace.rules.engine import months_between, run_rules

SILVER = get_policy("SURAKSHA-SILVER")
GOLD = get_policy("CAREFIRST-GOLD")


def outcomes(result, rule_id):
    return [f.outcome for f in result.findings if f.rule_id == rule_id]


def test_clean_claim_is_payable_in_full_and_auto_candidate():
    d = decide(SILVER, facts(), docs())
    assert d.recommendation is Recommendation.PAY
    assert d.payable_amount == 75000
    assert d.route is ReviewRoute.AUTO_CANDIDATE


def test_room_rent_over_cap_applies_proportionate_deduction():
    f = facts()
    f.line_items[0].amount = 22500  # 7,500/day vs 5,000 cap
    f.claimed_amount = f.bill_total
    r = run_rules(SILVER, f, docs())
    # room 15,000 + OT 20,000 + surgeon 13,333.33 + pharmacy 10,000 (exempt)
    assert r.payable_amount == pytest.approx(58333.33, abs=0.01)
    room = [x for x in r.findings if x.rule_id == "ROOM-001"]
    assert all(x.clause and x.clause.clause_id == "4.2" for x in room)


def test_no_room_cap_on_gold_but_deductible_applies():
    f = facts()
    f.line_items[0].amount = 45000
    f.claimed_amount = f.bill_total
    r = run_rules(GOLD, f, docs())
    assert r.payable_amount == f.bill_total - 25000


def test_consumables_are_non_payable():
    f = facts()
    f.line_items.append(
        BillLineItem(
            line_id="L5",
            description="Surgical Consumables",
            category=BillCategory.CONSUMABLES,
            amount=2345,
        )
    )
    f.claimed_amount = f.bill_total
    d = decide(SILVER, f, docs())
    assert d.recommendation is Recommendation.PARTIAL
    assert d.payable_amount == 75000


def test_senior_copay():
    r = run_rules(SILVER, facts(patient_age=66), docs())
    assert r.payable_amount == 67500
    assert FindingOutcome.ADJUST in outcomes(r, "COPAY-001")


def test_ped_within_waiting_period_denied():
    f = facts(
        diagnosis="Diabetic foot ulcer",
        procedure="Debridement",
        pre_existing_conditions=["Type 2 Diabetes Mellitus"],
        policy_start_date=date(2024, 6, 1),
    )
    d = decide(SILVER, f, docs())
    assert d.recommendation is Recommendation.NOT_PAYABLE
    assert d.payable_amount == 0
    assert d.route is not ReviewRoute.AUTO_CANDIDATE  # denials always get a human


def test_ped_after_waiting_period_passes():
    f = facts(
        diagnosis="Diabetic foot ulcer",
        pre_existing_conditions=["Diabetes"],
        policy_start_date=date(2020, 1, 1),
    )
    r = run_rules(SILVER, f, docs())
    assert outcomes(r, "PED-001") == [FindingOutcome.PASS]


def test_specific_waiting_period_denies_hernia():
    f = facts(
        diagnosis="Inguinal hernia", procedure="Hernioplasty", policy_start_date=date(2024, 9, 1)
    )
    assert decide(SILVER, f, docs()).recommendation is Recommendation.NOT_PAYABLE


def test_initial_waiting_period():
    f = facts(policy_start_date=date(2025, 3, 1))
    r = run_rules(SILVER, f, docs())
    assert outcomes(r, "WAIT-001") == [FindingOutcome.DENY]


def test_cosmetic_exact_match_denied():
    f = facts(diagnosis="Nasal deformity", procedure="Cosmetic rhinoplasty")
    assert decide(SILVER, f, docs()).recommendation is Recommendation.NOT_PAYABLE


def test_ambiguous_exclusion_escalates_rather_than_deciding():
    f = facts(diagnosis="Nasal hump", procedure="Aesthetic nasal reshaping")
    d = decide(SILVER, f, docs())
    assert d.route is ReviewRoute.ESCALATE
    review = [x for x in d.findings if x.outcome is FindingOutcome.REVIEW]
    assert review and not review[0].deterministic


def test_cataract_sublimit():
    f = facts(
        diagnosis="Senile cataract",
        procedure="Phacoemulsification",
        policy_start_date=date(2020, 1, 1),
    )
    r = run_rules(SILVER, f, docs())
    assert r.payable_amount == 40000


def test_missing_document_needs_info():
    d = decide(SILVER, facts(), docs(DocumentType.CLAIM_FORM, DocumentType.INVOICE))
    assert d.recommendation is Recommendation.NEEDS_INFO


def test_low_confidence_field_escalates():
    f = facts()
    f.field_confidence["admission_date"] = 0.5
    f.conflicts["admission_date"] = ["2025-03-08", "2025-03-10"]
    assert decide(SILVER, f, docs()).route is ReviewRoute.ESCALATE


def test_every_adjustment_and_denial_cites_a_clause():
    f = facts(patient_age=70)
    f.line_items[0].amount = 30000
    f.claimed_amount = f.bill_total
    for x in run_rules(SILVER, f, docs()).findings:
        if x.outcome in (FindingOutcome.ADJUST, FindingOutcome.DENY):
            assert x.clause is not None


@pytest.mark.parametrize(
    "start,end,expected",
    [
        (date(2020, 1, 15), date(2023, 1, 14), 35),
        (date(2020, 1, 15), date(2023, 1, 15), 36),
        (date(2024, 2, 29), date(2024, 3, 28), 0),
    ],
)
def test_months_between(start, end, expected):
    assert months_between(start, end) == expected
