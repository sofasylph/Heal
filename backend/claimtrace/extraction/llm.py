"""Interface for an LLM-backed extractor (not enabled in v0.1).

Contract: given classified documents, return a ClaimFacts with per-field confidence and
source doc ids. Outputs are schema-validated by Pydantic before use and merged with the
heuristic extractor; disagreements become `conflicts`, never silent overwrites.
"""

from __future__ import annotations

from typing import Protocol

from claimtrace.domain.models import ClaimDocument, ClaimFacts


class LLMExtractor(Protocol):
    model: str
    prompt_version: str

    def extract(self, documents: list[ClaimDocument]) -> ClaimFacts: ...
