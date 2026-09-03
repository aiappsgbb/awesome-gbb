# foundry-mcp-aca-jobs

ACA Job-backed companion to `foundry-mcp-aca`.

## File map

| File | Purpose |
|---|---|
| `SKILL.md` | Canonical contract: when to use, architecture, protocol, lifecycle, security, errors, and test expectations. |
| `references/` | Canonical Python modules and the upstream pin contract. |
| `templates/` | Copy-verbatim azd/Bicep/Dockerfile/script templates for the shared-image ACA Job pattern. |

## Install

Install the catalog plugin from the repo root:

```bash
copilot plugin install awesome-gbb@awesome-gbb
```

## Use

Use this skill when the MCP server should stay responsive and an ACA Job should
do the real work. The server handles Tasks, compatibility tools, callbacks, and
state; the job handles execution and writes the durable result URL.

For producer-side MCP hosting without an external worker, use
[`foundry-mcp-aca`](../foundry-mcp-aca/SKILL.md). For the canonical ACA Job
module and azd wiring, use [`azd-patterns`](../azd-patterns/SKILL.md).
