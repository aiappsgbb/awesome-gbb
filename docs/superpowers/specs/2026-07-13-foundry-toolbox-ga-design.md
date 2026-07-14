# Design - Foundry announcement audit and `foundry-toolbox` GA migration

- **Date:** 2026-07-13
- **Status:** Approved (design phase)
- **Repository:** `awesome-gbb`
- **First target skill:** `skills/foundry-toolbox/`
- **PR shape:** one skill source per PR
- **First skill version:** `1.6.3` -> `2.0.0`

---

## 1. Executive decision

The July 2026 announcements contain a mix of confirmed GA features,
partially GA feature sets, gated previews, and claims that current public
documentation does not support. The catalog will not apply one broad
"everything is GA" rewrite.

Changes will land one skill at a time. Each skill PR must include its own
pin/reference/fixture changes, generated documentation, and live evidence
before work starts on the next skill.

The first PR is `foundry-toolbox` because its current contract requires a
preview header that Microsoft removed when the Toolbox APIs became GA. It
also teaches the old `.beta.toolboxes` SDK namespace and generic Agent tool
classes that `azure-ai-projects` 2.3.0 replaced with stable Toolbox-specific
classes.

---

## 2. Evidence baseline for the announcement set

| Announcement | Verified public status on 2026-07-13 | Catalog treatment |
|---|---|---|
| GPT-5.6 Sol, Terra, Luna | GA since 2026-07-09; model version `2026-07-09`; phased rollout wording was "over the next 24 hours." Azure pricing and PTU data are not yet public. | Add model IDs and versions only after live Azure availability is proven. Do not invent Azure rates or PTU values. |
| Hosted agents | Current Foundry docs and SDK 2.3 stable methods support a container-GA interpretation, while a current Agent Framework page still says preview. Source-code deployment and some protocols remain preview. | Use a surface-level status matrix, not a blanket GA label. |
| VNet isolation | GA with account-creation-only network injection, same-region and subnet constraints, and a private-ACR behavior split based on project creation date. | Update VNet and network-runbook skills later, with manual Azure evidence where required. |
| Durable tasks | Durable execution is real through the separate Durable Task extension for Microsoft Agent Framework. It is not native Hosted-agent durability. | Track a separate future `agent-framework-durable-task` design; do not add the claim to `foundry-hosted-agents`. |
| Voice Live for Hosted Agents | VoiceLive SDK 1.2.0 is GA. The combined Hosted-agent integration has conflicting status signals and official native-voice samples use preview SDK 1.3.0b1. | Separate SDK status from integration status. |
| Toolboxes | Core Toolbox CRUD, versioning, and MCP endpoint are GA. Stable SDK operations are under `.toolboxes`. The preview opt-in header is removed. Tool Search remains preview. | Immediate major migration of `foundry-toolbox`. |
| Foundry IQ | Partial GA: stable API-level Knowledge Bases and selected sources are SLA-backed. Portal authoring, richer reasoning/synthesis, several sources, Serverless, and integrations remain preview or limited access. | Rebase `foundry-iq` on the stable API in its own PR. |
| Tracing and evaluation | Tracing is GA for prompt and hosted agents; workflow/external tracing remains preview. Core Hosted-agent evaluation is documented, but the whole evaluation surface is not unambiguously labeled GA. | Update `foundry-observability` and replace the obsolete mandatory two-phase premise in `foundry-evals`, each in its own PR. |
| Teams and Microsoft 365 publishing | Official sources conflict between shipped GA, "next week," and Learn pages still marked Early Access Preview. Private-network publishing uses REST plus a customer-controlled public ingress bridge. | Keep native-vs-custom routing in `foundry-teams-bot`; do not create a publishing skill yet. |
| Agent Optimizer | Gated preview. Current docs require allow-list access; "public preview" is not consistently supported by official sources. | Add `foundry-agent-optimizer` only after earlier dependencies are current and the CI subscription is allow-listed. |
| Routines event triggers | Routines are public preview. Public automatic triggers are still `schedule` and `timer`; `CustomRoutineTrigger` is manual dispatch. No connector-gateway contract was found. | Do not document connector event triggers. |
| ROI for Agents | Confirmed private preview with Net Value, Business Value, Total Cost, and Current ROI. | Add bounded handoffs to observability/evals/cost skills; no standalone skill yet. |

### Authoritative sources

- [GPT-5.6 launch](https://openai.com/index/gpt-5-6/)
- [Azure model retirement schedule](https://learn.microsoft.com/azure/foundry/openai/concepts/model-retirement-schedule)
- [Hosted agents](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents)
- [Hosted Agent Framework integration](https://learn.microsoft.com/agent-framework/hosting/foundry-hosted-agent)
- [Foundry virtual networks](https://learn.microsoft.com/azure/foundry/agents/how-to/virtual-networks)
- [Durable Task for AI agents](https://learn.microsoft.com/azure/durable-task/sdks/durable-task-for-ai-agents)
- [Voice agent integration](https://learn.microsoft.com/azure/ai-services/speech-service/how-to-voice-agent-integration)
- [Foundry Toolbox](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox)
- [Tool Search preview](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/tool-search)
- [July 2026 Foundry production-agent announcement](https://azure.microsoft.com/en-us/blog/frontier-models-and-production-agents-advancing-microsoft-foundry-for-the-agentic-era/)
- [`azure-ai-projects` 2.3.0 changelog](https://github.com/Azure/azure-sdk-for-python/blob/main/sdk/ai/azure-ai-projects/CHANGELOG.md)
- [`azure.ai.toolboxes` extension changelog](https://github.com/Azure/azure-dev/blob/main/cli/azd/extensions/azure.ai.toolboxes/CHANGELOG.md)
- [Microsoft Mechanics Tool Search demo](https://www.youtube.com/watch?v=dv-DGHRa_iU)
- [Foundry GA scope](https://learn.microsoft.com/azure/foundry/concepts/general-availability)
- [Foundry IQ overview](https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-foundry-iq)
- [Agent tracing](https://learn.microsoft.com/azure/foundry/observability/concepts/trace-agent-concept)
- [Agent evaluation](https://learn.microsoft.com/azure/foundry/observability/how-to/evaluate-agent)
- [Publish to Copilot and Teams](https://learn.microsoft.com/azure/foundry/agents/how-to/publish-copilot)
- [Private-network publishing](https://learn.microsoft.com/azure/foundry/agents/how-to/publish-copilot-virtual-network)
- [Agent Optimizer](https://learn.microsoft.com/azure/foundry/agents/concepts/agent-optimizer-overview)
- [Routines](https://learn.microsoft.com/azure/foundry/agents/concepts/routines)
- [ROI for Agents announcement](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/introducing-roi-for-agents-in-foundry/4531970)

---

## 3. One-skill-per-PR queue

The approved order is:

1. `foundry-toolbox`
2. `foundry-doc-vision-speech`
3. `foundry-iq`
4. `foundry-evals`
5. `foundry-observability`
6. `foundry-cost-monitoring`
7. `foundry-routines`
8. `foundry-hosted-agents`
9. `ghcp-hosted-agents`
10. `foundry-voice-live`
11. `foundry-skill-catalog`
12. new `foundry-agent-optimizer`
13. `foundry-teams-bot` after Microsoft 365 test access is available
14. `foundry-vnet-deploy` with manual Azure evidence
15. `foundry-network-runbook`

Each PR can update top-level catalog prose and generated site files for its
single skill. It must not edit a second skill body. Cross-skill cleanup waits
for that second skill's own PR.

---

## 4. First PR goals and non-goals

### Goals

- Move the skill from the preview Toolbox contract to the GA service contract.
- Make `azure-ai-projects` 2.3.0 the canonical management SDK.
- Replace `.beta.toolboxes` and generic `Tool` models with `.toolboxes` and
  `ToolboxTool` models.
- Remove the obsolete `Foundry-Features: Toolboxes=V1Preview` requirement.
- Separate core Toolbox GA from preview subfeatures, especially Tool Search.
- Replace the obsolete high-level MAF `AzureAIToolbox` sample with
  `agent_framework_foundry_hosting.FoundryToolbox`.
- Prove the new management and consumption paths against a live Foundry project.

### Non-goals

- No edits to `foundry-doc-vision-speech`; its obsolete header is the next PR.
- No Agent Optimizer, Foundry IQ, Teams publishing, or model-catalog changes.
- No broad rewrite of generic MCP guidance.
- No universal token-savings claim.
- No new plugin and no `plugin.json` or marketplace version bump.
- No normalization of unrelated prose, examples, or reference data.

---

## 5. Current defects

The current skill has five contract-level defects:

1. Frontmatter and body call Toolboxes preview and require
   `Toolboxes=V1Preview`.
2. CRUD examples use `project.beta.toolboxes`.
3. CRUD examples pass Agent `Tool` models such as `MCPTool`; SDK 2.3 requires
   Toolbox models such as `MCPToolboxTool`.
4. The canonical high-level reference imports `AzureAIToolbox`, while the
   current Agent Framework hosted sample uses `FoundryToolbox`.
5. The fixture explicitly instructs the agent to use `.beta.toolboxes` and the
   preview header.

The pin file compounds the drift: frontmatter pins SDK 2.3.0 but its prose
still says the skill validates 2.1.0 and marks the removed header issue open.

---

## 6. Locked contract decisions

| Area | Decision |
|---|---|
| Skill version | `2.0.0` because the canonical preview API contract is replaced |
| Management SDK | `AIProjectClient(...).toolboxes` |
| Toolbox model base | `ToolboxTool` |
| Minimal CRUD fixture tool | `CodeInterpreterToolboxTool()`; no external connection or model required to list tools |
| High-level MAF consumer | `agent_framework_foundry_hosting.FoundryToolbox` |
| Auth scope | `https://ai.azure.com/.default` |
| Stable request shape | Entra authorization plus `?api-version=v1`; no preview feature header |
| Tool Search | Optional preview mode using `ToolboxSearchPreviewToolboxTool` |
| Demo metric | One illustrative Microsoft trace; not a benchmark or guarantee |
| Old API guidance | One compact migration table, not parallel canonical examples |
| Fixture endpoint | `FOUNDRY_PROJECT_ENDPOINT`, never the account-level `AZURE_AI_ENDPOINT` |

### Stable CRUD shape

The canonical code uses:

```python
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import CodeInterpreterToolboxTool
from azure.identity import DefaultAzureCredential

with (
    DefaultAzureCredential() as credential,
    AIProjectClient(endpoint=project_endpoint, credential=credential) as project,
):
    toolbox_version = project.toolboxes.create_version(
        name=toolbox_name,
        description="CI smoke toolbox",
        tools=[CodeInterpreterToolboxTool()],
    )
```

The implementation must use the official 2.3 Toolbox model classes for every
tool row. Old generic Agent tool classes remain valid for Agent definitions,
not Toolbox version definitions.

### Tool Search status boundary

The skill will distinguish:

- **GA:** Toolbox resource, immutable versions, default-version promotion,
  stable MCP endpoints, core Toolbox tool types.
- **Preview:** `ToolboxSearchPreviewToolboxTool`, skills in Toolboxes, A2A,
  Work IQ, Fabric IQ, Browser Automation, and any other catalog item explicitly
  marked preview by Microsoft.

Tool Search exposes `tool_search` and `call_tool`. Tool descriptions are part
of retrieval quality; the model must be instructed to search before calling.
The cited 467 versus approximately 4,700 input-token result is presented as a
single Microsoft Mechanics demo trace (90.1% arithmetic reduction), without
generalizing quality or savings.

---

## 7. File-by-file implementation

### `skills/foundry-toolbox/SKILL.md`

- Rewrite frontmatter around the GA core and preview Tool Search.
- Keep the description at or below 1,024 characters.
- Add a status matrix near the overview.
- Replace the seven generic tool classes with the full 2.3 Toolbox class
  matrix and per-tool status.
- Replace the mandatory-header section with a stable request-contract section.
- Replace `.beta.toolboxes` CRUD and promotion examples with `.toolboxes`.
- Remove `allow_preview=True` from stable Toolbox management examples.
- Replace low-level preview-header MAF wiring with the canonical
  `FoundryToolbox` path.
- Keep direct `MCPStreamableHTTPTool` guidance only for non-Toolbox MCPs.
- Add the optional Tool Search preview section.
- Update the `azd` section to `azure.ai.toolboxes` 1.0.0-beta.2 and
  `azd >=1.27.0`, while clearly stating that the extension remains beta.
- Update troubleshooting, migration guidance, cross-references, and catalog
  history.

### `references/python/toolbox_wiring.py`

- Update the header to the current package versions and section name.
- Replace `AzureAIToolbox` with `FoundryToolbox`.
- Use sync `DefaultAzureCredential`, matching the current official
  `FoundryToolbox` sample and its `TokenCredential` contract.
- Resolve the platform-provided Toolbox MCP URL.
- Compose `FoundryToolbox` with the Agent as the high-level GA path.
- Preserve the direct Learn MCP example as a separate non-Toolbox pattern.
- Do not duplicate the implementation inline in `SKILL.md`.

### `references/python/mcp_text_extractor.py`

No planned edit. Its direct-MCP parser stays canonical unless validation against
MAF 1.11 proves the API or result envelope changed.

### `references/upstream-pin.md`

Set the bounded packages to:

```yaml
azure-ai-projects: "2.3.0"                 # install ~=2.3.0
agent-framework: "1.11.0"                  # install ~=1.11.0
agent-framework-foundry-hosting: "1.0.0a260709"  # install exact prerelease
mcp: "1.28.1"                              # install ~=1.28.1
```

- Add the hosting package to `packages`.
- Update package notes to the stable Toolbox and `FoundryToolbox` contract.
- Mark KI-001 `closed_upstream_fixed`.
- Retain the issue in the audit trail and set its workaround location to
  "removed in v2.0.0."
- Keep `known_issues_count: 1` because the count includes closed entries.
- Update the validation script to import stable Toolbox classes,
  `FoundryToolbox`, and `MCPStreamableHTTPTool`.
- Synchronize the prose package table and set `last_validated: 2026-07-13`.

### `test-fixture/consumer_prompt.md`

- Add the mandatory anti-recursive-`copilot` block.
- Use `FOUNDRY_PROJECT_ENDPOINT`; inventory it in Step 0.
- Create a UUID-suffixed Toolbox with `CodeInterpreterToolboxTool()`.
- Assert the returned name and version are non-empty.
- Fetch the version through `project.toolboxes`.
- Connect to the versioned MCP endpoint with `FoundryToolbox`, without a
  `Foundry-Features` header.
- Assert `FoundryToolbox.functions` is non-empty after `connect()`.
- Delete the Toolbox by name.
- Preserve the deterministic marker-file contract.

Cleanup remains part of the fixture success contract because the Toolbox is the
direct resource under test and deletion is a stable GA management operation.

### Top-level and generated docs

- Update the `foundry-toolbox` row in `README.md`.
- Run `python3 scripts/build-site.py --out docs/`.
- Do not hand-edit generated skill HTML.

---

## 8. Validation and acceptance criteria

### T0 - catalog validation

- All SKILL frontmatter parses.
- Description length is at most 1,024 characters.
- `metadata.version` is exactly `2.0.0`.
- Reference headers resolve to current SKILL section titles.
- No forbidden identifiers or real Azure resource IDs are introduced.

### T1/T2 - pin and import validation

The pin script must:

- install only bounded stable versions and exact prereleases;
- import `AIProjectClient`, `ToolboxTool`, `CodeInterpreterToolboxTool`,
  `MCPToolboxTool`, `ToolboxSearchPreviewToolboxTool`, `FoundryToolbox`, and
  `MCPStreamableHTTPTool`;
- prove the stable client exposes `.toolboxes`;
- compile both Python reference files; and
- emit every declared `expected_output` substring.

### T3 - live Foundry validation

The existing `foundry-toolbox` matrix leg must prove:

1. OIDC environment variables exist.
2. A Toolbox version is created through stable `.toolboxes`.
3. The response contains the expected name and version.
4. The version is retrievable.
5. `FoundryToolbox` connects to its MCP endpoint without the preview header.
6. At least one Toolbox function is visible.
7. The Toolbox is deleted.
8. The marker file is byte-exact `SMOKE_RESULT=PASS\n`.

The PR body must include the successful CI run or equivalent live Azure
evidence. A lint-only or import-only result is insufficient.

### Repository checks

- Run the existing catalog validation and test suites.
- Rebuild the site.
- Inspect every modified file with `git diff -a`.
- Confirm only the target skill source plus catalog/generated docs changed.
- Commit with `[skill-rewrite]`; do not use `[multi-skill]`.

---

## 9. Risks and controls

| Risk | Control |
|---|---|
| GA service but beta `azd` extension causes status confusion | Status matrix separates service/API status from extension status. |
| Official samples still carry stale preview prose | Prefer current service announcement, stable SDK namespace, and header-removal changelogs; cite conflicting samples as migration context only. |
| Tool Search is accidentally presented as GA | Keep "Preview" in its heading, class name, status matrix, and description. |
| Token reduction is treated as guaranteed | Label it a single demo trace and omit benchmark language. |
| MAF wrapper API differs from assumptions | Pin exact hosting prerelease and validate the canonical reference imports and live connection. |
| Fixture uses the account endpoint | Require `FOUNDRY_PROJECT_ENDPOINT` explicitly. |
| A multi-skill cleanup sneaks into the PR | Defer `foundry-doc-vision-speech` and every other skill body to its own PR. |

---

## 10. Deferred follow-ups

After this PR is green and merged, start a fresh single-skill PR for
`foundry-doc-vision-speech` to remove its obsolete Toolbox header. Continue
through the approved queue one skill at a time.

No implementation work for a later skill begins before the preceding skill's
live evidence is available.
