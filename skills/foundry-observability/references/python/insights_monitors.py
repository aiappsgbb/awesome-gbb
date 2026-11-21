"""Canonical Foundry Insights monitor lifecycle helpers.

Source of truth for the prose example in `../../SKILL.md § Insights monitors (agent_insight_monitors)`.

Requires `azure-ai-projects~=2.11.0` and `azure-identity`. Wraps
`AIProjectClient.agent_insight_monitors` with the two rules that keep a monitor
from silently costing money: always create with `enabled=False`, and always
disable, cancel active runs and delete before removing the agent.

Public API:
    create_disabled_monitor(ops, agent_name, judge_deployment, instructions=None)
    stop_and_delete_monitor(ops, monitor_id, attempts=12, sleep_seconds=10)
    smoke(project_endpoint, judge_deployment) -> dict

Run the lifecycle smoke (create + get + delete, no run, no schedule):
    FOUNDRY_PROJECT_ENDPOINT=... FOUNDRY_MODEL_DEPLOYMENT=... \
        python insights_monitors.py
"""
from __future__ import annotations

import os
import sys
import time
import uuid
from typing import Any

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError

ACTIVE_RUN_STATUSES = {"queued", "in_progress"}


def create_disabled_monitor(
    ops: Any,
    agent_name: str,
    judge_deployment: str,
    instructions: str | None = None,
) -> Any:
    """Create a monitor with scheduling OFF; runs start only on explicit request."""
    from azure.ai.projects.models import AgentInsightPriorities

    return ops.create(
        agent_name=agent_name,
        model_deployment_name=judge_deployment,
        enabled=False,
        priorities=AgentInsightPriorities(categories=[], instructions=instructions or ""),
    )


def _status(run: Any) -> str:
    value = getattr(run.status, "value", run.status)
    return str(value).lower()


def stop_and_delete_monitor(
    ops: Any,
    monitor_id: str,
    attempts: int = 12,
    sleep_seconds: float = 10,
) -> None:
    """Disable the schedule, cancel active runs, delete, then prove the 404.

    Disabling does not cancel a run already in progress, and deleting a monitor
    with an active run can conflict, so retry until no run is queued or running.
    """
    ops.update(monitor_id, enabled=False)
    for attempt in range(attempts):
        active = [r for r in ops.list_runs(monitor_id, limit=20) if _status(r) in ACTIVE_RUN_STATUSES]
        try:
            for run in active:
                ops.cancel_run(monitor_id, run.id)
            if not active:
                ops.delete(monitor_id)
                break
        except ResourceExistsError:
            if attempt == attempts - 1:
                raise
        time.sleep(sleep_seconds)
    else:
        raise TimeoutError(f"monitor {monitor_id} still has active runs after {attempts} attempts")
    try:
        ops.get(monitor_id)
    except ResourceNotFoundError:
        return
    raise RuntimeError(f"monitor {monitor_id} still exists after delete")


def smoke(project_endpoint: str, judge_deployment: str) -> dict:
    """Create a temporary external agent + disabled monitor, read it back, delete both."""
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import ExternalAgentDefinition
    from azure.identity import DefaultAzureCredential

    agent_name = f"ci-insights-{uuid.uuid4().hex[:8]}"
    result: dict = {"agent": agent_name, "monitor": None, "enabled": None, "cleanup": "pending"}
    with DefaultAzureCredential() as cred, AIProjectClient(endpoint=project_endpoint, credential=cred) as client:
        ops = client.agent_insight_monitors
        agent = None
        monitor_id = None
        try:
            agent = client.agents.create_version(
                agent_name=agent_name,
                definition=ExternalAgentDefinition(otel_agent_id=agent_name),
                description="Temporary external agent for an insights monitor lifecycle smoke.",
            )
            monitor = create_disabled_monitor(ops, agent.name, judge_deployment)
            monitor_id = monitor.id
            fetched = ops.get(monitor_id)
            result.update(
                monitor=monitor_id,
                enabled=fetched.enabled,
                judge=fetched.model_deployment_name,
                run_interval_hours=fetched.run_interval_hours,
            )
            if fetched.enabled is not False:
                raise RuntimeError(f"monitor {monitor_id} has enabled={fetched.enabled}, expected False")
            if fetched.agent_name != agent.name:
                raise RuntimeError(f"monitor bound to {fetched.agent_name}, expected {agent.name}")
        finally:
            if monitor_id:
                stop_and_delete_monitor(ops, monitor_id)
            if agent is not None:
                client.agents.delete(agent.name, force=True)
                try:
                    client.agents.get(agent.name)
                    raise RuntimeError(f"agent {agent.name} still exists after delete")
                except ResourceNotFoundError:
                    pass
            result["cleanup"] = "deleted"
    return result


if __name__ == "__main__":
    out = smoke(os.environ["FOUNDRY_PROJECT_ENDPOINT"], os.environ["FOUNDRY_MODEL_DEPLOYMENT"])
    print(f"INSIGHTS_SMOKE {out}")
    sys.exit(0 if out.get("cleanup") == "deleted" and out.get("enabled") is False else 1)
