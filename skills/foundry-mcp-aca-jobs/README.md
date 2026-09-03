# foundry-mcp-aca-jobs

ACA Job-backed companion to `foundry-mcp-aca`.

## File map

| File | Purpose |
|---|---|
| `SKILL.md` | Canonical contract: when to use, architecture, protocol, lifecycle, security, errors, and test expectations. |
| `references/` | Canonical Python modules and the upstream pin contract. |
| `templates/` | Copy-verbatim azd/Bicep/Dockerfile/script templates for the shared-image ACA Job pattern. |

The composition root at
`skills/foundry-mcp-aca-jobs/templates/infra/main.bicep` requires the sibling
catalog checkout layout. Keep `skills/foundry-mcp-aca-jobs/templates` beside
`skills/azd-patterns/references/bicep/aca-job.bicep` under the same checkout:

```text
<workdir>/skills/
├── foundry-mcp-aca-jobs/templates/
└── azd-patterns/references/bicep/aca-job.bicep
```

```bash
WORKDIR="<workdir>"
mkdir -p "$WORKDIR/skills/foundry-mcp-aca-jobs" \
  "$WORKDIR/skills/azd-patterns/references/bicep"
cp -R skills/foundry-mcp-aca-jobs/templates "$WORKDIR/skills/foundry-mcp-aca-jobs/"
cp skills/azd-patterns/references/bicep/aca-job.bicep "$WORKDIR/skills/azd-patterns/references/bicep/"
```

## Install

Install the catalog plugin from the repo root:

```bash
copilot plugin install awesome-gbb@awesome-gbb
```

## Use

Use this skill when the MCP server should stay responsive and an ACA Job should
do the real work. The server handles Tasks, compatibility tools, callbacks, and
state; the job handles execution and writes the durable result URL.

ACA Easy Auth caller allowlisting has two mutually exclusive modes: client ID
mode emits only `allowedApplications`, while principal object ID mode emits
only `allowedPrincipals.identities`. Choose exactly one nonempty list because
the `2025-01-01` authConfig API applies logical AND when both are present.
Hosted agent instance callers use principal object ID mode; client ID mode
remains supported for app-only callers.

For producer-side MCP hosting without an external worker, use
[`foundry-mcp-aca`](../foundry-mcp-aca/SKILL.md). For the canonical ACA Job
module and azd wiring, use [`azd-patterns`](../azd-patterns/SKILL.md).
