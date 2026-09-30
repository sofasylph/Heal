"""Clause reasoner tests. No API key needed: the Anthropic client is faked."""

import json
import random
from types import SimpleNamespace

import pytest
from factories import docs, facts
from fastapi.testclient import TestClient

from claimtrace.api.app import app
from claimtrace.claims import service
from claimtrace.decision.engine import decide
from claimtrace.decision.reasoner import (
    PROMPT_VERSION,
    ClaudeReasoner,
    ResponseCache,
)
from claimtrace.domain.models import (
    ClauseVerdict,
    FindingOutcome,
    ReasonerSuggestion,
    Recommendation,
    ReviewRoute,
)
from claimtrace.evaluation.run import evaluate
from claimtrace.evaluation.synthetic import Scenario, generate_claim, generate_dataset
from claimtrace.policies.registry import get_policy

SILVER = get_policy("SURAKSHA-SILVER")


class FakeClient:
    """Mimics client.beta.messages.create and records every request."""

    def __init__(self, answer=None, stop_reason="end_turn", raises=None, text=None):
        self.calls = []
        self.answer = answer
        self.stop_reason = stop_reason
        self.raises = raises
        self.text = text
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises
        return SimpleNamespace(
            stop_reason=self.stop_reason,
            model=kwargs["model"],
            content=[SimpleNamespace(type="text", text=self.text or json.dumps(self.answer))],
            usage=SimpleNamespace(input_tokens=900, output_tokens=150, cache_read_input_tokens=0),
        )


def answer(verdict: str, confidence: float) -> dict:
    return {
        "verdict": verdict,
        "rationale": "Clause 6.1 excludes treatment to change appearance.",
        "evidence_quotes": ["any treatment to change appearance"],
        "missing_information": [],
        "confidence": confidence,
    }


def ambiguous_facts():
    return facts(diagnosis="Nasal hump, patient request", procedure="Aesthetic nasal reshaping")


def test_request_shape():
    client = FakeClient(answer("applies", 0.9))
    decide(SILVER, ambiguous_facts(), docs(), reasoner=ClaudeReasoner(client=client))
    assert len(client.calls) == 1
    req = client.calls[0]
    assert req["model"] == "claude-opus-5-5"
    assert req["fallbacks"] == "default"
    assert req["betas"] == ["server-side-fallback-2026-07-01"]
    assert req["output_config"]["effort"] == "high"
    assert req["output_config"]["format"]["type"] == "json_schema"
    system = req["system"][0]
    assert system["cache_control"] == {"type": "ephemeral"}
    # the full policy wording, including the exception, is in the cached system prompt
    assert "unless for reconstruction following an accident, burn or cancer" in system["text"]
    assert "Aesthetic nasal reshaping" in req["messages"][0]["content"]


def test_confident_applies_denies_but_needs_human():
    reasoner = ClaudeReasoner(client=FakeClient(answer("applies", 0.92)))
    d = decide(SILVER, ambiguous_facts(), docs(), reasoner=reasoner)
    assert d.recommendation is Recommendation.NOT_PAYABLE
    assert d.route is ReviewRoute.HUMAN_VERIFY
    assert d.ai_assisted
    review = next(f for f in d.findings if f.rule_id == "EXCL-001")
    assert review.outcome is FindingOutcome.REVIEW  # deterministic record preserved
    assert review.suggestion.verdict is ClauseVerdict.APPLIES
    assert review.suggestion.prompt_version == PROMPT_VERSION


def test_confident_does_not_apply_never_goes_straight_through():
    reasoner = ClaudeReasoner(client=FakeClient(answer("does_not_apply", 1.0)))
    d = decide(SILVER, ambiguous_facts(), docs(), reasoner=reasoner)
    assert d.recommendation is Recommendation.PAY
    assert d.route is ReviewRoute.HUMAN_VERIFY


@pytest.mark.parametrize("verdict,conf", [("applies", 0.6), ("uncertain", 0.95)])
def test_unconfident_or_uncertain_stays_escalated(verdict, conf):
    reasoner = ClaudeReasoner(client=FakeClient(answer(verdict, conf)))
    d = decide(SILVER, ambiguous_facts(), docs(), reasoner=reasoner)
    assert d.route is ReviewRoute.ESCALATE
    assert not d.ai_assisted


@pytest.mark.parametrize(
    "client",
    [
        FakeClient(stop_reason="refusal"),
        FakeClient(stop_reason="max_tokens"),
        FakeClient(raises=RuntimeError("connection reset")),
        FakeClient(text="not json"),
        FakeClient(text=json.dumps({"verdict": "maybe", "confidence": 1})),
    ],
)
def test_failures_fail_closed_to_escalation(client):
    d = decide(SILVER, ambiguous_facts(), docs(), reasoner=ClaudeReasoner(client=client))
    assert d.route is ReviewRoute.ESCALATE
    assert all(f.suggestion is None for f in d.findings)


def test_only_ambiguous_eligibility_findings_are_sent():
    client = FakeClient(answer("applies", 0.9))
    decide(SILVER, facts(), docs(), reasoner=ClaudeReasoner(client=client))  # clean claim
    decide(
        SILVER,
        facts(procedure="Cosmetic rhinoplasty"),
        docs(),  # exact-match DENY
        reasoner=ClaudeReasoner(client=client),
    )
    assert client.calls == []


def test_confidence_is_clamped():
    reasoner = ClaudeReasoner(client=FakeClient(answer("applies", 7)))
    d = decide(SILVER, ambiguous_facts(), docs(), reasoner=reasoner)
    assert next(f for f in d.findings if f.suggestion).suggestion.confidence == 1.0


def test_response_cache_replays_without_calling_api(tmp_path):
    path = tmp_path / "cache.jsonl"
    first = FakeClient(answer("applies", 0.9))
    decide(
        SILVER,
        ambiguous_facts(),
        docs(),
        reasoner=ClaudeReasoner(client=first, cache=ResponseCache(path)),
    )
    assert len(first.calls) == 1

    second = FakeClient(raises=AssertionError("should not be called"))
    d = decide(
        SILVER,
        ambiguous_facts(),
        docs(),
        reasoner=ClaudeReasoner(client=second, cache=ResponseCache(path)),
    )
    s = next(f for f in d.findings if f.suggestion).suggestion
    assert s.cached_response and s.verdict is ClauseVerdict.APPLIES


class AdversarialReasoner:
    """Always confidently says the clause does not apply, whatever the truth."""

    name = "adversarial"

    def suggest(self, finding, facts, policy, documents):
        return ReasonerSuggestion(
            verdict=ClauseVerdict.DOES_NOT_APPLY,
            rationale="x",
            confidence=1.0,
            model="fake",
            prompt_version="t",
            input_sha256="0",
        )


def test_even_a_wrong_confident_model_cannot_cause_straight_through():
    report = evaluate(generate_dataset(n=150, seed=5), AdversarialReasoner())
    assert report["reasoner"]["suggestions"] > 0
    assert report["unsafe_straight_through_pct"] == 0.0
    assert report["escalation_recall_pct"] == 100.0


def test_llm_suggestion_is_written_to_audit_trail(monkeypatch):
    fake = ClaudeReasoner(client=FakeClient(answer("applies", 0.9)))
    monkeypatch.setattr(service, "_reasoner", lambda: fake)
    sc = generate_claim(random.Random(4), 9100, Scenario.AMBIGUOUS_EXCLUSION, SILVER)
    with TestClient(app) as client:
        body = {"policy_id": sc.policy_id, "documents": [d.model_dump() for d in sc.documents]}
        claim = client.post("/claims", json=body).json()
        assert claim["decision"]["ai_assisted"] is True
        trail = client.get(f"/claims/{claim['claim_id']}/audit").json()
    actions = [e["action"] for e in trail["events"]]
    assert "llm_suggested" in actions
    assert trail["chain_valid"]
    event = next(e for e in trail["events"] if e["action"] == "llm_suggested")
    assert event["actor"] == "llm:claude-opus-5-5"
    assert event["payload"]["suggestion"]["input_sha256"]
