"""Policy representation: human-readable clauses plus machine-executable rule parameters.

Every rule parameter carries a `clause_id` so any decision can be traced back to the
exact wording (and page) of the policy document it was derived from.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from claimtrace.domain.models import BillCategory, ClauseRef, DocumentType


class Clause(BaseModel):
    clause_id: str
    title: str
    page: int
    text: str


class ConditionRule(BaseModel):
    """A named condition matched against diagnosis/procedure text.

    `keywords` are unambiguous matches (rule applies deterministically).
    `related_terms` are signals that the rule *might* apply; they route the claim to a
    human (and, later, to an LLM reasoner) instead of silently passing or failing.
    """

    name: str
    keywords: list[str]
    related_terms: list[str] = Field(default_factory=list)
    clause_id: str


class WaitingPeriodRule(ConditionRule):
    months: int


class SublimitRule(ConditionRule):
    max_amount: float


class PolicyRules(BaseModel):
    sum_insured: float
    sum_insured_clause: str

    room_rent_cap_per_day: float | None = None
    icu_cap_per_day: float | None = None
    room_rent_clause: str | None = None
    proportionate_deduction_categories: list[BillCategory] = Field(default_factory=list)

    initial_waiting_days: int = 30
    initial_waiting_clause: str
    ped_waiting_months: int = 36
    ped_clause: str
    specific_waiting_periods: list[WaitingPeriodRule] = Field(default_factory=list)

    sublimits: list[SublimitRule] = Field(default_factory=list)
    exclusions: list[ConditionRule] = Field(default_factory=list)

    non_payable_categories: list[BillCategory] = Field(default_factory=list)
    non_payable_keywords: list[str] = Field(default_factory=list)
    non_payable_clause: str | None = None

    deductible: float = 0.0
    deductible_clause: str | None = None
    copay_percent: float = 0.0
    copay_min_age: int | None = None
    copay_clause: str | None = None

    required_documents: list[DocumentType] = Field(default_factory=list)
    required_documents_clause: str


class Policy(BaseModel):
    policy_id: str
    version: str
    name: str
    insurer: str
    description: str
    clauses: list[Clause]
    rules: PolicyRules

    def clause_ref(self, clause_id: str | None) -> ClauseRef | None:
        if clause_id is None:
            return None
        for c in self.clauses:
            if c.clause_id == clause_id:
                return ClauseRef(
                    policy_id=self.policy_id,
                    clause_id=c.clause_id,
                    title=c.title,
                    page=c.page,
                    excerpt=c.text,
                )
        raise KeyError(f"Policy {self.policy_id} has no clause {clause_id}")

    def validate_clause_links(self) -> None:
        """Fail fast if any rule points at a clause that does not exist."""
        r = self.rules
        ids = [
            r.sum_insured_clause,
            r.room_rent_clause,
            r.initial_waiting_clause,
            r.ped_clause,
            r.non_payable_clause,
            r.deductible_clause,
            r.copay_clause,
            r.required_documents_clause,
            *[w.clause_id for w in r.specific_waiting_periods],
            *[s.clause_id for s in r.sublimits],
            *[e.clause_id for e in r.exclusions],
        ]
        for cid in ids:
            self.clause_ref(cid)
