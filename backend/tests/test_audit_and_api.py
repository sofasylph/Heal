import random

from fastapi.testclient import TestClient

from claimtrace.api.app import app
from claimtrace.audit.log import events_for, verify_chain
from claimtrace.db.session import SessionLocal
from claimtrace.evaluation.synthetic import Scenario, generate_claim
from claimtrace.policies.registry import get_policy


def test_api_end_to_end():
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        queue = client.get("/claims").json()
        assert len(queue) >= 10  # demo seed

        sc = generate_claim(
            random.Random(3), 9001, Scenario.ROOM_RENT_OVER_CAP, get_policy("SURAKSHA-SILVER")
        )
        body = {"policy_id": sc.policy_id, "documents": [d.model_dump() for d in sc.documents]}
        created = client.post("/claims", json=body)
        assert created.status_code == 201
        claim = created.json()
        cid = claim["claim_id"]
        assert claim["decision"]["payable_amount"] == sc.truth.payable_amount

        r = client.post(
            f"/claims/{cid}/override",
            json={
                "reviewer": "tester",
                "recommendation": "partial",
                "payable_amount": 1000,
                "reason": "Testing override",
            },
        )
        assert r.status_code == 200 and r.json()["status"] == "finalised"

        trail = client.get(f"/claims/{cid}/audit").json()
        assert trail["chain_valid"] is True
        assert [e["action"] for e in trail["events"]] == [
            "documents_ingested",
            "facts_extracted",
            "rules_evaluated",
            "decision_recommended",
            "human_override",
        ]

        assert client.get("/claims/NOPE").status_code == 404
        assert client.post("/claims", json={**body, "policy_id": "X"}).status_code == 400


def test_tampering_breaks_audit_chain():
    with TestClient(app) as client:
        cid = client.get("/claims").json()[0]["claim_id"]
    with SessionLocal() as s:
        events = events_for(s, cid)
    assert verify_chain(events)
    events[1].payload["facts"] = {"tampered": True}
    assert not verify_chain(events)
