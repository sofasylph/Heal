"""Core domain models shared by extraction, rules, decisioning and the API."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


class DocumentType(StrEnum):
    POLICY = "policy"
    CLAIM_FORM = "claim_form"
    DISCHARGE_SUMMARY = "discharge_summary"
    INVOICE = "invoice"
    DIAGNOSTIC_REPORT = "diagnostic_report"
    PRESCRIPTION = "prescription"
    PRE_AUTH = "pre_auth"
    UNKNOWN = "unknown"


class ClaimDocument(BaseModel):
    doc_id: str
    filename: str
    text: str
    doc_type: DocumentType = DocumentType.UNKNOWN
    classification_confidence: float = 0.0
    sha256: str = ""


# ---------------------------------------------------------------------------
# Extracted claim facts
# ---------------------------------------------------------------------------


class BillCategory(StrEnum):
    ROOM = "room"
    ICU = "icu"
    PROCEDURE = "procedure"
    SURGEON_FEE = "surgeon_fee"
    NURSING = "nursing"
    MEDICINES = "medicines"
    CONSUMABLES = "consumables"
    DIAGNOSTICS = "diagnostics"
    IMPLANTS = "implants"
    OTHER = "other"


class BillLineItem(BaseModel):
    line_id: str
    description: str
    category: BillCategory
    amount: float
    days: int | None = None


class ClaimFacts(BaseModel):
    """Structured facts extracted from claim documents.

    `field_confidence` maps a field name to the extractor's confidence (0-1) and
    `field_source` maps it to the doc_id it came from, so every fact is traceable.
    """

    patient_name: str | None = None
    patient_age: int | None = None
    policy_number: str | None = None
    policy_start_date: date | None = None
    hospital: str | None = None
    diagnosis: str | None = None
    procedure: str | None = None
    admission_date: date | None = None
    discharge_date: date | None = None
    room_type: str | None = None
    room_rent_per_day: float | None = None
    pre_existing_conditions: list[str] = Field(default_factory=list)
    line_items: list[BillLineItem] = Field(default_factory=list)
    claimed_amount: float | None = None
    field_confidence: dict[str, float] = Field(default_factory=dict)
    field_source: dict[str, str] = Field(default_factory=dict)
    conflicts: dict[str, list[str]] = Field(default_factory=dict)

    @property
    def length_of_stay(self) -> int | None:
        if self.admission_date and self.discharge_date:
            return max((self.discharge_date - self.admission_date).days, 1)
        return None

    @property
    def bill_total(self) -> float:
        return round(sum(li.amount for li in self.line_items), 2)


# ---------------------------------------------------------------------------
# Rule findings and decisions
# ---------------------------------------------------------------------------


class ClauseRef(BaseModel):
    policy_id: str
    clause_id: str
    title: str
    page: int
    excerpt: str


class FindingOutcome(StrEnum):
    PASS = "pass"  # check satisfied, no impact
    ADJUST = "adjust"  # payable reduced
    DENY = "deny"  # claim not payable under this rule
    NEEDS_INFO = "needs_info"  # required information missing
    REVIEW = "review"  # rule could not be resolved deterministically


class Finding(BaseModel):
    rule_id: str
    rule_version: str
    title: str
    outcome: FindingOutcome
    message: str
    clause: ClauseRef | None = None
    amount_impact: float = 0.0  # negative = deduction from payable
    confidence: float = 1.0
    deterministic: bool = True
    evidence: dict[str, object] = Field(default_factory=dict)


class Recommendation(StrEnum):
    PAY = "pay"
    PARTIAL = "partial"
    NOT_PAYABLE = "not_payable"
    NEEDS_INFO = "needs_info"


class ReviewRoute(StrEnum):
    AUTO_CANDIDATE = "auto_candidate"  # high confidence, deterministic, low risk
    HUMAN_VERIFY = "human_verify"  # a reviewer should confirm
    ESCALATE = "escalate"  # conflicting / low-confidence evidence


class AnomalyFlag(BaseModel):
    code: str
    severity: float  # 0-1
    message: str
    evidence: dict[str, object] = Field(default_factory=dict)


class PayableLine(BaseModel):
    line_id: str
    description: str
    category: BillCategory
    claimed: float
    payable: float
    notes: list[str] = Field(default_factory=list)


class Decision(BaseModel):
    recommendation: Recommendation
    route: ReviewRoute
    claimed_amount: float
    payable_amount: float
    confidence: float
    risk_score: float
    findings: list[Finding]
    anomalies: list[AnomalyFlag]
    payable_lines: list[PayableLine]
    summary: str
    engine_version: str
    policy_version: str
    decided_at: datetime


class ReviewerOverride(BaseModel):
    reviewer: str
    recommendation: Recommendation
    payable_amount: float
    reason: str
    overridden_at: datetime


class ClaimStatus(StrEnum):
    RECEIVED = "received"
    EXTRACTED = "extracted"
    RECOMMENDED = "recommended"
    FINALISED = "finalised"


class Claim(BaseModel):
    claim_id: str
    policy_id: str
    status: ClaimStatus = ClaimStatus.RECEIVED
    documents: list[ClaimDocument] = Field(default_factory=list)
    facts: ClaimFacts | None = None
    decision: Decision | None = None
    override: ReviewerOverride | None = None
    created_at: datetime
