"""Ingestion pipeline: raw documents -> classified documents -> structured facts."""

from __future__ import annotations

import hashlib
import uuid

from pydantic import BaseModel

from claimtrace.domain.models import ClaimDocument, ClaimFacts, DocumentType
from claimtrace.extraction.classifier import classify
from claimtrace.extraction.extractor import extract_facts


class RawDocument(BaseModel):
    filename: str
    text: str
    doc_type: DocumentType | None = None  # caller may pre-label


def ingest_documents(raw: list[RawDocument], classifier=None) -> list[ClaimDocument]:
    """`classifier` is any object with classify(text) -> (DocumentType, confidence);
    defaults to the keyword classifier."""
    classify_fn = classifier.classify if classifier is not None else classify
    docs = []
    for r in raw:
        if r.doc_type:
            dtype, conf = r.doc_type, 1.0
        else:
            dtype, conf = classify_fn(r.text)
        docs.append(
            ClaimDocument(
                doc_id=f"DOC-{uuid.uuid4().hex[:8].upper()}",
                filename=r.filename,
                text=r.text,
                doc_type=dtype,
                classification_confidence=conf,
                sha256=hashlib.sha256(r.text.encode()).hexdigest(),
            )
        )
    return docs


def extract(docs: list[ClaimDocument]) -> ClaimFacts:
    return extract_facts(docs)
