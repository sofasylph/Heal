"""API request/response schemas (kept separate from domain models)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from claimtrace.audit.log import AuditEvent
from claimtrace.domain.models import Recommendation
from claimtrace.extraction.pipeline import RawDocument


class CreateClaimRequest(BaseModel):
    policy_id: str
    documents: list[RawDocument] = Field(min_length=1)
    adjudicate: bool = True


class OverrideRequest(BaseModel):
    """The reviewer's identity comes from the caller (X-User / X-Role), not the body."""

    recommendation: Recommendation
    payable_amount: float = Field(ge=0)
    reason: str = Field(min_length=3, max_length=2000)


class ClaimSummary(BaseModel):
    claim_id: str
    policy_id: str
    status: str
    patient_name: str | None
    diagnosis: str | None
    claimed_amount: float | None
    payable_amount: float | None
    recommendation: str | None
    route: str | None
    confidence: float | None
    risk_score: float | None
    created_at: datetime


class AuditTrail(BaseModel):
    claim_id: str
    chain_valid: bool
    events: list[AuditEvent]


class PolicySummary(BaseModel):
    policy_id: str
    version: str
    name: str
    insurer: str
    description: str
    sum_insured: float


class ExtractedDocument(BaseModel):
    filename: str
    text: str
    doc_type: str
    classification_confidence: float
    pages: int | None = None
    warning: str | None = None


class SampleClaim(BaseModel):
    scenario: str
    description: str
    policy_id: str
    documents: list[RawDocument]
    expected_recommendation: str
    expected_payable: float


class Me(BaseModel):
    user: str
    role: str
    permissions: list[str]
