"""Canonical Day-1 smoke-test runner for hosted-agent + MCP-tool pilots.

Source of truth for the prose example in `../../SKILL.md § Day-1 Smoke
Test Recipe (hosted-agent + MCP-tool pilots)`.

Why this exists: before running continuous evals or merging to production,
you need a 30-second sanity check that the agent picks the right tool on a
real demo prompt. This script does that with the smallest possible eval
config — one prompt, one built-in evaluator (`tool_selection`), one binary
decision.

Usage:
    # 1. Pick ONE representative prompt from spec.md § Demo Scenarios
    PROMPT="What's the weather in Tokyo?"

    # 2. Run the smoke
    python eval_runner.py "$PROMPT"

    # 3. Decision:
    #    tool_selection >= 0.7  → proceed to full eval suite
    #    tool_selection <  0.7  → agent is picking wrong tools; debug

Pre-conditions:
    AZURE_AI_PROJECT_ENDPOINT — set by azd env (Bicep output)
    Default credentials available (DefaultAzureCredential chain)

This is the canonical recipe from agentic-loop SKILL Validation history
row 4 (learn-assistant 2026-05-28). Used as the day-1 gate in every
subsequent from-scratch pilot.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


def invoke_and_capture(prompt: str) -> str | None:
    """Step 1: invoke the agent + capture the run_id from the CLI."""
    cmd = ["azd", "ai", "agent", "invoke", "--new-conversation", prompt]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"FAIL: invoke errored: {result.stderr}", file=sys.stderr)
        return None
    # Output format: 'run_id: <id>\n...response...'
    for line in result.stdout.splitlines():
        if line.startswith("run_id:"):
            return line.split(":", 1)[1].strip()
    print("FAIL: no run_id in invoke output", file=sys.stderr)
    return None


def smoke_score(prompt: str, run_id: str) -> dict:
    """Steps 2-3: create a 1-item eval with builtin.tool_selection."""
    client = AIProjectClient(
        endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
        credential=DefaultAzureCredential(),
    )
    eval_def = client.evals.create(
        name="smoke-test-tool-selection",
        description="Day-1 smoke test — validate tool selection on real scenario",
        evaluators=[{"evaluator_id": "builtin.tool_selection"}],
    )
    result = client.evals.runs.create(
        eval_id=eval_def.id,
        name=f"smoke-{run_id}",
        data_source={
            "type": "jsonl",
            "source": {
                "type": "file_content",
                "content": [{"item": {"prompt": prompt}}],
            },
        },
    )
    return result.metrics


def decide(metrics: dict) -> int:
    """Step 4: pass/fail gate on tool_selection >= 0.7."""
    score = metrics.get("tool_selection", 0.0)
    print(f"\n=== Smoke results ===")
    print(f"  tool_selection: {score:.2f}")
    if score >= 0.7:
        print("✓ PASS — proceed to full eval suite")
        return 0
    else:
        print("✗ FAIL — agent picking wrong tools; debug before merging")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("prompt", help="A representative demo-scenario prompt")
    args = parser.parse_args()

    run_id = invoke_and_capture(args.prompt)
    if run_id is None:
        return 1
    print(f"run_id: {run_id}")
    metrics = smoke_score(args.prompt, run_id)
    return decide(metrics)


if __name__ == "__main__":
    sys.exit(main())
