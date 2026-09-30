"""Seeds a demo queue covering each scenario type. Idempotent."""

from __future__ import annotations

import random

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from claimtrace.claims import service
from claimtrace.db.session import ClaimRow
from claimtrace.domain.models import Recommendation
from claimtrace.evaluation.synthetic import Scenario, generate_claim
from claimtrace.policies.registry import get_policy

DEMO = [
    (Scenario.CLEAN, "SURAKSHA-SILVER"),
    (Scenario.ROOM_RENT_OVER_CAP, "SURAKSHA-SILVER"),
    (Scenario.SENIOR_COPAY, "SURAKSHA-SILVER"),
    (Scenario.PED_WITHIN_WAITING, "SURAKSHA-SILVER"),
    (Scenario.AMBIGUOUS_EXCLUSION, "SURAKSHA-SILVER"),
    (Scenario.CONFLICTING_DATES, "CAREFIRST-GOLD"),
    (Scenario.DUPLICATE_LINE, "SURAKSHA-SILVER"),
    (Scenario.CLEAN, "CAREFIRST-GOLD"),
    (Scenario.SPECIFIC_WAITING, "CAREFIRST-GOLD"),
    (Scenario.MISSING_DOCUMENT, "SURAKSHA-SILVER"),
    (Scenario.COSMETIC_EXCLUDED, "CAREFIRST-GOLD"),
    (Scenario.ROOM_RENT_OVER_CAP, "SURAKSHA-SILVER"),
    (Scenario.PED_AFTER_WAITING, "CAREFIRST-GOLD"),
    (Scenario.INITIAL_WAITING, "SURAKSHA-SILVER"),
]


def seed_demo_data(session: Session, seed: int = 2181) -> int:
    if session.scalar(select(func.count()).select_from(ClaimRow)):
        return 0
    rng = random.Random(seed)
    for i, (scenario, policy_id) in enumerate(DEMO):
        sc = generate_claim(rng, 2181 + i, scenario, get_policy(policy_id))
        service.create_claim(session, policy_id, sc.documents, claim_id=sc.claim_id)
        claim = service.adjudicate(session, sc.claim_id)
        if scenario is Scenario.AMBIGUOUS_EXCLUSION:
            service.override(
                session,
                claim.claim_id,
                "a.reviewer",
                Recommendation.NOT_PAYABLE,
                0.0,
                "Procedure is aesthetic in nature with no functional "
                "indication; excluded under clause 6.1.",
            )
    return len(DEMO)
