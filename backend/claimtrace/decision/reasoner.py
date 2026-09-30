"""Interface for an LLM clause reasoner.

The reasoner may only *suggest* a resolution for findings the deterministic engine
marked REVIEW; it can never override a deterministic DENY/ADJUST, and its output is
recorded in the audit trail with model + prompt version. v0.1 ships the null
implementation so the system runs without API keys.
"""

from __future__ import annotations

import os
from typing import Protocol

from pydantic import BaseModel

from claimtrace.domain.models import ClaimFacts, Finding


class ReasonerSuggestion(BaseModel):
    rule_id: str
    suggested_outcome: str
    rationale: str
    model: str
    prompt_version: str
    confidence: float


class ClauseReasoner(Protocol):
    name: str

    def suggest(self, finding: Finding, facts: ClaimFacts) -> ReasonerSuggestion | None: ...


class NullReasoner:
    name = "none"

    def suggest(self, finding: Finding, facts: ClaimFacts) -> ReasonerSuggestion | None:
        return None


def get_reasoner() -> ClauseReasoner:
    provider = os.getenv("CLAIMTRACE_LLM_PROVIDER", "none")
    if provider == "none":
        return NullReasoner()
    raise NotImplementedError(f"LLM provider '{provider}' is not wired up yet; see docs/ROADMAP.md")
