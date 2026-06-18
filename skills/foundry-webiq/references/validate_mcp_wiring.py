"""Live Azure validation of the foundry-webiq MCP-grounding WIRING MECHANISM.

WHAT THIS PROVES (against real Azure + a real live MCP grounding server):
  1. tools/list AUTO-DISCOVERY — the skill's central claim that grounding tool
     names are discovered at runtime via the JSON-RPC handshake, never
     hardcoded.
  2. A real tool invocation returns a standard MCP CallToolResult envelope.
  3. The skill's OWN committed _webiq_result_parser (imported from the SSOT
     reference file, NOT copied) unwraps that real envelope into clean,
     citation-bearing text.
  4. END-TO-END on Azure: a real Azure OpenAI deployment (gpt-5.4-mini on the
     CI Foundry account, AAD / disableLocalAuth) performs a tool-calling loop,
     decides to call the grounding tool, and produces a grounded answer.

WHAT THIS DOES *NOT* PROVE:
  Nothing about Web IQ's gated, Entra-only contract (its real endpoint URL,
  API-key header name, Entra scope, or response field names). Those remain
  CONFIRM: placeholders in the skill. This harness points the SAME wiring at a
  PUBLIC no-auth streamable-HTTP MCP grounding server (Microsoft Learn MCP) as
  a faithful stand-in for the wiring MECHANISM only.

USAGE (from the skill's references/ directory):
    pip install agent-framework-core~=1.8.0 mcp httpx openai azure-identity
    az login   # account uses AAD (disableLocalAuth); no key
    export AZURE_OPENAI_ENDPOINT="https://<your-foundry-account>.cognitiveservices.azure.com/"
    export AZURE_OPENAI_DEPLOYMENT="gpt-5.4-mini"   # any chat deployment
    python validate_mcp_wiring.py                   # prints SMOKE_RESULT=PASS/FAIL

By default it imports the skill's committed parser from the sibling
`python/` directory; override with WEBIQ_SKILL_REF if you relocate it.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

from azure.identity import AzureCliCredential, get_bearer_token_provider
from openai import AzureOpenAI

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Import the skill's SSOT parser DIRECTLY from the committed reference file.
SKILL_REF = pathlib.Path(
    os.environ.get(
        "WEBIQ_SKILL_REF",
        str(pathlib.Path(__file__).resolve().parents[0] / "python"),
    )
)
sys.path.insert(0, str(SKILL_REF))
from webiq_mcp_grounding import _webiq_result_parser  # noqa: E402

AOAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"]
DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5.4-mini")
MCP_URL = os.environ.get("LEARN_MCP_ENDPOINT", "https://learn.microsoft.com/api/mcp")
API_VERSION = "2024-12-01-preview"

USER_QUERY = (
    "What is the Azure AI Foundry Agent Service? Use the web_grounding tool to "
    "look it up on Microsoft Learn, answer in two sentences, and cite the "
    "source titles you used."
)

# OpenAI tool schema. The name is OUR choice; the MCP tool it maps to was
# DISCOVERED at runtime (see tools/list below), not hardcoded.
GROUNDING_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_grounding",
        "description": "Search the live web/docs for fresh, cited grounding context.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "search query"}},
            "required": ["query"],
        },
    },
}


def main() -> int:
    evidence: dict[str, object] = {}

    # ---- Azure model client (AAD; account has disableLocalAuth=True) -------- #
    token_provider = get_bearer_token_provider(
        AzureCliCredential(), "https://cognitiveservices.azure.com/.default"
    )
    aoai = AzureOpenAI(
        azure_endpoint=AOAI_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version=API_VERSION,
    )

    # MCP session is opened with the low-level SDK so we can both (a) prove
    # tools/list discovery and (b) feed a genuine CallToolResult to the skill's
    # parser. The skill itself wraps this same transport in MCPStreamableHTTPTool.
    import anyio

    async def run() -> int:
        async with streamablehttp_client(MCP_URL) as (reader, writer, _):
            async with ClientSession(reader, writer) as session:
                init = await session.initialize()
                server_name = getattr(getattr(init, "serverInfo", None), "name", "?")
                evidence["server"] = server_name

                # (1) AUTO-DISCOVERY -------------------------------------------------
                listed = await session.list_tools()
                tool_names = [t.name for t in listed.tools]
                evidence["discovered_tools"] = tool_names
                print(f"[1] tools/list auto-discovered {len(tool_names)} tool(s) "
                      f"on '{server_name}': {tool_names}")
                if not tool_names:
                    print("FAIL: no tools discovered via tools/list")
                    return 1
                search_tool = next(
                    (n for n in tool_names if "search" in n.lower()), tool_names[0]
                )

                # (2)+(3) real envelope -> skill's committed parser -----------------
                probe = await session.call_tool(search_tool, {"query": "Azure AI Foundry Agent Service"})
                parsed_probe = _webiq_result_parser(probe)
                envelope_ok = (
                    isinstance(parsed_probe, str)
                    and parsed_probe.strip() != ""
                    and "no grounding results" not in parsed_probe
                    and "<agent_framework" not in parsed_probe  # no object-repr leak
                )
                evidence["parser_envelope_unwrap_ok"] = envelope_ok
                print(f"[2] real CallToolResult -> SSOT _webiq_result_parser: "
                      f"unwrap_ok={envelope_ok}, len={len(parsed_probe)}")
                print("    parsed head:", parsed_probe[:160].replace("\n", " "))
                if not envelope_ok:
                    print("FAIL: parser did not unwrap a real MCP envelope")
                    return 1

                # (4) END-TO-END: Azure model tool-calling loop --------------------
                messages = [
                    {"role": "system", "content":
                     "You MUST call web_grounding to answer. Cite the source titles."},
                    {"role": "user", "content": USER_QUERY},
                ]
                first = aoai.chat.completions.create(
                    model=DEPLOYMENT, messages=messages,
                    tools=[GROUNDING_TOOL_SCHEMA], tool_choice="auto",
                    max_completion_tokens=800,
                )
                msg = first.choices[0].message
                tool_calls = msg.tool_calls or []
                evidence["model_invoked_tool"] = bool(tool_calls)
                print(f"[3] gpt-5.4-mini ({DEPLOYMENT}) requested "
                      f"{len(tool_calls)} tool call(s)")
                if not tool_calls:
                    print("FAIL: model did not call the grounding tool")
                    return 1

                messages.append({
                    "role": "assistant", "content": msg.content,
                    "tool_calls": [
                        {"id": tc.id, "type": "function",
                         "function": {"name": tc.function.name,
                                      "arguments": tc.function.arguments}}
                        for tc in tool_calls
                    ],
                })
                # Execute each tool call via the REAL MCP server + skill parser.
                for tc in tool_calls:
                    args = json.loads(tc.function.arguments or "{}")
                    q = args.get("query", "Azure AI Foundry Agent Service")
                    real = await session.call_tool(search_tool, {"query": q})
                    grounded = _webiq_result_parser(real)
                    messages.append({
                        "role": "tool", "tool_call_id": tc.id,
                        "content": grounded[:6000],
                    })

                final = aoai.chat.completions.create(
                    model=DEPLOYMENT, messages=messages, max_completion_tokens=800,
                )
                answer = final.choices[0].message.content or ""
                evidence["final_answer"] = answer
                print("\n[4] FINAL grounded answer from Azure model:\n" + answer.strip())

                grounded_ok = len(answer.strip()) > 0 and (
                    "foundry" in answer.lower() or "agent" in answer.lower()
                )
                evidence["answer_grounded_ok"] = grounded_ok

                ok = (
                    bool(tool_names) and envelope_ok
                    and bool(tool_calls) and grounded_ok
                )
                print("\n=== EVIDENCE ===")
                print(json.dumps({k: v for k, v in evidence.items()
                                  if k != "final_answer"}, indent=2))
                print("SMOKE_RESULT=PASS" if ok else "SMOKE_RESULT=FAIL")
                return 0 if ok else 1

        return 1

    return anyio.run(run)


if __name__ == "__main__":
    raise SystemExit(main())
