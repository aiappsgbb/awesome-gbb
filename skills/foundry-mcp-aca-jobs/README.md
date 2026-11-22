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
│   └── bicepconfig.json
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

ACA Easy Auth caller allowlisting always emits `allowedApplications` from the
required caller client IDs; optional principal object IDs add
`allowedPrincipals.identities`, ANDed with it. Container Apps treats an omitted
`allowedApplications` as `[]` and returns `403` for every caller, so a
principal-only allowlist never works. Hosted agent callers are allowlisted by
both their instance identity client ID and object ID.

The CI fixture has an explicit **standing-resource reuse** path, separate from
the normal subscription-scope consumer. `templates/infra/ci-reuse.bicep`
composes the existing modules and `templates/infra/scripts/ci_reuse.py` gates
exact resources/identities/endpoints/permissions before any write. It uses an
existing RG, identities and database; only the UUID app/Job/control container,
blob containers and image are temporary. No shared role/grant/network
provisioning is a fallback. Cleanup requires recorded ownership and verified
absence and never deletes the standing database, identities or RG.

See `SKILL.md`'s **Deploy with azd** section and the fixture for exact inputs.
The local candidate is not evidence that the selected CI identities currently
have every prerequisite; verify live audience/binding/access and cleanup on
the approved standing environment before reporting acceptance.

For producer-side MCP hosting without an external worker, use
[`foundry-mcp-aca`](../foundry-mcp-aca/SKILL.md). For the canonical ACA Job
module and azd wiring, use [`azd-patterns`](../azd-patterns/SKILL.md).
