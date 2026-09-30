"""Settings, document upload, sample claims and analytics routes."""

from __future__ import annotations

import io
import random

from fastapi import APIRouter, HTTPException, UploadFile

from claimtrace.access import AccessDenied, Permission, Role, require
from claimtrace.analytics.service import compute as compute_analytics
from claimtrace.api.deps import DB, CurrentActor
from claimtrace.api.schemas import ExtractedDocument, Me, SampleClaim
from claimtrace.evaluation.synthetic import Scenario, generate_claim
from claimtrace.policies.registry import get_policy
from claimtrace.settings import store
from claimtrace.settings.components import build, catalog

router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_FILES = 10

SCENARIO_DESCRIPTIONS = {
    Scenario.CLEAN: "Routine surgical or medical admission, within limits",
    Scenario.ROOM_RENT_OVER_CAP: "Room category above eligibility: proportionate deduction",
    Scenario.SENIOR_COPAY: "Insured aged 61+: co-payment applies",
    Scenario.PED_WITHIN_WAITING: "Pre-existing disease inside its waiting period",
    Scenario.PED_AFTER_WAITING: "Pre-existing disease after its waiting period",
    Scenario.SPECIFIC_WAITING: "Hernia inside the specified-disease waiting period",
    Scenario.INITIAL_WAITING: "Illness within 30 days of policy start",
    Scenario.COSMETIC_EXCLUDED: "Cosmetic surgery: permanent exclusion",
    Scenario.AMBIGUOUS_EXCLUSION: "Ambiguous wording that is really cosmetic",
    Scenario.AMBIGUOUS_COVERED: "Ambiguous wording covered by a clause exception (burns)",
    Scenario.MISSING_DOCUMENT: "Discharge summary missing",
    Scenario.CONFLICTING_DATES: "Documents disagree on the admission date",
    Scenario.DUPLICATE_LINE: "Bill contains a duplicated line item",
    Scenario.PADDED_PHARMACY: "Pharmacy padded while the total looks normal",
}


@router.get("/me", response_model=Me)
def me(actor: CurrentActor) -> Me:
    return Me(
        user=actor.user,
        role=actor.role.value,
        permissions=sorted(p.value for p in Permission if actor.can(p)),
    )


@router.get("/roles")
def roles() -> list[dict]:
    return [
        {
            "id": Role.REVIEWER,
            "label": "Reviewer",
            "description": "Creates claims and decides auto-candidate and verify claims.",
        },
        {
            "id": Role.SENIOR_REVIEWER,
            "label": "Senior reviewer",
            "description": "Everything a reviewer can do, plus escalated claims and settings.",
        },
        {
            "id": Role.AUDITOR,
            "label": "Auditor",
            "description": "Read-only access to claims, audit trails and analytics.",
        },
    ]


# ---------------------------------------------------------------- settings


@router.get("/settings")
def get_settings(session: DB) -> dict:
    cur = store.current(session)
    return {
        "version": cur.version,
        "settings": cur.settings,
        "updated_by": cur.updated_by,
        "updated_at": cur.updated_at,
        "active_models": build(cur.settings).models_used,
        "catalog": catalog(cur.settings),
    }


@router.put("/settings")
def put_settings(new: store.ModelSettings, session: DB, actor: CurrentActor) -> dict:
    try:
        require(actor, Permission.UPDATE_SETTINGS, "Only a senior reviewer can change models")
    except AccessDenied as e:
        raise HTTPException(403, str(e)) from e
    store.save(session, new, actor.label)
    return get_settings(session)


@router.get("/settings/history")
def settings_history(session: DB) -> list[store.SettingsVersion]:
    return store.history(session)


# ---------------------------------------------------------------- documents


def _pdf_text(data: bytes) -> tuple[str, int]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages), len(reader.pages)


@router.post("/documents/extract", response_model=list[ExtractedDocument])
async def extract_documents(files: list[UploadFile], session: DB) -> list[ExtractedDocument]:
    if len(files) > MAX_FILES:
        raise HTTPException(413, f"At most {MAX_FILES} files per upload")
    classifier = build(store.current(session).settings).classifier
    out = []
    for f in files:
        data = await f.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{f.filename} is larger than 10 MB")
        name = f.filename or "document"
        pages, warning = None, None
        if name.lower().endswith(".pdf") or data[:5] == b"%PDF-":
            try:
                text, pages = _pdf_text(data)
            except Exception as e:
                raise HTTPException(422, f"Could not read PDF {name}: {e}") from e
            if not text.strip():
                warning = "No text layer found (scanned PDF?). OCR is not supported yet."
        else:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError as e:
                raise HTTPException(415, f"{name}: only PDF and UTF-8 text files") from e
        dtype, conf = classifier.classify(text)
        out.append(
            ExtractedDocument(
                filename=name,
                text=text,
                doc_type=dtype.value,
                classification_confidence=conf,
                pages=pages,
                warning=warning,
            )
        )
    return out


# ---------------------------------------------------------------- samples


@router.get("/samples")
def list_samples() -> list[dict]:
    return [{"scenario": s.value, "description": d} for s, d in SCENARIO_DESCRIPTIONS.items()]


@router.get("/samples/{scenario}", response_model=SampleClaim)
def sample(
    scenario: Scenario, policy_id: str = "SURAKSHA-SILVER", seed: int | None = None
) -> SampleClaim:
    if scenario in (Scenario.AMBIGUOUS_EXCLUSION, Scenario.AMBIGUOUS_COVERED):
        policy_id = "SURAKSHA-SILVER"  # only this policy lists the related terms
    try:
        policy = get_policy(policy_id)
    except KeyError as e:
        raise HTTPException(404, f"Unknown policy {policy_id}") from e
    rng = random.Random(seed if seed is not None else random.randrange(1_000_000))
    sc = generate_claim(rng, 0, scenario, policy)
    return SampleClaim(
        scenario=scenario.value,
        description=SCENARIO_DESCRIPTIONS[scenario],
        policy_id=policy_id,
        documents=sc.documents,
        expected_recommendation=sc.truth.recommendation.value,
        expected_payable=sc.truth.payable_amount,
    )


# ---------------------------------------------------------------- analytics


@router.get("/analytics")
def analytics(session: DB) -> dict:
    return compute_analytics(session)
