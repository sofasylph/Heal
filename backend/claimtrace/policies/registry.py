"""Loads policy definitions from YAML. Policies are versioned, immutable inputs."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from claimtrace.policies.models import Policy

DATA_DIR = Path(__file__).parent / "data"


@lru_cache
def load_policies() -> dict[str, Policy]:
    policies: dict[str, Policy] = {}
    for path in sorted(DATA_DIR.glob("*.yaml")):
        policy = Policy.model_validate(yaml.safe_load(path.read_text()))
        policy.validate_clause_links()
        policies[policy.policy_id] = policy
    return policies


def get_policy(policy_id: str) -> Policy:
    policies = load_policies()
    if policy_id not in policies:
        raise KeyError(f"Unknown policy {policy_id}")
    return policies[policy_id]
