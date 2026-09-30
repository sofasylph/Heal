"""Deterministic text matching of clinical descriptions against policy conditions.

Matching is intentionally conservative: an exact keyword hit applies the rule, a hit on
a *related* term only raises the possibility, and the claim is routed to review. This
is the seam where an LLM reasoner can later resolve ambiguity, without ever being
allowed to silently approve.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from claimtrace.policies.models import ConditionRule


class MatchKind(StrEnum):
    EXACT = "exact"
    RELATED = "related"
    NONE = "none"


@dataclass(frozen=True)
class MatchResult:
    kind: MatchKind
    term: str | None = None
    field: str | None = None


def _contains(text: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term.lower())}\b", text.lower()) is not None


def match_condition(texts: dict[str, str | None], rule: ConditionRule) -> MatchResult:
    """Match a rule against named text fields (e.g. diagnosis, procedure)."""
    for field, text in texts.items():
        if not text:
            continue
        for kw in rule.keywords:
            if _contains(text, kw):
                return MatchResult(MatchKind.EXACT, kw, field)
    for field, text in texts.items():
        if not text:
            continue
        for term in rule.related_terms:
            if _contains(text, term):
                return MatchResult(MatchKind.RELATED, term, field)
    return MatchResult(MatchKind.NONE)


def stem_overlap(condition: str, text: str | None, stem_len: int = 6) -> bool:
    """Loose relation test between a declared condition and a diagnosis.

    `diabetes` -> stem `diabet` matches `diabetic foot ulcer`. Words shorter than the
    stem length must match whole-word.
    """
    if not text:
        return False
    text_l = text.lower()
    for word in re.findall(r"[a-z]+", condition.lower()):
        if len(word) < 4:
            continue
        stem = word[:stem_len]
        if re.search(rf"\b{re.escape(stem)}", text_l):
            return True
    return False
