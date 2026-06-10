"""Canonical blue-green / canary / rollback patterns for Foundry hosted agents.

Source of truth for the prose example in
`../../SKILL.md § Version rollout patterns (blue-green / canary / rollback)`.

Demonstrates the **native** Foundry platform traffic-routing primitives —
NOT a client-side router. Each `create_version` call yields an immutable
version; `patch_agent_details(agent_endpoint=...)` weights traffic across
versions via `FixedRatio` rules summing to 100 %.

Requires:
- azure-ai-projects ~= 2.1.0
- azure-identity ~= 1.25.3
- Environment variables: FOUNDRY_PROJECT_ENDPOINT, AGENT_NAME, NEW_IMAGE

Usage:
    export FOUNDRY_PROJECT_ENDPOINT=https://<acct>.services.ai.azure.com/api/projects/<proj>
    export AGENT_NAME=my-agent
    export NEW_IMAGE=myregistry.azurecr.io/my-agent@sha256:def...
    python version_rollout.py blue-green
    python version_rollout.py canary 1            # prior version is "1"
    python version_rollout.py rollback 1          # revert to version "1"

The script is preview-feature-aware: the SDK calls below use
`project.beta.agents.patch_agent_details` which sends the
`Foundry-Features: AgentEndpoints=V1Preview` header server-side.
"""

from __future__ import annotations

import os
import sys
import time

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    AgentEndpoint,
    AgentEndpointProtocol,
    FixedRatioVersionSelectionRule,
    HostedAgentDefinition,
    ProtocolVersionRecord,
    VersionSelector,
)
from azure.identity import DefaultAzureCredential


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"missing required env var: {name}")
    return value


def wait_for_active(
    project: AIProjectClient,
    agent_name: str,
    agent_version: str,
    max_attempts: int = 60,
    sleep_seconds: float = 10.0,
) -> None:
    """Poll until status == 'active' (typically 2-5 minutes).

    Raises on 'failed' or timeout. Idempotent on 'active'.
    """
    for attempt in range(max_attempts):
        time.sleep(sleep_seconds)
        v = project.agents.get_version(agent_name=agent_name, agent_version=agent_version)
        status = v["status"]
        print(f"  v{agent_version} status={status} (attempt {attempt + 1})")
        if status == "active":
            return
        if status == "failed":
            raise RuntimeError(f"Version provisioning failed: {dict(v)}")
    raise RuntimeError(
        f"Timed out waiting for v{agent_version} to reach 'active' "
        f"({max_attempts} * {sleep_seconds}s = {int(max_attempts * sleep_seconds)}s)"
    )


def patch_routing(
    project: AIProjectClient,
    agent_name: str,
    splits: list[tuple[str, int]],
) -> None:
    """Set the agent_endpoint traffic split.

    Args:
        splits: list of (agent_version, traffic_percentage) tuples
                summing to 100 %.
    """
    total = sum(p for _, p in splits)
    if total != 100:
        raise ValueError(f"Traffic percentages must sum to 100, got {total}: {splits}")
    rules = [
        FixedRatioVersionSelectionRule(agent_version=v, traffic_percentage=p)
        for v, p in splits
    ]
    project.beta.agents.patch_agent_details(
        agent_name=agent_name,
        agent_endpoint=AgentEndpoint(
            version_selector=VersionSelector(version_selection_rules=rules),
            protocols=[AgentEndpointProtocol.RESPONSES],
        ),
    )
    print(f"  routed: {splits}")


def create_new_version(
    project: AIProjectClient,
    agent_name: str,
    image: str,
    cpu: str = "1",
    memory: str = "2Gi",
) -> str:
    """Create a new agent version. Returns the version id (e.g. '2').

    Always bumps a `_BUILD_TS` env var to defeat the `create_version`
    deduplication trap documented in SKILL.md §
    `create_version deduplication trap`. Without it, the platform may
    silently return an existing version with identical inputs.
    """
    v = project.agents.create_version(
        agent_name=agent_name,
        definition=HostedAgentDefinition(
            cpu=cpu,
            memory=memory,
            image=image,
            container_protocol_versions=[
                ProtocolVersionRecord(protocol="responses", version="1.0.0"),
            ],
            environment_variables={"_BUILD_TS": str(int(time.time()))},
        ),
    )
    print(f"  created v{v.version} (status: {v['status']})")
    return v.version


def blue_green(project: AIProjectClient, agent_name: str, new_image: str) -> str:
    """Pattern A: atomic 0 → 100 % cutover. Returns new version id."""
    print("== BLUE-GREEN ==")
    new_v = create_new_version(project, agent_name, new_image)
    wait_for_active(project, agent_name, new_v)
    patch_routing(project, agent_name, [(new_v, 100)])
    print(f"  cutover complete; v{new_v} now serves 100 % traffic")
    return new_v


def canary(
    project: AIProjectClient,
    agent_name: str,
    new_image: str,
    prior_version: str,
    ramp: tuple[int, ...] = (10, 50, 100),
    observe_seconds_between_ramps: float = 0.0,
) -> str:
    """Pattern B: gradual ramp (default 10/90 → 50/50 → 100/0).

    `observe_seconds_between_ramps` is 0 by default for CI; in production,
    pass hours / days converted to seconds. Returns new version id.
    """
    print(f"== CANARY (ramp: {ramp}) ==")
    new_v = create_new_version(project, agent_name, new_image)
    wait_for_active(project, agent_name, new_v)
    for new_pct in ramp:
        if new_pct < 100:
            splits = [(prior_version, 100 - new_pct), (new_v, new_pct)]
        else:
            splits = [(new_v, 100)]
        patch_routing(project, agent_name, splits)
        if new_pct < 100 and observe_seconds_between_ramps > 0:
            time.sleep(observe_seconds_between_ramps)
    print(f"  promotion complete; v{new_v} now serves 100 % traffic")
    return new_v


def rollback(
    project: AIProjectClient,
    agent_name: str,
    prior_version: str,
) -> None:
    """Pattern C: immediate revert to a known-good prior version.

    Assumes `prior_version` was NOT deleted. If it was, you must
    `create_new_version()` from the prior image digest first (2-5 min
    cold provision) — which is why production guidance is to keep
    `prior_version` for ≥ 24 h after promotion.
    """
    print(f"== ROLLBACK to v{prior_version} ==")
    patch_routing(project, agent_name, [(prior_version, 100)])
    print(f"  revert complete; v{prior_version} now serves 100 % traffic")


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in {"blue-green", "canary", "rollback"}:
        print("usage: version_rollout.py {blue-green|canary <prior>|rollback <prior>}")
        raise SystemExit(2)

    endpoint = _env("FOUNDRY_PROJECT_ENDPOINT")
    agent_name = _env("AGENT_NAME")
    project = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())

    mode = sys.argv[1]
    if mode == "blue-green":
        blue_green(project, agent_name, _env("NEW_IMAGE"))
    elif mode == "canary":
        if len(sys.argv) < 3:
            raise SystemExit("canary requires a <prior_version> argument")
        canary(project, agent_name, _env("NEW_IMAGE"), prior_version=sys.argv[2])
    elif mode == "rollback":
        if len(sys.argv) < 3:
            raise SystemExit("rollback requires a <prior_version> argument")
        rollback(project, agent_name, prior_version=sys.argv[2])


if __name__ == "__main__":
    main()
