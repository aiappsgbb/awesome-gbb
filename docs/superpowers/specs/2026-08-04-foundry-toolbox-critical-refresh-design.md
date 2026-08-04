# Foundry Toolbox Critical Refresh - Design

- **Date:** 2026-08-04
- **Status:** Approved after independent specification review
- **Skill:** `foundry-toolbox`
- **Current skill version:** `2.0.1`
- **Target skill version:** `2.1.0`
- **PR shape:** one skill source plus required catalog metadata and generated docs

---

## 1. Decision

Refresh the Toolbox contract to the current coherent stack:

| Package | Target |
|---|---|
| `azure-ai-projects` | `~=2.4.0` |
| `agent-framework` | `~=1.13.0` |
| `agent-framework-foundry-hosting` | `==1.0.0b260730` |
| `mcp` | `~=1.29.0` |

Use the stable `ToolSearchToolboxTool` model and classify Tool Search as GA.
Keep `ToolboxSearchPreviewToolboxTool` only in a migration note so consumers
can recognize and replace the old serialized type
`toolbox_search_preview`. Do not add the new
`FoundryToolbox.as_skills_provider()` surface in this refresh; it is additive
and useful, but not required to close the current critical drift.

Hold MCP below `2.0.0` while
`agent-framework-foundry-hosting==1.0.0b260730` requires
`mcp>=1.24,<2`. The hold is an explicit compatibility decision, not a stale
pin.

---

## 2. Goals and non-goals

### Goals

- Move Tool Search from preview to its stable model and wire type.
- Prove `ToolSearchToolboxTool().as_dict()` emits
  `{"type": "toolbox_search"}`.
- Refresh all package claims in the pin, canonical reference, skill, and
  fixture.
- Encode the MCP 2 compatibility ceiling with a machine-enforced hold and an
  open known issue.
- Prove the stable Tool Search model is accepted by live Toolbox management
  and exposed as the `tool_search` and `call_tool` meta-tools.
- Rebuild generated catalog pages.

### Non-goals

- No `as_skills_provider()` documentation.
- No Agent Framework or MCP 2 migration.
- No edits to `foundry-hosted-agents` or another skill body.
- No broad rewrite of Toolbox CRUD, auth, azd, or direct MCP guidance that
  remains correct.
- No plugin restructuring or new skill.

---

## 3. Compatibility boundary

The installable target stack was reproduced in a scratch environment. MCP
2.0 cannot be installed with the selected hosting package because the latter
declares `mcp>=1.24,<2`. The pin will therefore:

```yaml
- name: mcp
  version: "1.29.0"
  hold_below: "2.0.0"
  hold_reason: KI-002
```

The same pin edit must add `KI-002` with `status: open` and set
`known_issues_count: 2`; the detector deliberately ignores a hold without a
matching open issue. `KI-002` remains open until a released
`agent-framework-foundry-hosting` version supports MCP 2 and the canonical
`FoundryToolbox` reference plus live fixture pass on that stack.

---

## 4. Contract changes

### Stable Tool Search

The canonical stable model is:

```python
from azure.ai.projects.models import ToolSearchToolboxTool

tool = ToolSearchToolboxTool()
assert tool.as_dict() == {"type": "toolbox_search"}
```

The skill must no longer label Tool Search preview or use
`ToolboxSearchPreviewToolboxTool` as the recommended model. A compact
migration row will map:

| Old | Current |
|---|---|
| `ToolboxSearchPreviewToolboxTool` | `ToolSearchToolboxTool` |
| `toolbox_search_preview` | `toolbox_search` |

Retain `ToolboxSearchPreviewToolboxTool` as a frontmatter trigger and migration
term so existing preview consumers still discover the skill. Update the
frontmatter description's status wording without removing that trigger.

### Current API matrix

Update the package matrix and prose to the four target versions. Preserve
the existing stable management namespace, `FoundryToolbox` consumer, and
Toolbox MCP endpoint guidance.

### Canonical reference

`references/python/toolbox_wiring.py` remains the single source of truth for
hosted Toolbox wiring. Its package-version docstring and imports must match
the target stack. It does not gain an `as_skills_provider()` example.

---

## 5. Validation design

### T0/T1/T2

The pin script installs the exact bounded stack and asserts:

1. stable Toolbox operations remain present;
2. `ToolSearchToolboxTool().as_dict()` is exactly
   `{"type": "toolbox_search"}`;
3. the preview model remains importable only for migration recognition;
4. `FoundryToolbox`, `MCPStreamableHTTPTool`, and MCP 1.29 client imports
   remain available;
5. the MCP hold is backed by open `KI-002`.

### T3

Extend the existing live fixture to create a UUID-named Toolbox version
through stable `project.toolboxes`, containing the stable Tool Search model
and another Toolbox tool. The fixture must retain its prohibition on
`project.beta.toolboxes`. Connect with `FoundryToolbox`, require the exposed
function names to include
`tool_search` and `call_tool`. After each object has produced its hard evidence,
delete it best-effort before evaluating the deterministic marker. Deletion
results are transcript-only `NOTE` lines, never required sidecar records, and
cannot turn completed hard proof into a failure.

The live test fails if the service rejects the stable model, the management
SDK serializes the preview type, or the wrapper does not expose both
meta-tools. Acceptance only through `.beta.toolboxes` is a non-GA result and
triggers the rollback in section 7.

---

## 6. Files

| File | Responsibility |
|---|---|
| `skills/foundry-toolbox/SKILL.md` | Stable Tool Search status, model, migration row, package matrix, `2.1.0` |
| `skills/foundry-toolbox/references/upstream-pin.md` | Current package pins, MCP 2 hold, import/serialization probes |
| `skills/foundry-toolbox/references/python/toolbox_wiring.py` | Canonical dependency claims and stable imports |
| `skills/foundry-toolbox/test-fixture/consumer_prompt.md` | Live stable Tool Search acceptance and meta-tool proof |
| `README.md` | Replace the stale "preview Tool Search" catalog row |
| `plugin.json` | Validator-required minimal PATCH `4.29.3 -> 4.29.4` |
| `.github/plugin/marketplace.json` | Match both marketplace version fields to `4.29.4` |
| `docs/` | Regenerated static catalog |

The body rewrite requires a `[skill-rewrite]` commit tag. The skill MINOR is
intentional: stable Tool Search is a newly supported stable capability, not
only a pin refresh. The current frontmatter description is 1,010 characters;
the status reword must stay at or below 1,024 characters while retaining the
preview-class trigger. Trim redundant wording before adding a stable-model
trigger if the net change would exceed the 14-character headroom.

---

## 7. Rollback and unblock conditions

Rollback is one revert of the one-skill implementation commit. If stable Tool
Search fails live service acceptance despite the 2.4.0 model, leave the skill
at `2.0.1`, keep Tool Search preview, and record the service/region evidence
on the freshness issue.

MCP 2 is unblocked only after:

1. a released hosting package removes `<2`;
2. the selected Agent Framework stack resolves with MCP 2;
3. pin validation passes with the migrated client imports; and
4. the live Toolbox fixture passes without compatibility shims.
