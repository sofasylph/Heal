"""Application service: orchestrates ingestion, extraction, adjudication and overrides,
writing an audit event at every step."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from claimtrace.audit.log import AuditAction, record
from claimtrace.db.session import ClaimRow
from claimtrace.decision.engine import decide
from claimtrace.domain.models import Claim, ClaimStatus, Recommendation, ReviewerOverride
from claimtrace.extraction.pipeline import RawDocument, extract, ingest_documents
from claimtrace.policies.registry import get_policy

SYSTEM = "system:claimtrace"


class NotFoundError(Exception):
    pass


def _save(session: Session, claim: Claim) -> None:
    row = session.get(ClaimRow, claim.claim_id)
    now = datetime.now(UTC)
    if row is None:
        row = ClaimRow(claim_id=claim.claim_id, created_at=claim.created_at)
        session.add(row)
    row.policy_id = claim.policy_id
    row.status = claim.status.value
    row.patient_name = claim.facts.patient_name if claim.facts else None
    row.diagnosis = claim.facts.diagnosis if claim.facts else None
    row.claimed_amount = claim.facts.claimed_amount if claim.facts else None
    final = claim.override or claim.decision
    row.recommendation = final.recommendation.value if final else None
    row.payable_amount = final.payable_amount if final else None
    row.route = claim.decision.route.value if claim.decision else None
    row.confidence = claim.decision.confidence if claim.decision else None
    row.risk_score = claim.decision.risk_score if claim.decision else None
    row.data = claim.model_dump(mode="json")
    row.updated_at = now


def get_claim(session: Session, claim_id: str) -> Claim:
    row = session.get(ClaimRow, claim_id)
    if row is None:
        raise NotFoundError(claim_id)
    return Claim.model_validate(row.data)


def list_claims(session: Session) -> list[ClaimRow]:
    return list(session.scalars(select(ClaimRow).order_by(ClaimRow.created_at.desc())).all())


def create_claim(
    session: Session, policy_id: str, raw_docs: list[RawDocument], claim_id: str | None = None
) -> Claim:
    get_policy(policy_id)  # validate
    docs = ingest_documents(raw_docs)
    claim = Claim(
        claim_id=claim_id or f"CLM-{uuid.uuid4().hex[:6].upper()}",
        policy_id=policy_id,
        documents=docs,
        created_at=datetime.now(UTC),
    )
    _save(session, claim)
    record(
        session,
        claim.claim_id,
        SYSTEM,
        AuditAction.DOCUMENTS_INGESTED,
        {
            "documents": [
                {
                    "doc_id": d.doc_id,
                    "filename": d.filename,
                    "doc_type": d.doc_type,
                    "classification_confidence": d.classification_confidence,
                    "sha256": d.sha256,
                }
                for d in docs
            ],
        },
    )

    claim.facts = extract(docs)
    claim.status = ClaimStatus.EXTRACTED
    _save(session, claim)
    record(
        session,
        claim.claim_id,
        SYSTEM,
        AuditAction.FACTS_EXTRACTED,
        {
            "extractor": "heuristic-v1",
            "facts": claim.facts.model_dump(mode="json"),
        },
    )
    session.commit()
    return claim


def adjudicate(session: Session, claim_id: str) -> Claim:
    claim = get_claim(session, claim_id)
    policy = get_policy(claim.policy_id)
    if claim.facts is None:
        claim.facts = extract(claim.documents)
    decision = decide(policy, claim.facts, claim.documents)
    record(
        session,
        claim_id,
        SYSTEM,
        AuditAction.RULES_EVALUATED,
        {
            "policy_version": decision.policy_version,
            "engine_version": decision.engine_version,
            "findings": [f.model_dump(mode="json") for f in decision.findings],
            "anomalies": [a.model_dump(mode="json") for a in decision.anomalies],
        },
    )
    record(
        session,
        claim_id,
        SYSTEM,
        AuditAction.DECISION_RECOMMENDED,
        {
            "recommendation": decision.recommendation,
            "route": decision.route,
            "claimed_amount": decision.claimed_amount,
            "payable_amount": decision.payable_amount,
            "confidence": decision.confidence,
            "risk_score": decision.risk_score,
            "llm_used": False,
        },
    )
    claim.decision = decision
    claim.override = None
    claim.status = ClaimStatus.RECOMMENDED
    _save(session, claim)
    session.commit()
    return claim


def override(
    session: Session,
    claim_id: str,
    reviewer: str,
    recommendation: Recommendation,
    payable_amount: float,
    reason: str,
) -> Claim:
    claim = get_claim(session, claim_id)
    if claim.decision is None:
        raise ValueError("Claim must be adjudicated before a reviewer decision is recorded")
    claim.override = ReviewerOverride(
        reviewer=reviewer,
        recommendation=recommendation,
        payable_amount=payable_amount,
        reason=reason,
        overridden_at=datetime.now(UTC),
    )
    claim.status = ClaimStatus.FINALISED
    record(
        session,
        claim_id,
        f"reviewer:{reviewer}",
        AuditAction.HUMAN_OVERRIDE,
        {
            "system_recommendation": claim.decision.recommendation,
            "system_payable": claim.decision.payable_amount,
            "final_recommendation": recommendation,
            "final_payable": payable_amount,
            "agrees_with_system": (
                recommendation == claim.decision.recommendation
                and abs(payable_amount - claim.decision.payable_amount) < 1
            ),
            "reason": reason,
        },
    )
    _save(session, claim)
    session.commit()
    return claim
