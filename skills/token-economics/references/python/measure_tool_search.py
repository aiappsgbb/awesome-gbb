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
        [--tools-file my_tools.json (--expect-tool <name> | --cases cases.jsonl)]
        [--session] [--cached-ratio 0.1 --output-ratio 8]

Multi-case mode: ``--cases cases.jsonl`` (one {"prompt", "expect_tool"} per
line) reports tool-selection success per variant; ``--session`` chains the
cases as turns of one conversation to observe caching across a session.
``--cached-ratio``/``--output-ratio`` (and ``--cache-write-ratio`` for GPT-5.6+)
add an input-equivalent cost estimate.

Exit codes: 0 = deferred variant called every expected tool; 1 = it missed at
least one (selection regression); 2 = configuration/API/input error (for
example HTTP 400 on a pre-gpt-5.4 model).
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
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


def make_client(endpoint: str, tenant: str | None = None, timeout: float = 120.0) -> OpenAI:
    credential = AzureCliCredential(tenant_id=tenant) if tenant else DefaultAzureCredential()
    return OpenAI(
        base_url=openai_base_url(endpoint),
        api_key=get_bearer_token_provider(credential, SCOPE),
        timeout=timeout,
        max_retries=2,
    )


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
        # GPT-5.6+ Standard: subset of input_tokens billed at the cache-write rate.
        "cache_write_tokens": getattr(in_details, "cache_write_tokens", 0) or 0,
        "output_tokens": u.output_tokens,
        "reasoning_tokens": getattr(out_details, "reasoning_tokens", 0) or 0,
    }


def _tool_names(tools: list[Any]) -> list[str]:
    """Function names inside tool_search_output (namespaces flattened)."""
    names = []
    for tool in tools:
        t = tool if isinstance(tool, dict) else tool.model_dump()
        if t.get("type") == "namespace":
            names += [member.get("name") for member in t.get("tools", [])]
        elif t.get("name"):
            names.append(t["name"])
    return names


def run_case(
    client: OpenAI, model: str, history: list[Any], prompt: str, tools: list[dict[str, Any]], effort: str,
    max_inferences: int = 6,
) -> dict[str, Any]:
    """Append one user turn to ``history`` and run the tool loop statelessly (store=False).

    Every function call receives a synthetic output, so the loop measures the
    complete turn: discovery, call(s) and the final answer.
    """
    common = {
        "model": model,
        "tools": tools,
        "parallel_tool_calls": False,
        "reasoning": {"effort": effort},
        "store": False,
        "include": ["reasoning.encrypted_content"],
    }
    history.append({"role": "user", "content": prompt})
    inferences, called, searched, loaded = [], [], [], []
    started = time.perf_counter()
    for _ in range(max_inferences):
        response = client.responses.create(input=history, **common)
        inferences.append(_usage(response))
        history += [o.model_dump(exclude_none=True) for o in response.output]
        searched += [o.arguments for o in response.output if o.type == "tool_search_call"]
        loaded += [name for o in response.output if o.type == "tool_search_output" for name in _tool_names(o.tools)]
        calls = [o for o in response.output if o.type == "function_call"]
        if not calls:
            break
        called += [c.name for c in calls]
        history += [
            {"type": "function_call_output", "call_id": c.call_id, "output": json.dumps({"status": "ok", "data": "synthetic"})}
            for c in calls
        ]
    return {
        "inferences": inferences,
        "called_tools": called,
        "tool_search_arguments": searched,
        "loaded_tools": sorted(set(loaded)),
        "elapsed_s": round(time.perf_counter() - started, 2),
    }


def run_variant(
    client: OpenAI, model: str, cases: list[dict[str, str]], tools: list[dict[str, Any]], effort: str, session: bool,
) -> dict[str, Any]:
    """Run all cases; ``session=True`` chains them as successive turns of one conversation."""
    history: list[Any] = []
    results = []
    for case in cases:
        if not session:
            history = []
        result = run_case(client, model, history, case["prompt"], tools, effort)
        result["expect_tool"] = case["expect_tool"]
        result["success"] = case["expect_tool"] in result["called_tools"]
        # Distinguishes "never found" from "found but asked the user for input".
        result["expected_loaded"] = case["expect_tool"] in result["loaded_tools"]
        results.append(result)
    inferences = [i for r in results for i in r["inferences"]]
    return {
        "cases": results,
        "inferences": inferences,
        "totals": {k: sum(i[k] for i in inferences) for k in inferences[0]},
        "called_tools": [t for r in results for t in r["called_tools"]],
        "tool_search_arguments": [a for r in results for a in r["tool_search_arguments"]],
        "successes": sum(r["success"] for r in results),
        "found_not_called": sum((not r["success"]) and r["expected_loaded"] for r in results),
        "elapsed_s": round(sum(r["elapsed_s"] for r in results), 2),
    }


def input_equivalent(totals: dict[str, int], cached_ratio: float, output_ratio: float, write_ratio: float = 1.0) -> float:
    """Cost in uncached-input-token units: U + c*C + w*W + r*O.

    ``cached_tokens`` and ``cache_write_tokens`` are both subsets of
    ``input_tokens``; W is billed at ``write_ratio`` (1.25 on GPT-5.6+ Standard,
    1.0 where writes are not charged separately).
    """
    cached, written = totals["cached_tokens"], totals.get("cache_write_tokens", 0)
    uncached = totals["input_tokens"] - cached - written
    cost = uncached + cached_ratio * cached + write_ratio * written + output_ratio * totals["output_tokens"]
    return round(cost, 1)


def compare(
    client: OpenAI, model: str, tools: list[dict[str, Any]], cases: list[dict[str, str]] | str,
    effort: str = "low", session: bool = False, cached_ratio: float | None = None, output_ratio: float | None = None,
    write_ratio: float = 1.0,
) -> dict[str, Any]:
    if isinstance(cases, str):  # single prompt, demo expectation
        cases = [{"prompt": cases, "expect_tool": DEMO_EXPECTED_TOOL}]
    eager = run_variant(client, model, cases, tools, effort, session)
    deferred = run_variant(client, model, cases, to_deferred(tools), effort, session)
    e_in, d_in = eager["totals"]["input_tokens"], deferred["totals"]["input_tokens"]
    report = {
        "model": model,
        "cases": len(cases),
        "session": session,
        "eager": eager,
        "deferred": deferred,
        "input_token_change_pct": round(100.0 * (d_in - e_in) / e_in, 1) if e_in else None,
        "output_token_delta": deferred["totals"]["output_tokens"] - eager["totals"]["output_tokens"],
    }
    if cached_ratio is not None and output_ratio is not None:
        e_cost = input_equivalent(eager["totals"], cached_ratio, output_ratio, write_ratio)
        d_cost = input_equivalent(deferred["totals"], cached_ratio, output_ratio, write_ratio)
        report["input_equivalent_cost"] = {"eager": e_cost, "deferred": d_cost,
                                           "change_pct": round(100.0 * (d_cost - e_cost) / e_cost, 1)}
    return report


def load_cases(path: str) -> list[dict[str, str]]:
    """JSON Lines: one {"prompt": ..., "expect_tool": ...} object per line."""
    with open(path, encoding="utf-8") as fh:
        cases = [json.loads(line) for line in fh if line.strip()]
    if not cases or any(not c.get("prompt") or not c.get("expect_tool") for c in cases):
        raise ValueError("every case needs non-empty 'prompt' and 'expect_tool'")
    return cases


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--endpoint", default=os.getenv("AZURE_OPENAI_ENDPOINT") or os.getenv("FOUNDRY_PROJECT_ENDPOINT"))
    p.add_argument("--model", required=True, help="Deployment name of a gpt-5.4-or-later model")
    p.add_argument("--tenant", help="Use AzureCliCredential for this tenant instead of DefaultAzureCredential")
    p.add_argument("--tools-file", help="JSON array of Responses tool definitions (default: synthetic demo catalog)")
    p.add_argument("--prompt", default=DEMO_PROMPT)
    p.add_argument("--expect-tool", help="Tool the deferred variant must call (required with --tools-file)")
    p.add_argument("--cases", help="JSONL of {prompt, expect_tool}; overrides --prompt/--expect-tool")
    p.add_argument("--session", action="store_true", help="Chain cases as turns of one conversation")
    p.add_argument("--cached-ratio", type=float, help="Cached/uncached input price ratio, e.g. 0.1")
    p.add_argument("--output-ratio", type=float, help="Output/uncached input price ratio, e.g. 6")
    p.add_argument("--cache-write-ratio", type=float, default=1.0,
                   help="Cache-write/uncached input price ratio (1.25 on GPT-5.6+ Standard)")
    p.add_argument("--effort", default="low", choices=["none", "minimal", "low", "medium", "high"])
    a = p.parse_args(argv)
    if not a.endpoint:
        p.error("--endpoint (or AZURE_OPENAI_ENDPOINT / FOUNDRY_PROJECT_ENDPOINT) is required")
    if a.tools_file and not (a.expect_tool or a.cases):
        p.error("--expect-tool or --cases is required with --tools-file")
    if (a.cached_ratio is None) != (a.output_ratio is None):
        p.error("--cached-ratio and --output-ratio must be given together")

    try:
        if a.tools_file:
            with open(a.tools_file, encoding="utf-8") as fh:
                tools = json.load(fh)
        else:
            tools = build_demo_catalog()
        cases = load_cases(a.cases) if a.cases else [{"prompt": a.prompt, "expect_tool": a.expect_tool or DEMO_EXPECTED_TOOL}]
        report = compare(make_client(a.endpoint, a.tenant), a.model, tools, cases, a.effort, a.session,
                         a.cached_ratio, a.output_ratio, a.cache_write_ratio)
    except Exception as exc:  # API/config/input errors (e.g. HTTP 400 on unsupported models)
        print(json.dumps({"error": type(exc).__name__, "detail": str(exc)[:500]}, indent=2))
        return 2
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["deferred"]["successes"] == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
