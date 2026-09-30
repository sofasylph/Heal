"""Append-only, hash-chained audit log.

Each event stores sha256(prev_hash + canonical JSON of the event). Editing or deleting
any historical event breaks the chain, which `verify_chain` detects. This answers the
"why did the system recommend INR 142,500 six months ago?" question with evidence that
the record has not been altered since.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from claimtrace.db.session import AuditEventRow

GENESIS = "0" * 64


class AuditAction(StrEnum):
    DOCUMENTS_INGESTED = "documents_ingested"
    FACTS_EXTRACTED = "facts_extracted"
    RULES_EVALUATED = "rules_evaluated"
    LLM_SUGGESTED = "llm_suggested"
    DECISION_RECOMMENDED = "decision_recommended"
    HUMAN_OVERRIDE = "human_override"


class AuditEvent(BaseModel):
    claim_id: str
    seq: int
    timestamp: datetime
    actor: str
    action: AuditAction
    payload: dict
    prev_hash: str
    hash: str


def _digest(prev_hash: str, body: dict) -> str:
    canonical = json.dumps(body, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256((prev_hash + canonical).encode()).hexdigest()


def _body(claim_id: str, seq: int, ts: datetime, actor: str, action: str, payload: dict) -> dict:
    return {
        "claim_id": claim_id,
        "seq": seq,
        "timestamp": ts.isoformat(),
        "actor": actor,
        "action": action,
        "payload": payload,
    }


def record(
    session: Session, claim_id: str, actor: str, action: AuditAction, payload: dict
) -> AuditEventRow:
    last = session.scalars(
        select(AuditEventRow)
        .where(AuditEventRow.claim_id == claim_id)
        .order_by(AuditEventRow.seq.desc())
        .limit(1)
    ).first()
    seq = (last.seq + 1) if last else 1
    prev = last.hash if last else GENESIS
    ts = datetime.now(UTC)
    payload = json.loads(json.dumps(payload, default=str))
    row = AuditEventRow(
        claim_id=claim_id,
        seq=seq,
        timestamp=ts,
        actor=actor,
        action=action.value,
        payload=payload,
        prev_hash=prev,
        hash=_digest(prev, _body(claim_id, seq, ts, actor, action.value, payload)),
    )
    session.add(row)
    session.flush()
    return row


def events_for(session: Session, claim_id: str) -> list[AuditEvent]:
    rows = session.scalars(
        select(AuditEventRow).where(AuditEventRow.claim_id == claim_id).order_by(AuditEventRow.seq)
    ).all()
    return [
        AuditEvent(
            claim_id=r.claim_id,
            seq=r.seq,
            timestamp=r.timestamp,
            actor=r.actor,
            action=AuditAction(r.action),
            payload=r.payload,
            prev_hash=r.prev_hash,
            hash=r.hash,
        )
        for r in rows
    ]


def verify_chain(events: list[AuditEvent]) -> bool:
    prev = GENESIS
    for e in events:
        ts = e.timestamp if e.timestamp.tzinfo else e.timestamp.replace(tzinfo=UTC)
        expected = _digest(prev, _body(e.claim_id, e.seq, ts, e.actor, e.action.value, e.payload))
        if e.prev_hash != prev or e.hash != expected:
            return False
        prev = e.hash
    return True
