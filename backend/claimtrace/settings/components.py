"""Turns ModelSettings into live components, plus the catalog shown on the settings page."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from claimtrace.decision.reasoner import (
    CLAUDE_MODELS,
    ClaudeReasoner,
    ClauseReasoner,
    NullReasoner,
    OllamaReasoner,
    ResponseCache,
    ollama_models,
)
from claimtrace.ml.anomaly import ANOMALY_DETECTORS, AnomalyDetector, get_anomaly_detector
from claimtrace.ml.doc_classifier import DOC_CLASSIFIERS, DocClassifier, get_doc_classifier
from claimtrace.settings.store import ModelSettings

log = logging.getLogger("claimtrace.settings")


@dataclass(frozen=True)
class Components:
    classifier: DocClassifier
    detector: AnomalyDetector
    reasoner: ClauseReasoner
    models_used: dict[str, str]


def _cache() -> ResponseCache | None:
    path = os.getenv("CLAIMTRACE_LLM_CACHE")
    return ResponseCache(Path(path)) if path else None


def claude_credentials_present() -> bool:
    return bool(
        os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("ANTHROPIC_AUTH_TOKEN")
        or (Path.home() / ".config" / "anthropic").exists()
    )


@lru_cache(maxsize=16)
def _build(settings_json: str) -> Components:
    s = ModelSettings.model_validate_json(settings_json)
    reasoner: ClauseReasoner = NullReasoner()
    reasoner_label = "none"
    try:
        if s.reasoner_provider == "claude":
            reasoner = ClaudeReasoner(model=s.claude_model, effort=s.claude_effort, cache=_cache())
            reasoner_label = f"claude:{s.claude_model}"
        elif s.reasoner_provider == "ollama":
            reasoner = OllamaReasoner(model=s.ollama_model, url=s.ollama_url, cache=_cache())
            reasoner_label = f"ollama:{s.ollama_model}"
    except Exception as e:  # e.g. no credentials: fail closed, record why
        log.warning("Clause reasoner unavailable (%s): %s", type(e).__name__, e)
        reasoner, reasoner_label = NullReasoner(), f"none ({s.reasoner_provider} unavailable)"
    return Components(
        classifier=get_doc_classifier(s.doc_classifier),
        detector=get_anomaly_detector(s.anomaly_detector),
        reasoner=reasoner,
        models_used={
            "doc_classifier": s.doc_classifier,
            "anomaly_detector": s.anomaly_detector,
            "clause_reasoner": reasoner_label,
        },
    )


def build(settings: ModelSettings) -> Components:
    return _build(settings.model_dump_json())


def catalog(settings: ModelSettings) -> dict:
    installed = ollama_models(settings.ollama_url)
    return {
        "doc_classifier": [
            {"id": k, "label": v[0], "description": v[1], "available": True}
            for k, v in DOC_CLASSIFIERS.items()
        ],
        "anomaly_detector": [
            {"id": k, "label": v[0], "description": v[1], "available": True}
            for k, v in ANOMALY_DETECTORS.items()
        ],
        "reasoner_provider": [
            {
                "id": "none",
                "label": "Off (rules only)",
                "available": True,
                "description": "Ambiguous clauses always escalate to a senior reviewer.",
            },
            {
                "id": "claude",
                "label": "Claude (Anthropic API)",
                "available": claude_credentials_present(),
                "description": "Hosted models. Needs ANTHROPIC_API_KEY or `ant auth login`.",
            },
            {
                "id": "ollama",
                "label": "Local open-weights (Ollama)",
                "available": installed is not None,
                "description": "Runs on your machine; claim data never leaves it.",
            },
        ],
        "claude_model": [{"id": k, "label": v["label"]} for k, v in CLAUDE_MODELS.items()],
        "ollama_installed_models": installed or [],
    }
