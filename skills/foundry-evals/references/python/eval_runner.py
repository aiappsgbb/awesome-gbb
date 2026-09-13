"""Canonical one-item Foundry evaluation smoke.

Source of truth for `../../SKILL.md § Day-1 Smoke Test Recipe (hosted-agent + MCP-tool pilots)`.

Agent-target mode sends a query to a named Responses-protocol agent. Explicit
invoke-score mode instead scores its captured response. Both use the project's
OpenAI evals sub-client, wait for completion, and require per-item numeric scores.
This coherence smoke does not certify tool selection or production quality.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
import time
import uuid

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


def invoke_and_capture(prompt: str, agent_name: str, *, project_client) -> str:
    """Invoke the selected agent via its Responses endpoint; reject empty output."""
    client = project_client.get_openai_client(agent_name=agent_name)
    response = client.responses.create(input=prompt, stream=False)
    if response.status != "completed" or not response.output_text.strip():
        raise RuntimeError(f"Agent invocation failed or empty: {response.status}")
    return response.output_text


def smoke_score(
    prompt: str,
    response: str | None = None,
    *,
    agent_name: str | None = None,
    agent_version: str | None = None,
    project_client=None,
    judge_model: str | None = None,
    timeout_seconds: float = 300,
    poll_seconds: float = 5,
    name: str | None = None,
    artifact_path: str | Path | None = None,
) -> dict:
    """Run one disposable coherence eval and return its finite numeric metric.

    Without agent_name, response must contain the actual captured agent text.
    With agent_name, only the query is submitted; the service invokes the agent.
    There is deliberately no automatic fallback on service/auth/schema failures.
    """
    if not prompt.strip():
        raise ValueError("A non-empty query is required")
    if not agent_name and (not response or not response.strip()):
        raise ValueError("invoke-score requires a non-empty captured response")
    judge_model = judge_model or os.environ.get("JUDGE_MODEL_DEPLOYMENT")
    if not judge_model:
        raise ValueError("Set JUDGE_MODEL_DEPLOYMENT to an existing chat deployment")
    credential = None
    owns_project = project_client is None
    if owns_project:
        credential = DefaultAzureCredential()
        project_client = AIProjectClient(
            endpoint=os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
            or os.environ["AZURE_AI_PROJECT_ENDPOINT"],
            credential=credential,
        )
    client = project_client.get_openai_client()
    eval_id = None
    run_id = None
    report = {"mode": "agent-target" if agent_name else "invoke-score"}
    try:
        fields = {"query": {"type": "string"}}
        row = {"query": prompt}
        if not agent_name:
            fields["response"] = {"type": "string"}
            row["response"] = response
        definition = client.evals.create(
            name=name or f"ci-refresh-eval-{uuid.uuid4().hex[:8]}",
            data_source_config={
                "type": "custom",
                "item_schema": {
                    "type": "object", "properties": fields, "required": list(fields),
                },
                "include_sample_schema": True,
            },
            testing_criteria=[{
                "type": "azure_ai_evaluator",
                "name": "coherence",
                "evaluator_name": "builtin.coherence",
                "initialization_parameters": {"deployment_name": judge_model},
                "data_mapping": {
                    "query": "{{item.query}}",
                    "response": "{{sample.output_text}}" if agent_name else "{{item.response}}",
                },
            }],
        )
        eval_id = definition.id
        report["eval_id"] = eval_id
        source = {
            "type": "jsonl",
            "source": {"type": "file_content", "content": [{"item": row}]},
        }
        if agent_name:
            target = {"type": "azure_ai_agent", "name": agent_name}
            if agent_version:
                target["version"] = agent_version
            source.update({
                "type": "azure_ai_target_completions",
                "target": target,
                "input_messages": {
                    "type": "template",
                    "template": [{
                        "type": "message", "role": "user",
                        "content": {"type": "input_text", "text": "{{item.query}}"},
                    }],
                },
            })
        run = client.evals.runs.create(
            eval_id=eval_id, name=f"ci-refresh-eval-run-{uuid.uuid4().hex[:8]}",
            data_source=source,
        )
        run_id = run.id
        report["run_id"] = run_id
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            run = client.evals.runs.retrieve(eval_id=eval_id, run_id=run_id)
            report["status"] = run.status
            if run.status in {"completed", "succeeded"}:
                break
            if run.status in {"failed", "error", "canceled", "cancelled"}:
                report["error"] = str(getattr(run, "error", None))
                raise RuntimeError(f"Evaluation run {run.status}: {report['error']}")
            time.sleep(min(poll_seconds, max(0, deadline - time.monotonic())))
        else:
            raise TimeoutError("Evaluation timed out before a successful terminal state")
        items = [
            item.model_dump()
            for item in client.evals.runs.output_items.list(eval_id=eval_id, run_id=run_id)
        ]
        report["output_items"] = items
        if len(items) != 1:
            raise RuntimeError(f"Expected one scored output item, got {len(items)}")
        item = items[0]
        if item.get("status") in {"failed", "error", "errored"} or (item.get("sample") or {}).get("error"):
            raise RuntimeError("Evaluation output contains an execution error")
        if agent_name:
            generated = (item.get("datasource_item") or {}).get("sample.output_text")
            if not isinstance(generated, str) or not generated.strip():
                raise RuntimeError("Agent-target evaluation returned no generated response")
        scores = [
            result.get("score") for result in items[0].get("results", [])
            if result.get("name") == "coherence" and not result.get("error")
            and result.get("status") not in {"failed", "error", "errored", "running", "queued"}
        ]
        if len(scores) != 1 or isinstance(scores[0], bool) or not isinstance(scores[0], (int, float)):
            raise RuntimeError("Evaluation output has no unambiguous numeric coherence score")
        if not math.isfinite(scores[0]):
            raise RuntimeError("Evaluation output score is not finite")
        report["metrics"] = {"coherence": float(scores[0])}
        return report["metrics"]
    finally:
        if eval_id:
            try:
                client.evals.delete(eval_id)
                report["cleanup"] = "deleted"
            except Exception as exc:
                report["cleanup"] = f"unverified: {type(exc).__name__}"
                print(f"NOTE: eval cleanup unverified; retained eval {eval_id}", file=sys.stderr)
        if artifact_path:
            path = Path(artifact_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        if owns_project:
            close = getattr(project_client, "close", None)
            if close:
                close()
            credential.close()


def decide(metrics: dict, threshold: float = 3.0) -> int:
    """Coherence is scored on a 1-5 scale; the caller owns its quality policy."""
    score = metrics.get("coherence")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
        raise ValueError("Missing or invalid coherence score")
    print(f"coherence={score:.2f} threshold={threshold:.2f}")
    return 0 if score >= threshold else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt")
    parser.add_argument("--agent-name", required=True)
    parser.add_argument("--agent-version")
    parser.add_argument("--mode", choices=["agent-target", "invoke-score"], default="agent-target")
    parser.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL_DEPLOYMENT"))
    parser.add_argument("--threshold", type=float, default=3.0)
    parser.add_argument("--artifact", help="Optional private JSON with per-item evidence")
    args = parser.parse_args()
    if not 1 <= args.threshold <= 5:
        parser.error("--threshold must be on coherence's 1-5 scale")
    if args.mode == "invoke-score" and args.agent_version:
        parser.error("invoke-score uses the agent-bound endpoint; do not imply a pinned version")
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT") or os.environ["AZURE_AI_PROJECT_ENDPOINT"]
    with DefaultAzureCredential() as credential, AIProjectClient(
        endpoint=endpoint, credential=credential
    ) as project:
        response = None
        if args.mode == "invoke-score":
            response = invoke_and_capture(args.prompt, args.agent_name, project_client=project)
        metrics = smoke_score(
            args.prompt, response, project_client=project,
            agent_name=args.agent_name if args.mode == "agent-target" else None,
            agent_version=args.agent_version, judge_model=args.judge_model,
            artifact_path=args.artifact,
        )
    return decide(metrics, args.threshold)


if __name__ == "__main__":
    sys.exit(main())
