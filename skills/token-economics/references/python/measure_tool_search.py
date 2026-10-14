"""Canonical eager-vs-deferred tool loading measurement for the Responses API.

Source of truth for the prose example in `../../SKILL.md § Measure before and after`.

Runs the SAME task twice against one deployment: once with every tool
definition loaded eagerly, once with `defer_loading: true` plus the hosted
`tool_search` tool. Each variant runs a complete tool turn (request ->
function_call -> synthetic function_call_output -> final request) so the
report covers the whole turn, not only the first inference.

Prints usage counters only. It never logs prompts, tool arguments or
outputs beyond tool names and the tool_search paths.

Usage (Entra ID; the identity needs Cognitive Services OpenAI User):

    python measure_tool_search.py --endpoint https://<resource>.openai.azure.com \
        --model <gpt-5.4-or-later-deployment> [--tenant <tenant-id>] \
        [--tools-file my_tools.json --prompt "..." --expect-tool <name>]

Exit codes: 0 = deferred variant called the expected tool; 1 = it did not;
2 = configuration/API error (for example HTTP 400 on a pre-gpt-5.4 model).
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from typing import Any

from azure.identity import AzureCliCredential, DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

SCOPE = "https://ai.azure.com/.default"

DEMO_DOMAINS = {
    "crm": "Customer records: profiles, contacts, open orders and account notes.",
    "billing": "Invoices, payments, refunds, credit notes and payment plans.",
    "shipping": "Shipments, carriers, tracking, delivery ETAs and returns logistics.",
    "inventory": "Stock levels, warehouses, reorder points and product availability.",
    "hr": "Employee directory, leave balances, org chart and onboarding tasks.",
}
DEMO_VERBS = ("get", "list", "create", "update", "search", "archive")
DEMO_PROMPT = (
    "Use the shipping tools to get the delivery ETA record for shipment SHP-42 "
    "(field_0=SHP-42). Call the tool; do not answer from memory."
)
DEMO_EXPECTED_TOOL = "get_shipping_record"


def openai_base_url(endpoint: str) -> str:
    """Accept a resource endpoint or a Foundry project endpoint; return the /openai/v1/ base."""
    endpoint = endpoint.strip().rstrip("/")
    if "/api/projects/" in endpoint:
        endpoint = endpoint.split("/api/projects/")[0]
    if endpoint.endswith("/openai/v1"):
        return endpoint + "/"
    return endpoint + "/openai/v1/"


def make_client(endpoint: str, tenant: str | None = None) -> OpenAI:
    credential = AzureCliCredential(tenant_id=tenant) if tenant else DefaultAzureCredential()
    return OpenAI(base_url=openai_base_url(endpoint), api_key=get_bearer_token_provider(credential, SCOPE))


def build_demo_catalog() -> list[dict[str, Any]]:
    """Synthetic 30-function catalog in 5 namespaces (6 functions each, under the <10 guidance)."""
    catalog = []
    for ns, description in DEMO_DOMAINS.items():
        tools = []
        for verb in DEMO_VERBS:
            props = {
                f"field_{i}": {
                    "type": "string",
                    "description": f"Field {i} for {ns}: accepted formats, validation rules and examples.",
                }
                for i in range(6)
            }
            tools.append({
                "type": "function",
                "name": f"{verb}_{ns}_record",
                "description": f"{verb.title()} a {ns} record. " + "Detailed behaviour notes. " * 6,
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": list(props),
                    "additionalProperties": False,
                },
            })
        catalog.append({"type": "namespace", "name": ns, "description": description, "tools": tools})
    return catalog


def to_deferred(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a copy with defer_loading on functions/namespace members/MCP servers, plus tool_search."""
    out = copy.deepcopy(tools)
    for tool in out:
        kind = tool.get("type")
        if kind in ("function", "mcp"):
            tool["defer_loading"] = True
        elif kind == "namespace":
            # defer_loading applies to functions inside the namespace, not the namespace object.
            for member in tool.get("tools", []):
                if member.get("type") == "function":
                    member["defer_loading"] = True
    if not any(t.get("type") == "tool_search" for t in out):
        out.append({"type": "tool_search"})
    return out


def _usage(response: Any) -> dict[str, int]:
    u = response.usage
    in_details = getattr(u, "input_tokens_details", None)
    out_details = getattr(u, "output_tokens_details", None)
    return {
        "input_tokens": u.input_tokens,
        "cached_tokens": getattr(in_details, "cached_tokens", 0) or 0,
        "output_tokens": u.output_tokens,
        "reasoning_tokens": getattr(out_details, "reasoning_tokens", 0) or 0,
    }


def run_turn(client: OpenAI, model: str, prompt: str, tools: list[dict[str, Any]], effort: str) -> dict[str, Any]:
    """Run one complete tool turn statelessly (store=False) and return per-inference usage."""
    common = {
        "model": model,
        "tools": tools,
        "parallel_tool_calls": False,
        "reasoning": {"effort": effort},
        "store": False,
        "include": ["reasoning.encrypted_content"],
    }
    history: list[Any] = [{"role": "user", "content": prompt}]
    first = client.responses.create(input=history, **common)
    inferences = [_usage(first)]
    calls = [o for o in first.output if o.type == "function_call"]
    searched = [o.arguments for o in first.output if o.type == "tool_search_call"]

    if calls:
        history += [o.model_dump(exclude_none=True) for o in first.output]
        history += [
            {"type": "function_call_output", "call_id": c.call_id, "output": json.dumps({"status": "ok", "eta": "synthetic"})}
            for c in calls
        ]
        second = client.responses.create(input=history, **common)
        inferences.append(_usage(second))

    totals = {k: sum(i[k] for i in inferences) for k in inferences[0]}
    return {
        "inferences": inferences,
        "totals": totals,
        "called_tools": [c.name for c in calls],
        "tool_search_arguments": searched,
    }


def compare(client: OpenAI, model: str, tools: list[dict[str, Any]], prompt: str, effort: str = "low") -> dict[str, Any]:
    eager = run_turn(client, model, prompt, tools, effort)
    deferred = run_turn(client, model, prompt, to_deferred(tools), effort)
    e_in, d_in = eager["totals"]["input_tokens"], deferred["totals"]["input_tokens"]
    return {
        "model": model,
        "eager": eager,
        "deferred": deferred,
        "input_token_change_pct": round(100.0 * (d_in - e_in) / e_in, 1) if e_in else None,
        "output_token_delta": deferred["totals"]["output_tokens"] - eager["totals"]["output_tokens"],
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--endpoint", default=os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("FOUNDRY_PROJECT_ENDPOINT"))
    p.add_argument("--model", required=True, help="Deployment name of a gpt-5.4-or-later model")
    p.add_argument("--tenant", help="Use AzureCliCredential for this tenant instead of DefaultAzureCredential")
    p.add_argument("--tools-file", help="JSON array of Responses tool definitions (default: synthetic demo catalog)")
    p.add_argument("--prompt", default=DEMO_PROMPT)
    p.add_argument("--expect-tool", help="Tool the deferred variant must call (required with --tools-file)")
    p.add_argument("--effort", default="low", choices=["none", "minimal", "low", "medium", "high"])
    a = p.parse_args(argv)
    if not a.endpoint:
        p.error("--endpoint (or AZURE_OPENAI_ENDPOINT / FOUNDRY_PROJECT_ENDPOINT) is required")
    if a.tools_file and not a.expect_tool:
        p.error("--expect-tool is required with --tools-file")
    expect_tool = a.expect_tool or DEMO_EXPECTED_TOOL

    try:
        if a.tools_file:
            with open(a.tools_file, encoding="utf-8") as fh:
                tools = json.load(fh)
        else:
            tools = build_demo_catalog()
        report = compare(make_client(a.endpoint, a.tenant), a.model, tools, a.prompt, a.effort)
    except Exception as exc:  # API/config/input errors (e.g. HTTP 400 on unsupported models)
        print(json.dumps({"error": type(exc).__name__, "detail": str(exc)[:500]}, indent=2))
        return 2
    print(json.dumps(report, indent=2, default=str))
    return 0 if expect_tool in report["deferred"]["called_tools"] else 1


if __name__ == "__main__":
    sys.exit(main())
