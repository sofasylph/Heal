"""FastAPI application. Run: uvicorn claimtrace.api.app:app --reload"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from claimtrace import ENGINE_VERSION
from claimtrace.access import AccessDenied
from claimtrace.api.deps import DB, CurrentActor
from claimtrace.api.routes_extra import router as extra_router
from claimtrace.api.schemas import (
    AuditTrail,
    ClaimSummary,
    CreateClaimRequest,
    OverrideRequest,
    PolicySummary,
)
from claimtrace.audit.log import events_for, verify_chain
from claimtrace.claims import service
from claimtrace.db.session import SessionLocal, init_db
from claimtrace.domain.models import Claim
from claimtrace.policies.models import Policy
from claimtrace.policies.registry import get_policy, load_policies

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("claimtrace")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if os.getenv("CLAIMTRACE_SEED", "1") == "1":
        from claimtrace.db.seed import seed_demo_data

        with SessionLocal() as s:
            n = seed_demo_data(s)
            if n:
                log.info("Seeded %d demo claims", n)
    yield


app = FastAPI(
    title="ClaimTrace API",
    version=ENGINE_VERSION,
    description="Evidence-backed decision support for health insurance claims review.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(extra_router)


@app.exception_handler(AccessDenied)
async def access_denied(_: Request, exc: AccessDenied) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "engine_version": ENGINE_VERSION}


@app.get("/policies", response_model=list[PolicySummary])
def list_policies() -> list[PolicySummary]:
    return [
        PolicySummary(
            policy_id=p.policy_id,
            version=p.version,
            name=p.name,
            insurer=p.insurer,
            description=p.description,
            sum_insured=p.rules.sum_insured,
        )
        for p in load_policies().values()
    ]


@app.get("/policies/{policy_id}", response_model=Policy)
def policy_detail(policy_id: str) -> Policy:
    try:
        return get_policy(policy_id)
    except KeyError as e:
        raise HTTPException(404, f"Unknown policy {policy_id}") from e


@app.get("/claims", response_model=list[ClaimSummary])
def list_claims(session: DB) -> list[ClaimSummary]:
    return [
        ClaimSummary.model_validate(r, from_attributes=True) for r in service.list_claims(session)
    ]


@app.post("/claims", response_model=Claim, status_code=201)
def create_claim(req: CreateClaimRequest, session: DB, actor: CurrentActor) -> Claim:
    try:
        claim = service.create_claim(session, req.policy_id, req.documents, actor=actor)
    except KeyError as e:
        raise HTTPException(400, str(e)) from e
    if req.adjudicate:
        claim = service.adjudicate(session, claim.claim_id, actor=actor)
    return claim


@app.get("/claims/{claim_id}", response_model=Claim)
def get_claim(claim_id: str, session: DB) -> Claim:
    try:
        return service.get_claim(session, claim_id)
    except service.NotFoundError as e:
        raise HTTPException(404, f"Unknown claim {claim_id}") from e


@app.post("/claims/{claim_id}/adjudicate", response_model=Claim)
def adjudicate(claim_id: str, session: DB, actor: CurrentActor) -> Claim:
    try:
        return service.adjudicate(session, claim_id, actor=actor)
    except service.NotFoundError as e:
        raise HTTPException(404, f"Unknown claim {claim_id}") from e


@app.post("/claims/{claim_id}/override", response_model=Claim)
def override(claim_id: str, req: OverrideRequest, session: DB, actor: CurrentActor) -> Claim:
    try:
        return service.override(
            session, claim_id, actor, req.recommendation, req.payable_amount, req.reason
        )
    except service.NotFoundError as e:
        raise HTTPException(404, f"Unknown claim {claim_id}") from e
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.get("/claims/{claim_id}/audit", response_model=AuditTrail)
def audit(claim_id: str, session: DB) -> AuditTrail:
    events = events_for(session, claim_id)
    if not events:
        raise HTTPException(404, f"No audit trail for {claim_id}")
    return AuditTrail(claim_id=claim_id, chain_valid=verify_chain(events), events=events)
