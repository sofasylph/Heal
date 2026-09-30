"""Synthetic training data for the small models.

Training uses different random seeds from the evaluation benchmark (seed 7), so models
are never scored on claims they were trained on.
"""

from __future__ import annotations

import random
import re
from functools import lru_cache

from claimtrace.domain.models import ClaimFacts, DocumentType
from claimtrace.evaluation.synthetic import (
    Scenario,
    generate_claim,
    render_auxiliary_documents,
)
from claimtrace.extraction.pipeline import extract, ingest_documents
from claimtrace.policies.registry import load_policies

TRAIN_SEED = 101
TEST_SEED = 202

FILENAME_LABELS = {
    "claim_form.txt": DocumentType.CLAIM_FORM,
    "discharge_summary.txt": DocumentType.DISCHARGE_SUMMARY,
    "final_bill.txt": DocumentType.INVOICE,
}

# Scenarios whose bills are normal; the anomaly model learns "normal" from these.
NORMAL_SCENARIOS = [
    Scenario.CLEAN,
    Scenario.ROOM_RENT_OVER_CAP,
    Scenario.SENIOR_COPAY,
    Scenario.PED_AFTER_WAITING,
    Scenario.SPECIFIC_WAITING,
    Scenario.CONFLICTING_DATES,
]


def degrade(text: str, rng: random.Random, drop: float = 0.3) -> str:
    """Simulate a poor scan / partial upload: lose title lines and a share of the rest."""
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and stripped.upper() == stripped and any(c.isalpha() for c in stripped):
            continue  # all-caps headers are the first thing OCR mangles
        if rng.random() < drop:
            continue
        out.append(line)
    return "\n".join(out)


def labelled_documents(n_claims: int, seed: int, degraded_share: float = 0.5):
    """(text, DocumentType) pairs covering six document types."""
    rng = random.Random(seed)
    policies = list(load_policies().values())
    scenarios = [s for s in Scenario if s is not Scenario.MISSING_DOCUMENT]
    pairs: list[tuple[str, DocumentType]] = []
    for i in range(n_claims):
        sc = generate_claim(rng, i, rng.choice(scenarios), rng.choice(policies))
        docs = [(d.text, FILENAME_LABELS[d.filename]) for d in sc.documents]
        docs += [
            (d.text, DocumentType(d.doc_type))
            for d in render_auxiliary_documents(rng, sc.truth_facts)
        ]
        for text, label in docs:
            pairs.append((text, label))
            if rng.random() < degraded_share:
                pairs.append((degrade(text, rng), label))
    return pairs


@lru_cache
def normal_claim_facts(n_claims: int = 300, seed: int = TRAIN_SEED) -> tuple[ClaimFacts, ...]:
    rng = random.Random(seed)
    policies = list(load_policies().values())
    out = []
    for i in range(n_claims):
        sc = generate_claim(rng, i, rng.choice(NORMAL_SCENARIOS), rng.choice(policies))
        out.append(extract(ingest_documents(sc.documents)))
    return tuple(out)


def normalise(text: str) -> str:
    return re.sub(r"\d", "0", text.lower())
