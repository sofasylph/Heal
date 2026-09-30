"""Keyword-scored document classifier. Replaceable by an ML/LLM classifier later."""

from __future__ import annotations

import re

from claimtrace.domain.models import DocumentType

SIGNALS: dict[DocumentType, list[str]] = {
    DocumentType.CLAIM_FORM: [
        "claim form",
        "policy number",
        "declaration by insured",
        "amount claimed",
        "insured name",
    ],
    DocumentType.DISCHARGE_SUMMARY: [
        "discharge summary",
        "date of admission",
        "course in hospital",
        "final diagnosis",
        "condition at discharge",
    ],
    DocumentType.INVOICE: ["final bill", "invoice", "bill no", "net payable", "grand total"],
    DocumentType.DIAGNOSTIC_REPORT: [
        "investigation report",
        "impression",
        "specimen",
        "reference range",
        "radiology",
    ],
    DocumentType.PRE_AUTH: ["pre-authorization", "pre-authorisation", "cashless request"],
    DocumentType.PRESCRIPTION: ["prescription", "rx", "sig:"],
    DocumentType.POLICY: ["policy wording", "exclusions", "sum insured", "waiting period"],
}


def classify(text: str) -> tuple[DocumentType, float]:
    t = text.lower()
    scores = {
        dt: sum(1 for kw in kws if re.search(rf"\b{re.escape(kw)}", t))
        for dt, kws in SIGNALS.items()
    }
    best = max(scores, key=lambda d: scores[d])
    total = sum(scores.values())
    if scores[best] == 0:
        return DocumentType.UNKNOWN, 0.0
    return best, round(scores[best] / total, 2)
