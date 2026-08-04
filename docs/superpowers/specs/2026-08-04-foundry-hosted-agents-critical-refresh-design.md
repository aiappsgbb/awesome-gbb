# Foundry Hosted Agents Critical Refresh - Design

- **Date:** 2026-08-04
- **Status:** Approved after independent specification review
- **Skill:** `foundry-hosted-agents`
- **Current skill version:** `2.1.0`
- **Target skill version:** `2.1.1`
- **PR shape:** one skill source plus generated docs

---

## 1. Decision

Adopt the latest coherent Foundry-first dependency set:

| Package | Target |
|---|---|
| `agent-framework-core` | `~=1.13.0` |
| `agent-framework-foundry` | `~=1.10.4` |
| `agent-framework-foundry-hosting` | `==1.0.0b260730` |
| `azure-ai-projects` | `~=2.3.0` |
| `mcp` | `~=1.29.0` |
| `azure-identity` | `~=1.25.3` |
| `python-dotenv` | `~=1.2.2` |

Prefer `agent-framework-foundry==1.10.4` over
`azure-ai-projects==2.4.0`. The Foundry package requires
`azure-ai-projects>=2.2,<2.4`, and the hosted-agent contract does not need the
2.4-only stable Tool Search model. `AgentsOperations.update_details` remains
available on Azure AI Projects 2.3.

---

## 2. Goals and non-goals

### Goals

- Refresh the canonical `pyproject.toml`, pin file, skill dependency claims,
  and fixture to one installable set.
- Encode a machine-enforced Azure AI Projects hold below 2.4 and an MCP hold
  below 2.0.
- Preserve the current hosted-agent deploy, invoke, update-details, rollout,
  identity, and retry behavior.
- Fix the source-of-truth violation by removing the duplicated full
  `azure.yaml` body from `SKILL.md`.
- Keep `references/yaml/azure.yaml` as the only complete YAML source and
  retain an imperative cross-link in the skill.
- Rebuild generated catalog pages.

### Non-goals

- No Tool Search adoption.
- No migration to MCP 2.
- No change to hosted-agent architecture, `FoundryChatClient`, or azd
  deployment model.
- No changes to dependent skill bodies.
- No plugin version bump; this is a PATCH correction.

The PR requires a `[skill-rewrite]` commit tag because it changes SKILL.md
body content. No `[multi-skill]` tag is needed.

---

## 3. Compatibility boundary

The latest `agent-framework-foundry==1.10.4` metadata requires:

```text
agent-framework-core>=1.13,<2
azure-ai-projects>=2.2,<2.4
```

The selected hosting beta requires MCP below 2. The pin will therefore add:

```yaml
- name: azure-ai-projects
  version: "2.3.0"
  hold_below: "2.4.0"
  hold_reason: KI-009

- name: mcp
  version: "1.29.0"
  hold_below: "2.0.0"
  hold_reason: KI-010
```

The 2.4 ceiling is intentionally a minor-version boundary because
`agent-framework-foundry` declares `<2.4`; it must not be widened to 3.0.
The same pin edit adds both issues with `status: open`, sets
`known_issues_count: 9`, and refreshes `last_validated`/`validated_by`.
`KI-009` closes when a released `agent-framework-foundry` supports 2.4 or
later and the hosted reference/fixture pass. `KI-010` closes when the hosting
package supports MCP 2 and the same proof passes.

---

## 4. Source-of-truth correction

`references/yaml/azure.yaml` remains canonical. Replace the full duplicated
YAML block in `SKILL.md` with:

```markdown
> **MUST:** Copy the complete configuration verbatim from
> [`references/yaml/azure.yaml`](references/yaml/azure.yaml).
> Do not redefine it inline; that file is the canonical unified
> `host: azure.ai.agent` configuration used by the fixture.
```

Keep the surrounding section heading and explanation so this is a PATCH bug
fix, not removal of a documented capability.

The refresh must also replace every stale alpha-era version claim in
`SKILL.md` and `references/upstream-pin.md`: Core 1.11, Foundry 1.10.1,
hosting `a260709`, MCP 1.28.1, and "alpha" labels. Update the hosting package
note and KI-008 item 2 from exact alpha discipline to exact beta discipline.

---

## 5. Validation design

### T0/T1/T2

The pin script installs the exact target stack and asserts:

1. installed versions match the selected set;
2. `FoundryChatClient`, `FoundryAgentRunner`, hosting middleware, and
   `McpError` imports resolve;
3. Azure AI Projects exposes `agents.update_details`;
4. the two package holds reference open known issues;
5. `references/python/pyproject.toml` matches the pin values.

The pyproject intentionally adds `azure-ai-projects~=2.3.0` as a direct
constraint. Although Agent Framework Foundry brings it transitively, the
container contract must not float to another 2.3 patch or cross the `<2.4`
boundary independently of the pin.

### T3

The existing fixture remains the live contract. It copies the canonical
`pyproject.toml` and `azure.yaml`, runs `azd up`, invokes the hosted agent via
the stable SDK path, exercises update-details, and verifies rendered YAML
parity. The refresh is approved only if the `foundry-hosted-agents` matrix leg
passes against live Azure.

Because `.github/skill-deps.yml` has forward fanout, the PR also runs
`foundry-mcp-aca` and `ghcp-hosted-agents`; those legs are compatibility
evidence, not permission to edit their skill bodies.

---

## 6. Files

| File | Responsibility |
|---|---|
| `skills/foundry-hosted-agents/SKILL.md` | Current dependency set, SSOT link, `2.1.1` |
| `skills/foundry-hosted-agents/references/upstream-pin.md` | Coherent pins, holds, version/import probes |
| `skills/foundry-hosted-agents/references/python/pyproject.toml` | Canonical container dependency set |
| `skills/foundry-hosted-agents/test-fixture/consumer_prompt.md` | Current package install and parity assertions |
| `docs/` | Regenerated static catalog |

---

## 7. Rollback and unblock conditions

Rollback is one revert. Do not partially retain a newer Foundry package with
the old core or hosting beta.

Azure AI Projects 2.4 is unblocked only when a compatible released
`agent-framework-foundry` exists and the hosted fixture passes. MCP 2 is
unblocked only when the hosting package supports it and the canonical
reference plus all three live fanout legs pass.
