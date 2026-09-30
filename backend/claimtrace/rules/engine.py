"""Deterministic policy rules engine.

Rules run in a fixed, documented order. Eligibility rules emit findings only; payable
rules also mutate the payable ledger (line level) or the running subtotal (claim level).
Every finding records the rule id + version, the clause it enforces, the evidence it
used and a confidence derived from the extraction confidence of those inputs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from claimtrace.domain.models import (
    BillCategory,
    ClaimDocument,
    ClaimFacts,
    Finding,
    FindingOutcome,
    PayableLine,
)
from claimtrace.policies.models import Policy
from claimtrace.rules.matching import MatchKind, match_condition, stem_overlap

CRITICAL_FIELDS = [
    "diagnosis",
    "admission_date",
    "discharge_date",
    "policy_start_date",
    "claimed_amount",
]
LOW_CONFIDENCE = 0.7


@dataclass
class RuleContext:
    policy: Policy
    facts: ClaimFacts
    documents: list[ClaimDocument]
    ledger: dict[str, PayableLine] = field(default_factory=dict)
    subtotal: float = 0.0

    def conf(self, *fields: str) -> float:
        return min((self.facts.field_confidence.get(f, 1.0) for f in fields), default=1.0)

    def clinical_text(self) -> dict[str, str | None]:
        return {"diagnosis": self.facts.diagnosis, "procedure": self.facts.procedure}


@dataclass(frozen=True)
class Rule:
    rule_id: str
    version: str
    title: str
    fn: Callable[[RuleContext, Rule], list[Finding]]

    def evaluate(self, ctx: RuleContext) -> list[Finding]:
        return self.fn(ctx, self)


def _finding(
    rule: Rule,
    ctx: RuleContext,
    outcome: FindingOutcome,
    message: str,
    clause_id: str | None = None,
    **kw: object,
) -> Finding:
    return Finding(
        rule_id=rule.rule_id,
        rule_version=rule.version,
        title=rule.title,
        outcome=outcome,
        message=message,
        clause=ctx.policy.clause_ref(clause_id),
        **kw,
    )


def months_between(start, end) -> int:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        months -= 1
    return months


# ---------------------------------------------------------------------------
# Eligibility rules
# ---------------------------------------------------------------------------


def required_documents(ctx: RuleContext, rule: Rule) -> list[Finding]:
    present = {d.doc_type for d in ctx.documents}
    missing = [d for d in ctx.policy.rules.required_documents if d not in present]
    clause = ctx.policy.rules.required_documents_clause
    if missing:
        names = ", ".join(m.value.replace("_", " ") for m in missing)
        return [
            _finding(
                rule,
                ctx,
                FindingOutcome.NEEDS_INFO,
                f"Missing required documents: {names}.",
                clause,
                evidence={"missing": [m.value for m in missing]},
            )
        ]
    return [_finding(rule, ctx, FindingOutcome.PASS, "All required documents present.", clause)]


def required_fields(ctx: RuleContext, rule: Rule) -> list[Finding]:
    f = ctx.facts
    missing = [name for name in CRITICAL_FIELDS if getattr(f, name) in (None, "")]
    if not f.line_items:
        missing.append("line_items")
    if missing:
        return [
            _finding(
                rule,
                ctx,
                FindingOutcome.NEEDS_INFO,
                f"Could not extract required fields: {', '.join(missing)}.",
                evidence={"missing_fields": missing},
            )
        ]
    weak = {
        k: v for k, v in f.field_confidence.items() if k in CRITICAL_FIELDS and v < LOW_CONFIDENCE
    }
    if weak or f.conflicts:
        detail = "; ".join(f"{k}: {', '.join(v)}" for k, v in f.conflicts.items())
        fields = ", ".join(sorted(weak or f.conflicts))
        msg = f"Low-confidence or conflicting extraction for {fields}"
        if detail:
            msg += f" (values seen: {detail})"
        return [
            _finding(
                rule,
                ctx,
                FindingOutcome.REVIEW,
                msg + ".",
                confidence=min(weak.values(), default=0.5),
                deterministic=False,
                evidence={"field_confidence": weak, "conflicts": f.conflicts},
            )
        ]
    return [
        _finding(
            rule,
            ctx,
            FindingOutcome.PASS,
            "All critical fields extracted.",
            confidence=ctx.conf(*CRITICAL_FIELDS),
        )
    ]


def initial_waiting(ctx: RuleContext, rule: Rule) -> list[Finding]:
    f, r = ctx.facts, ctx.policy.rules
    if not (f.policy_start_date and f.admission_date):
        return []
    days = (f.admission_date - f.policy_start_date).days
    conf = ctx.conf("policy_start_date", "admission_date")
    ev = {
        "policy_start_date": str(f.policy_start_date),
        "admission_date": str(f.admission_date),
        "days_since_inception": days,
        "required_days": r.initial_waiting_days,
    }
    if days < 0:
        return [
            _finding(
                rule,
                ctx,
                FindingOutcome.DENY,
                "Admission precedes policy inception.",
                r.initial_waiting_clause,
                confidence=conf,
                evidence=ev,
            )
        ]
    if days < r.initial_waiting_days:
        return [
            _finding(
                rule,
                ctx,
                FindingOutcome.DENY,
                f"Admission {days} days after inception; initial waiting period is "
                f"{r.initial_waiting_days} days.",
                r.initial_waiting_clause,
                confidence=conf,
                evidence=ev,
            )
        ]
    return [
        _finding(
            rule,
            ctx,
            FindingOutcome.PASS,
            f"Initial waiting period satisfied ({days} days since inception).",
            r.initial_waiting_clause,
            confidence=conf,
            evidence=ev,
        )
    ]


def pre_existing(ctx: RuleContext, rule: Rule) -> list[Finding]:
    f, r = ctx.facts, ctx.policy.rules
    if not (f.policy_start_date and f.admission_date):
        return []
    tenure = months_between(f.policy_start_date, f.admission_date)
    related = [
        c
        for c in f.pre_existing_conditions
        if stem_overlap(c, f.diagnosis) or stem_overlap(c, f.procedure)
    ]
    ev = {
        "declared_ped": f.pre_existing_conditions,
        "related_ped": related,
        "tenure_months": tenure,
        "required_months": r.ped_waiting_months,
    }
    conf = ctx.conf("policy_start_date", "admission_date", "diagnosis")
    if not related:
        return [
            _finding(
                rule,
                ctx,
                FindingOutcome.PASS,
                "Diagnosis not related to any declared pre-existing disease.",
                r.ped_clause,
                confidence=min(conf, 0.95),
                evidence=ev,
            )
        ]
    if tenure < r.ped_waiting_months:
        exact = any(c.lower() in (f.diagnosis or "").lower() for c in related)
        return [
            _finding(
                rule,
                ctx,
                FindingOutcome.DENY,
                f"Diagnosis relates to declared PED ({', '.join(related)}); tenure "
                f"{tenure} months is within the {r.ped_waiting_months}-month PED "
                "waiting period.",
                r.ped_clause,
                confidence=min(conf, 0.97 if exact else 0.85),
                evidence=ev,
            )
        ]
    return [
        _finding(
            rule,
            ctx,
            FindingOutcome.PASS,
            f"Related to PED ({', '.join(related)}) but PED waiting period completed "
            f"({tenure} months).",
            r.ped_clause,
            confidence=conf,
            evidence=ev,
        )
    ]


def specific_waiting(ctx: RuleContext, rule: Rule) -> list[Finding]:
    f = ctx.facts
    if not (f.policy_start_date and f.admission_date):
        return []
    tenure = months_between(f.policy_start_date, f.admission_date)
    out: list[Finding] = []
    for wp in ctx.policy.rules.specific_waiting_periods:
        m = match_condition(ctx.clinical_text(), wp)
        if m.kind is MatchKind.NONE:
            continue
        ev = {
            "condition": wp.name,
            "matched_term": m.term,
            "matched_field": m.field,
            "tenure_months": tenure,
            "required_months": wp.months,
        }
        if tenure >= wp.months:
            out.append(
                _finding(
                    rule,
                    ctx,
                    FindingOutcome.PASS,
                    f"{wp.name}: {wp.months}-month waiting period completed ({tenure} months).",
                    wp.clause_id,
                    evidence=ev,
                    confidence=ctx.conf("policy_start_date", "admission_date"),
                )
            )
        elif m.kind is MatchKind.EXACT:
            out.append(
                _finding(
                    rule,
                    ctx,
                    FindingOutcome.DENY,
                    f"{wp.name} treatment within {wp.months}-month waiting period "
                    f"(tenure {tenure} months).",
                    wp.clause_id,
                    evidence=ev,
                    confidence=ctx.conf(
                        "policy_start_date", "admission_date", m.field or "diagnosis"
                    ),
                )
            )
        else:
            out.append(
                _finding(
                    rule,
                    ctx,
                    FindingOutcome.REVIEW,
                    f"'{m.term}' may indicate {wp.name} (waiting period "
                    f"{wp.months} months, tenure {tenure}). Needs reviewer judgement.",
                    wp.clause_id,
                    evidence=ev,
                    confidence=0.55,
                    deterministic=False,
                )
            )
    if not out:
        out.append(
            _finding(
                rule,
                ctx,
                FindingOutcome.PASS,
                "No specified-disease waiting period applies.",
                confidence=min(ctx.conf("diagnosis"), 0.95),
            )
        )
    return out


def exclusions(ctx: RuleContext, rule: Rule) -> list[Finding]:
    out: list[Finding] = []
    for ex in ctx.policy.rules.exclusions:
        m = match_condition(ctx.clinical_text(), ex)
        ev = {"exclusion": ex.name, "matched_term": m.term, "matched_field": m.field}
        if m.kind is MatchKind.EXACT:
            out.append(
                _finding(
                    rule,
                    ctx,
                    FindingOutcome.DENY,
                    f"Treatment falls under permanent exclusion: {ex.name} (matched '{m.term}').",
                    ex.clause_id,
                    evidence=ev,
                    confidence=ctx.conf(m.field or "diagnosis"),
                )
            )
        elif m.kind is MatchKind.RELATED:
            out.append(
                _finding(
                    rule,
                    ctx,
                    FindingOutcome.REVIEW,
                    f"'{m.term}' may fall under exclusion '{ex.name}'. Not resolved "
                    "automatically; reviewer must confirm medical necessity.",
                    ex.clause_id,
                    evidence=ev,
                    confidence=0.5,
                    deterministic=False,
                )
            )
    if not out:
        out.append(
            _finding(
                rule,
                ctx,
                FindingOutcome.PASS,
                "No permanent exclusion matched.",
                confidence=min(ctx.conf("diagnosis"), 0.95),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Payable rules (line level)
# ---------------------------------------------------------------------------


def non_payables(ctx: RuleContext, rule: Rule) -> list[Finding]:
    r = ctx.policy.rules
    out: list[Finding] = []
    for line in ctx.ledger.values():
        desc = line.description.lower()
        hit_kw = next((k for k in r.non_payable_keywords if k in desc), None)
        if line.category in r.non_payable_categories or hit_kw:
            deducted = line.payable
            line.payable = 0.0
            reason = f"keyword '{hit_kw}'" if hit_kw else f"category '{line.category.value}'"
            line.notes.append(f"Non-payable ({reason})")
            out.append(
                _finding(
                    rule,
                    ctx,
                    FindingOutcome.ADJUST,
                    f"'{line.description}' INR {deducted:,.0f} is non-payable ({reason}).",
                    r.non_payable_clause,
                    amount_impact=-deducted,
                    evidence={"line_id": line.line_id},
                )
            )
    return out


def room_rent(ctx: RuleContext, rule: Rule) -> list[Finding]:
    r, f = ctx.policy.rules, ctx.facts
    out: list[Finding] = []
    caps = {BillCategory.ROOM: r.room_rent_cap_per_day, BillCategory.ICU: r.icu_cap_per_day}
    days_default = f.length_of_stay or 1
    ratio = 1.0
    for line in ctx.ledger.values():
        cap = caps.get(line.category)
        if cap is None or line.payable <= 0:
            continue
        days = next((li.days for li in f.line_items if li.line_id == line.line_id), None)
        days = days or days_default
        per_day = line.claimed / days
        if per_day <= cap + 0.5:
            continue
        allowed = cap * days
        deducted = line.payable - allowed
        line.payable = allowed
        line.notes.append(f"Capped at INR {cap:,.0f}/day x {days} days")
        ev = {"charged_per_day": per_day, "cap_per_day": cap, "days": days}
        out.append(
            _finding(
                rule,
                ctx,
                FindingOutcome.ADJUST,
                f"{line.category.value.upper()} charged INR {per_day:,.0f}/day; policy "
                f"permits INR {cap:,.0f}/day.",
                r.room_rent_clause,
                amount_impact=-deducted,
                evidence=ev,
            )
        )
        if line.category is BillCategory.ROOM:
            ratio = cap / per_day
    if ratio < 1.0 and r.proportionate_deduction_categories:
        total = 0.0
        for line in ctx.ledger.values():
            if line.category in r.proportionate_deduction_categories and line.payable > 0:
                before = line.payable
                line.payable = round(before * ratio, 2)
                line.notes.append(f"Proportionate deduction x{ratio:.3f}")
                total += before - line.payable
        if total > 0:
            out.append(
                _finding(
                    rule,
                    ctx,
                    FindingOutcome.ADJUST,
                    f"Proportionate deduction of {(1 - ratio):.1%} applied to "
                    "associated medical expenses (room category above eligibility).",
                    r.room_rent_clause,
                    amount_impact=-round(total, 2),
                    evidence={
                        "ratio": round(ratio, 4),
                        "categories": [c.value for c in r.proportionate_deduction_categories],
                    },
                )
            )
    if not out:
        out.append(
            _finding(
                rule,
                ctx,
                FindingOutcome.PASS,
                "Room/ICU charges within eligible limits.",
                r.room_rent_clause,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Payable rules (claim level)
# ---------------------------------------------------------------------------


def sublimits(ctx: RuleContext, rule: Rule) -> list[Finding]:
    out: list[Finding] = []
    for sl in ctx.policy.rules.sublimits:
        m = match_condition(ctx.clinical_text(), sl)
        ev = {"sublimit": sl.name, "max_amount": sl.max_amount, "matched_term": m.term}
        if m.kind is MatchKind.EXACT:
            if ctx.subtotal > sl.max_amount:
                deducted = ctx.subtotal - sl.max_amount
                ctx.subtotal = sl.max_amount
                out.append(
                    _finding(
                        rule,
                        ctx,
                        FindingOutcome.ADJUST,
                        f"{sl.name} sublimit caps payable at INR {sl.max_amount:,.0f}.",
                        sl.clause_id,
                        amount_impact=-deducted,
                        evidence=ev,
                        confidence=ctx.conf(m.field or "procedure"),
                    )
                )
            else:
                out.append(
                    _finding(
                        rule,
                        ctx,
                        FindingOutcome.PASS,
                        f"{sl.name} sublimit (INR {sl.max_amount:,.0f}) not exceeded.",
                        sl.clause_id,
                        evidence=ev,
                    )
                )
        elif m.kind is MatchKind.RELATED and ctx.subtotal > sl.max_amount:
            out.append(
                _finding(
                    rule,
                    ctx,
                    FindingOutcome.REVIEW,
                    f"'{m.term}' may attract the {sl.name} sublimit (INR {sl.max_amount:,.0f}).",
                    sl.clause_id,
                    evidence=ev,
                    confidence=0.55,
                    deterministic=False,
                )
            )
    return out


def sum_insured(ctx: RuleContext, rule: Rule) -> list[Finding]:
    r = ctx.policy.rules
    if ctx.subtotal > r.sum_insured:
        deducted = ctx.subtotal - r.sum_insured
        ctx.subtotal = r.sum_insured
        return [
            _finding(
                rule,
                ctx,
                FindingOutcome.ADJUST,
                f"Payable capped at sum insured INR {r.sum_insured:,.0f}.",
                r.sum_insured_clause,
                amount_impact=-deducted,
            )
        ]
    return [
        _finding(
            rule,
            ctx,
            FindingOutcome.PASS,
            f"Within sum insured (INR {r.sum_insured:,.0f}).",
            r.sum_insured_clause,
        )
    ]


def deductible(ctx: RuleContext, rule: Rule) -> list[Finding]:
    r = ctx.policy.rules
    if r.deductible <= 0:
        return []
    deducted = min(r.deductible, ctx.subtotal)
    ctx.subtotal -= deducted
    return [
        _finding(
            rule,
            ctx,
            FindingOutcome.ADJUST,
            f"Deductible of INR {r.deductible:,.0f} applied.",
            r.deductible_clause,
            amount_impact=-deducted,
        )
    ]


def copay(ctx: RuleContext, rule: Rule) -> list[Finding]:
    r, f = ctx.policy.rules, ctx.facts
    if r.copay_percent <= 0:
        return []
    applies = r.copay_min_age is None or (
        f.patient_age is not None and f.patient_age >= r.copay_min_age
    )
    if not applies:
        return [
            _finding(
                rule,
                ctx,
                FindingOutcome.PASS,
                f"Co-pay not applicable (age {f.patient_age}).",
                r.copay_clause,
                confidence=ctx.conf("patient_age"),
            )
        ]
    deducted = round(ctx.subtotal * r.copay_percent / 100, 2)
    ctx.subtotal -= deducted
    return [
        _finding(
            rule,
            ctx,
            FindingOutcome.ADJUST,
            f"{r.copay_percent:g}% co-pay applied (insured aged {f.patient_age}).",
            r.copay_clause,
            amount_impact=-deducted,
            confidence=ctx.conf("patient_age"),
        )
    ]


ELIGIBILITY_RULES = [
    Rule("DOC-001", "1.0", "Required documents", required_documents),
    Rule("EXT-001", "1.0", "Extraction completeness", required_fields),
    Rule("WAIT-001", "1.0", "Initial waiting period", initial_waiting),
    Rule("PED-001", "1.0", "Pre-existing disease", pre_existing),
    Rule("WAIT-002", "1.0", "Specified disease waiting period", specific_waiting),
    Rule("EXCL-001", "1.0", "Permanent exclusions", exclusions),
]
LINE_RULES = [
    Rule("NPAY-001", "1.0", "Non-payable items", non_payables),
    Rule("ROOM-001", "1.0", "Room rent / ICU limits", room_rent),
]
CLAIM_RULES = [
    Rule("SUBL-001", "1.0", "Procedure sublimits", sublimits),
    Rule("SI-001", "1.0", "Sum insured", sum_insured),
    Rule("DED-001", "1.0", "Deductible", deductible),
    Rule("COPAY-001", "1.0", "Co-payment", copay),
]


@dataclass
class RulesResult:
    findings: list[Finding]
    payable_lines: list[PayableLine]
    payable_amount: float


def run_rules(policy: Policy, facts: ClaimFacts, documents: list[ClaimDocument]) -> RulesResult:
    ctx = RuleContext(policy=policy, facts=facts, documents=documents)
    ctx.ledger = {
        li.line_id: PayableLine(
            line_id=li.line_id,
            description=li.description,
            category=li.category,
            claimed=li.amount,
            payable=li.amount,
        )
        for li in facts.line_items
    }
    findings: list[Finding] = []
    for rule in ELIGIBILITY_RULES + LINE_RULES:
        findings.extend(rule.evaluate(ctx))
    ctx.subtotal = round(sum(line.payable for line in ctx.ledger.values()), 2)
    for rule in CLAIM_RULES:
        findings.extend(rule.evaluate(ctx))
    return RulesResult(
        findings=findings,
        payable_lines=list(ctx.ledger.values()),
        payable_amount=round(max(ctx.subtotal, 0.0), 2),
    )
