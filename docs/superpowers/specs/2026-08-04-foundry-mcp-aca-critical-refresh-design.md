# Foundry MCP on ACA Critical Refresh - Design

- **Date:** 2026-08-04
- **Status:** Approved after independent specification review
- **Skill:** `foundry-mcp-aca`
- **Current skill version:** `1.2.3`
- **Target skill version:** `1.2.4`
- **PR shape:** one skill source plus generated docs

---

## 1. Decision

Refresh the independently versioned packages without adopting incompatible
MCP 2:

| Package | Target |
|---|---|
| `fastmcp` | `~=2.14.7` |
| `mcp` | `~=1.29.0`, held below 2.0 |
| `azure-mgmt-appcontainers` | `~=5.0.0` |
| `azure-cosmos` | `~=4.16.3` |
| `azure-identity` | `~=1.25.3` |
| `azure-keyvault-secrets` | `~=4.11.0` |
| `aiohttp` | `~=3.13.5` |

MCP 2 is not installable with either FastMCP 2.14.7 or current FastMCP 3.x,
because both require `mcp>=1.24,<2`. Keep the existing FastMCP 3 hold and add
a separate MCP 2 hold.

Adopt App Containers 5.0. The earlier predicted `Job.template` break was
disproved by an executable probe: the hybrid model preserves `job.template`
as an alias of `job.properties.template`, assignment through the alias
updates the nested property, and serialization emits nested `properties`.
Lock that behavior into pin validation rather than documenting a false
breaking change.

---

## 2. Goals and non-goals

### Goals

- Update the package pin and prose table to one truthful version set.
- Cap the skill's documented MCP requirement at `mcp>=1.24,<2`.
- Add a machine-enforced MCP 2 hold backed by `KI-002`.
- Prove App Containers 5 hybrid-model alias and serialization behavior.
- Prove the current Cosmos async `query_items` surface remains available.
- Extend the live fixture to retrieve the deployed Container App with
  `ContainerAppsAPIClient` 5.0 after the MCP transport succeeds.
- Preserve the current azd-first ACA deployment and FastMCP transport. The
  fixture prebuilds the real 8080 image with ACR remote build, then runs
  `azd provision`; it does not use `azd up` because the Bicep image parameter
  is intentionally required and the stock placeholder serves port 80.
- Rebuild generated catalog pages.

### Non-goals

- No FastMCP 3 migration.
- No MCP 2 migration or compatibility shim.
- No new Cosmos account in CI and no claim that the T3 fixture executes a
  Cosmos query.
- No changes to `azd-patterns` or another skill body.
- No plugin version bump; this is a PATCH correction.

The SKILL.md dependency-body edit requires a `[skill-rewrite]` commit tag.
No `[multi-skill]` tag is needed.

---

## 3. Compatibility holds

Preserve the existing FastMCP hold:

```yaml
hold_below: "3.0.0"
hold_reason: KI-001
```

Add the MCP hold:

```yaml
- name: mcp
  version: "1.29.0"
  hold_below: "2.0.0"
  hold_reason: KI-002
```

The same edit adds `KI-002` with `status: open`, sets
`known_issues_count: 2`, and refreshes `last_validated`/`validated_by`;
without the matching open issue the hold fails open. `KI-002` cites the MCP
2 migration guide and records that no released FastMCP
line supports MCP 2. It closes only after a compatible FastMCP release,
successful bounded install, updated canonical imports, and a passing live
MCP roundtrip.

Combining the MCP hold, App Containers 5, and Cosmos 4.16.3 in one PR is
intentional: all changes belong to one skill contract, the disproved
App Containers break removes the original split rationale, and T2/T3 gate the
combined result. Rollback remains all-or-nothing.

---

## 4. App Containers 5 contract

Pin validation will use the real model classes:

```python
from azure.mgmt.appcontainers.models import Container, Job, JobTemplate

template = JobTemplate(
    containers=[Container(name="mcp", image="example.azurecr.io/mcp:latest")]
)
job = Job(location="swedencentral", template=template)
assert job.template.containers[0].image.endswith(":latest")
assert job.properties.template.containers[0].image.endswith(":latest")

replacement = JobTemplate(
    containers=[Container(name="mcp", image="example.azurecr.io/mcp:v2")]
)
job.template = replacement
assert job.properties.template.containers[0].image.endswith(":v2")
assert job.as_dict()["properties"]["template"]["containers"][0]["image"].endswith(":v2")
```

This is a regression assertion, not a new consumer sample in `SKILL.md`.

---

## 5. Validation design

### T0/T1/T2

The pin script explicitly installs all seven bounded packages and asserts:

1. FastMCP resolves with MCP 1.29;
2. the App Containers 5 hybrid-model alias and serialization contract above;
3. `CosmosClient` and async `query_items` remain available;
4. the FastMCP and MCP holds both reference open known issues;
5. frontmatter and prose tables agree for all seven packages.

The App Containers hybrid-model machinery is bundled by
`azure-mgmt-appcontainers` itself. Do not add an `azure-core` floor assertion;
the executable `Job.template` alias and serialization probe is the contract.

### T3

Retain the live ACR remote build plus `azd provision`, `initialize`, and
`tools/list` hard gates. Correct stale fixture prose that still calls this
path `azd up`. After the Container App exists, install the target App
Containers SDK in a workspace-scoped fixture venv and retrieve the UUID-named
app with:

```python
ContainerAppsAPIClient(
    DefaultAzureCredential(), os.environ["AZURE_SUBSCRIPTION_ID"]
).container_apps.get("rg-awesome-gbb-ci", app_name)
```

Install both `azure-mgmt-appcontainers~=5.0.0` and
`azure-identity~=1.25.3` in the fixture venv. Read
`app.properties.latest_revision_name` and
`app.properties.provisioning_state`, and require at least one non-empty value.
This proves the 5.0 management client against the resource created by the
fixture without relying on an optional top-level alias.
Cosmos remains T2 signature coverage because CI has no standing Cosmos
account; the PR must say so explicitly and must not imply live Cosmos proof.

---

## 6. Files

| File | Responsibility |
|---|---|
| `skills/foundry-mcp-aca/SKILL.md` | MCP upper bound and `1.2.4` |
| `skills/foundry-mcp-aca/references/upstream-pin.md` | Pins, holds, model/query probes, corrected prose table |
| `skills/foundry-mcp-aca/test-fixture/consumer_prompt.md` | Live MCP transport plus App Containers 5 retrieval |
| `docs/` | Regenerated static catalog |

---

## 7. Rollback and unblock conditions

Rollback is one revert of the one-skill commit. If App Containers 5 retrieval
fails for a reproducible SDK reason, restore 4.0, add a hold below 5 backed by
a new known issue, and preserve the executable failure evidence.

MCP 2 is unblocked only after a released FastMCP supports it, the documented
server and client imports are migrated, and both pin validation and the live
wire-protocol fixture pass.
