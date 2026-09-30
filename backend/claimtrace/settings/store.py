"""Model settings: which classifier, anomaly detector and clause reasoner to use.

Stored as append-only versions (who changed what, when); the latest version is live.
Every decision records the models it was produced with.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from claimtrace.db.session import SettingsVersionRow
from claimtrace.decision.reasoner import DEFAULT_OLLAMA_MODEL, DEFAULT_OLLAMA_URL

ReasonerProvider = Literal["none", "claude", "ollama"]
ClaudeModel = Literal["claude-haiku-4-5", "claude-sonnet-5-5", "claude-opus-5-5"]


def _env_provider() -> ReasonerProvider:
    p = os.getenv("CLAIMTRACE_LLM_PROVIDER", "none").lower()
    return p if p in ("none", "claude", "ollama") else "none"  # type: ignore[return-value]


class ModelSettings(BaseModel):
    reasoner_provider: ReasonerProvider = "none"
    claude_model: ClaudeModel = "claude-opus-5-5"
    claude_effort: Literal["low", "medium", "high"] = "high"
    ollama_model: str = DEFAULT_OLLAMA_MODEL
    ollama_url: str = DEFAULT_OLLAMA_URL
    # Defaults are the best-measured options (docs/eval/model_comparison.md).
    doc_classifier: Literal["keyword", "tfidf_logreg"] = "tfidf_logreg"
    anomaly_detector: Literal["rules", "isolation_forest", "hybrid"] = "hybrid"

    @classmethod
    def from_env(cls) -> ModelSettings:
        base = cls()
        return cls.model_validate(
            base.model_dump()
            | {
                "reasoner_provider": _env_provider(),
                "claude_model": os.getenv("CLAIMTRACE_LLM_MODEL", base.claude_model),
                "claude_effort": os.getenv("CLAIMTRACE_LLM_EFFORT", base.claude_effort),
                "ollama_model": os.getenv("CLAIMTRACE_OLLAMA_MODEL", base.ollama_model),
                "ollama_url": os.getenv("CLAIMTRACE_OLLAMA_URL", base.ollama_url),
                "doc_classifier": os.getenv("CLAIMTRACE_DOC_CLASSIFIER", base.doc_classifier),
                "anomaly_detector": os.getenv("CLAIMTRACE_ANOMALY_DETECTOR", base.anomaly_detector),
            }
        )


class SettingsVersion(BaseModel):
    version: int
    settings: ModelSettings
    updated_by: str
    updated_at: datetime


def current(session: Session) -> SettingsVersion:
    row = session.scalars(
        select(SettingsVersionRow).order_by(SettingsVersionRow.id.desc()).limit(1)
    ).first()
    if row is None:
        return SettingsVersion(
            version=0,
            settings=ModelSettings.from_env(),
            updated_by="environment",
            updated_at=datetime.now(UTC),
        )
    return SettingsVersion(
        version=row.id,
        settings=ModelSettings.model_validate(row.value),
        updated_by=row.updated_by,
        updated_at=row.updated_at,
    )


def save(session: Session, settings: ModelSettings, updated_by: str) -> SettingsVersion:
    row = SettingsVersionRow(
        value=settings.model_dump(mode="json"), updated_by=updated_by, updated_at=datetime.now(UTC)
    )
    session.add(row)
    session.commit()
    return current(session)


def history(session: Session, limit: int = 20) -> list[SettingsVersion]:
    rows = session.scalars(
        select(SettingsVersionRow).order_by(SettingsVersionRow.id.desc()).limit(limit)
    ).all()
    return [
        SettingsVersion(
            version=r.id,
            settings=ModelSettings.model_validate(r.value),
            updated_by=r.updated_by,
            updated_at=r.updated_at,
        )
        for r in rows
    ]
