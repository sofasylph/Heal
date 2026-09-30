"""Roles, model settings, uploads, samples and analytics through the API."""

import random

import pytest
from fastapi.testclient import TestClient

from claimtrace.api.app import app
from claimtrace.evaluation.synthetic import Scenario, generate_claim
from claimtrace.policies.registry import get_policy

REVIEWER = {"X-User": "rita", "X-Role": "reviewer"}
SENIOR = {"X-User": "sam", "X-Role": "senior_reviewer"}
AUDITOR = {"X-User": "alex", "X-Role": "auditor"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _submit(client, scenario, headers=REVIEWER, seed=1):
    sc = generate_claim(random.Random(seed), 0, scenario, get_policy("SURAKSHA-SILVER"))
    body = {"policy_id": sc.policy_id, "documents": [d.model_dump() for d in sc.documents]}
    return client.post("/claims", json=body, headers=headers), sc


DECISION = {"recommendation": "not_payable", "payable_amount": 0, "reason": "Confirmed."}


def test_me_reports_permissions(client):
    assert "settings:update" not in client.get("/me", headers=REVIEWER).json()["permissions"]
    assert "settings:update" in client.get("/me", headers=SENIOR).json()["permissions"]
    assert client.get("/me", headers=AUDITOR).json()["permissions"] == []
    assert client.get("/me", headers={"X-Role": "admin"}).status_code == 400


def test_auditor_is_read_only(client):
    r, _ = _submit(client, Scenario.CLEAN, headers=AUDITOR)
    assert r.status_code == 403
    cid = client.get("/claims").json()[0]["claim_id"]
    assert client.get(f"/claims/{cid}", headers=AUDITOR).status_code == 200
    assert client.get(f"/claims/{cid}/audit", headers=AUDITOR).status_code == 200
    assert client.post(f"/claims/{cid}/override", json=DECISION, headers=AUDITOR).status_code == 403
    assert client.post(f"/claims/{cid}/adjudicate", headers=AUDITOR).status_code == 403


def test_escalated_claims_need_a_senior_reviewer(client):
    r, _ = _submit(client, Scenario.AMBIGUOUS_EXCLUSION)
    claim = r.json()
    assert claim["decision"]["route"] == "escalate"
    cid = claim["claim_id"]
    denied = client.post(f"/claims/{cid}/override", json=DECISION, headers=REVIEWER)
    assert denied.status_code == 403
    assert "senior reviewer" in denied.json()["detail"]
    ok = client.post(f"/claims/{cid}/override", json=DECISION, headers=SENIOR)
    assert ok.status_code == 200
    assert ok.json()["override"] == {
        **ok.json()["override"],
        "reviewer": "sam",
        "role": "senior_reviewer",
    }
    events = client.get(f"/claims/{cid}/audit").json()["events"]
    assert events[0]["actor"] == "reviewer:rita"  # who submitted
    assert events[-1]["actor"] == "senior_reviewer:sam"  # who decided


def test_reviewer_can_decide_non_escalated_claims(client):
    r, _ = _submit(client, Scenario.PED_WITHIN_WAITING)
    claim = r.json()
    assert claim["decision"]["route"] == "human_verify"
    res = client.post(f"/claims/{claim['claim_id']}/override", json=DECISION, headers=REVIEWER)
    assert res.status_code == 200


def test_settings_switch_models_and_are_versioned(client):
    s = client.get("/settings").json()
    assert s["settings"]["doc_classifier"] == "tfidf_logreg"
    assert s["settings"]["anomaly_detector"] == "hybrid"
    ids = {o["id"] for o in s["catalog"]["claude_model"]}
    assert ids == {"claude-haiku-4-5", "claude-sonnet-5-5", "claude-opus-5-5"}

    new = {**s["settings"], "doc_classifier": "keyword", "anomaly_detector": "rules"}
    assert client.put("/settings", json=new, headers=REVIEWER).status_code == 403
    r = client.put("/settings", json=new, headers=SENIOR)
    assert r.status_code == 200
    assert r.json()["version"] > s["version"]
    assert r.json()["updated_by"] == "senior_reviewer:sam"

    claim, _ = _submit(client, Scenario.CLEAN, seed=9)
    assert claim.json()["decision"]["models_used"]["anomaly_detector"] == "rules"
    assert client.get("/settings/history").json()[0]["updated_by"] == "senior_reviewer:sam"

    bad = {**new, "anomaly_detector": "magic"}
    assert client.put("/settings", json=bad, headers=SENIOR).status_code == 422
    client.put("/settings", json=s["settings"], headers=SENIOR)  # restore


def test_unavailable_reasoner_fails_closed(client, monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    s = client.get("/settings").json()["settings"]
    r = client.put(
        "/settings",
        json={**s, "reasoner_provider": "ollama", "ollama_url": "http://127.0.0.1:9"},
        headers=SENIOR,
    )
    assert r.json()["active_models"]["clause_reasoner"] == "ollama:qwen3:8b"
    res, _ = _submit(client, Scenario.AMBIGUOUS_EXCLUSION, seed=4)
    d = res.json()["decision"]
    assert d["route"] == "escalate" and not d["ai_assisted"]  # call failed -> no suggestion
    client.put("/settings", json=s, headers=SENIOR)


def test_samples_round_trip(client):
    names = {s["scenario"] for s in client.get("/samples").json()}
    assert "padded_pharmacy" in names
    sample = client.get("/samples/clean", params={"seed": 3}).json()
    r = client.post(
        "/claims",
        json={"policy_id": sample["policy_id"], "documents": sample["documents"]},
        headers=REVIEWER,
    )
    assert r.json()["decision"]["payable_amount"] == sample["expected_payable"]
    assert client.get("/samples/nonsense").status_code == 422


def _pdf(text: str) -> bytes:
    """Minimal single-page PDF with a text layer."""
    lines = text.splitlines()
    ops = (
        "BT /F1 10 Tf 40 800 Td 12 TL "
        + " ".join(f"({ln.replace('(', '[').replace(')', ']')}) Tj T*" for ln in lines)
        + " ET"
    )
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(ops)} >>\nstream\n{ops}\nendstream",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


def test_upload_pdf_and_text(client):
    sc = generate_claim(random.Random(2), 0, Scenario.CLEAN, get_policy("SURAKSHA-SILVER"))
    discharge = next(d for d in sc.documents if d.filename == "discharge_summary.txt")
    bill = next(d for d in sc.documents if d.filename == "final_bill.txt")
    files = [
        ("files", ("discharge.pdf", _pdf(discharge.text), "application/pdf")),
        ("files", ("bill.txt", bill.text.encode(), "text/plain")),
    ]
    out = client.post("/documents/extract", files=files).json()
    assert [d["doc_type"] for d in out] == ["discharge_summary", "invoice"]
    assert out[0]["pages"] == 1 and "DISCHARGE SUMMARY" in out[0]["text"]
    bad = client.post("/documents/extract", files=[("files", ("x.bin", b"\xff\xfe", "x"))])
    assert bad.status_code == 415


def test_analytics_totals_are_consistent(client):
    a = client.get("/analytics", headers=AUDITOR).json()
    assert a["decided"] > 0
    assert sum(a["by_route"].values()) == a["decided"]
    assert sum(a["by_recommendation"].values()) == a["decided"]
    t = a["totals"]
    assert abs(t["claimed"] - t["final_payable"] - t["not_paid"]) < 1
    assert a["reviewer"]["finalised"] >= 1
    assert "doc_classifier" in a["models_used"]
