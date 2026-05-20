# GHCP CLI / Cowork dev-loop recipes

This document captures the recommended dev-loops for running a
Threadlight PoC under specifically:

- **GitHub Copilot CLI** (the `copilot` command — what you're
  most likely using right now)
- **GHCP "Cowork"** mode — multiple parallel CLI agents working on
  the same PoC repo
- **Clawpilot** — Anthropic Claude Code (for users who run the same
  PoC under both)

All three are stateless agent-style CLIs that benefit from the same
3-pattern split documented in `SKILL.md`. The differences are in
how you wire MCP and how you structure the multi-agent fanout.

---

## Recipe A — Single CLI, tool-first (most common)

For one developer iterating on tools.

```powershell
# Terminal 1: MCP server
cd <poc-root>/src/mcp_server
uv run python main.py

# Terminal 2: register + open CLI
copilot mcp add <poc>-local --url http://localhost:8000/mcp
copilot

# Inside CLI:
> /mcp <poc>-local list_tools
> "Call get_case dc001 and tell me what's in the evidence array"
> # ... read response, edit tool, ask again ...
```

This recipe is described in detail in
`copilot_mcp_register.md`.

---

## Recipe B — Two parallel CLIs (Cowork-style)

Agent A iterates on the **MCP server**; Agent B iterates on the
**workspace UI**. They share the PoC repo but should NOT share
the running services (port collisions).

```
Terminal 1                Terminal 2                Terminal 3 (CLI A)        Terminal 4 (CLI B)
──────────                ──────────                ──────────────────        ──────────────────
MCP server                Cosmos emulator           copilot                   copilot
:8000                     :8081                     mcp: <poc>-local          (no MCP — UI work)
                                                    "fix get_case to ..."     "tweak the audit-viewer
                                                                              to show signature hash"
```

CLI A talks to the live MCP. CLI B edits files in `src/workspace/`
that nginx (running on :8080 from Pattern 3 compose) auto-serves
on browser-refresh.

> **Cowork tip:** if both CLIs target the same PoC repo, give them
> non-overlapping file scopes. CLI A is responsible for
> `src/mcp_server/` + `tests/`; CLI B for `src/workspace/`.
> Otherwise you'll get merge conflicts on common files
> (`agent.yaml`, `pyproject.toml`).

---

## Recipe C — End-to-end smoke (any CLI, no MCP registration)

When you want the CLI to drive a **full agent invocation** (not just
tools), use Pattern 2's `local_smoke_oneshot.py` and call it as a
shell command:

```
> Run: uv run python tests/local_smoke_oneshot.py "investigate dc001 and recommend"
```

The CLI shells out, captures stdout, summarises. Slower than
Pattern 1 (full agent + LLM round-trip) but exercises the whole
agent code path.

---

## Recipe D — Clawpilot (Claude Code) variant

Claude Code uses the same MCP standard. The registration command
differs:

```powershell
# Add to ~/.claude/mcp.json (manually) or via the UI
{
  "mcpServers": {
    "<poc>-local": {
      "url": "http://localhost:8000/mcp",
      "transport": "streamable-http"
    }
  }
}
```

Otherwise the dev-loop is identical to Recipe A — open Claude Code
in the PoC root, ask it to call tools.

---

## Common pitfalls

- **Two MCP servers, same name, different URLs** → CLI calls the
  first one registered. Use distinct names per process: `<process-a>-local`,
  `<process-b>-local`.
- **MCP server still running after you `Ctrl+C` the terminal** →
  FastMCP catches SIGINT but doesn't always release port 8000
  cleanly. `Get-NetTCPConnection -LocalPort 8000` to find the PID,
  `Stop-Process -Id <pid>`.
- **CLI session cached the MCP tool list before the server reloaded**
  → exit the CLI session, restart. The CLI snapshots the tool
  catalog at session start.
- **Tools work in CLI but break in `local_smoke.py`** → the agent
  uses `MCPStreamableHTTPTool` which needs the
  `parse_tool_results=_mcp_text_extractor` workaround per
  `foundry-hosted-agents`. The CLI's MCP client doesn't have this
  bug. Fix is in the agent code, not the MCP server.

---

## Verifying you're truly local (not hitting cloud)

It's surprisingly easy to think you're testing locally while actually
hitting a deployed Foundry agent. Sanity-check by killing your
internet for 30s and re-running the smoke. If it still works, you
are genuinely local. If it errors with DNS / connectivity issues,
you've got a cloud dependency that wasn't supposed to be there.

For the AOAI call specifically — the agent needs the cloud LLM, so
it WILL break offline. To prove the rest is local: capture an
HTTPS network trace (Fiddler or `mitmproxy`) and confirm the only
outbound destination is your AOAI endpoint hostname.
