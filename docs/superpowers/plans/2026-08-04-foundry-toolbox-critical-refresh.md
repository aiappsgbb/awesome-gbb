# Foundry Toolbox Critical Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `foundry-toolbox` to the current stable Tool Search contract, current package stack, and an explicit MCP 2 compatibility hold, with live Azure proof.

**Architecture:** Keep stable Toolbox management in `azure-ai-projects~=2.4.0` and hosted consumption in `FoundryToolbox`. Replace the preview Tool Search model with `ToolSearchToolboxTool`, pin the MCP 1.29 maintenance line below 2.0, and extend the existing live fixture so service acceptance and the two Tool Search meta-tools are hard gates.

**Tech Stack:** Python 3.12, Azure AI Projects 2.4, Microsoft Agent Framework 1.13, Foundry hosting beta `b260730`, MCP 1.29, azd, Copilot-CLI T3 fixtures, static docs generator.

---

## File map

| File | Action |
|---|---|
| `skills/foundry-toolbox/references/upstream-pin.md` | Update package pins, validation, and `KI-002` |
| `skills/foundry-toolbox/references/python/toolbox_wiring.py` | Update canonical dependency claims/import |
| `skills/foundry-toolbox/SKILL.md` | Stable Tool Search contract and version `2.1.0` |
| `skills/foundry-toolbox/test-fixture/consumer_prompt.md` | Live stable Tool Search proof |
| `README.md` | Replace the stale preview Tool Search catalog row |
| `plugin.json` | Validator-required minimal PATCH `4.29.3` to `4.29.4` |
| `.github/plugin/marketplace.json` | Match both version fields to `4.29.4` |
| `docs/` | Regenerate |

## Execution precondition

Execute only after this approved plan is merged. Use
`superpowers:using-git-worktrees` to create a fresh worktree from current
`origin/main`; do not reuse the planning branch.

```bash
git fetch origin main
test -z "$(git status --short)"
test -z "$(git diff --name-only origin/main...HEAD)"
```

Expected: both `test` commands exit `0`. Every commit below must include
`Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>`;
the executing Copilot session must also append its runtime-provided
`Copilot-Session` trailer.

### Task 1: Establish the red contract

**Files:**
- Verify: `skills/foundry-toolbox/**`

- [ ] **Step 1: Run the clean baseline**

```bash
python3 scripts/validate-skills.py
python3 -m pytest -q scripts/tests/
```

Expected: both commands exit `0`.

- [ ] **Step 2: Run the migration probe**

```bash
python3 - <<'PY'
from pathlib import Path

skill = Path("skills/foundry-toolbox/SKILL.md").read_text()
pin = Path("skills/foundry-toolbox/references/upstream-pin.md").read_text()
fixture = Path("skills/foundry-toolbox/test-fixture/consumer_prompt.md").read_text()

assert "ToolSearchToolboxTool" in skill, "stable Tool Search model missing"
assert '{"type": "toolbox_search"}' in skill, "stable wire type missing"
assert 'version: "2.4.0"' in pin, "Azure AI Projects 2.4 pin missing"
assert 'version: "1.29.0"' in pin, "MCP 1.29 pin missing"
assert 'hold_below: "2.0.0"' in pin, "MCP 2 hold missing"
assert "ToolSearchToolboxTool" in fixture, "live stable Tool Search proof missing"
PY
```

Expected: FAIL at `stable Tool Search model missing`.

### Task 2: Refresh the machine-readable pin

**Files:**
- Modify: `skills/foundry-toolbox/references/upstream-pin.md:10-130`

- [ ] **Step 1: Replace the four package entries**

Use these exact versions and notes; preserve unrelated fields:

```yaml
packages:
  - name: azure-ai-projects
    source: pypi
    version: "2.4.0"
    upstream_changelog: https://pypi.org/project/azure-ai-projects/#history
    notes: Stable Toolbox management and stable ToolSearchToolboxTool.
  - name: agent-framework
    source: pypi
    version: "1.13.0"
    upstream_changelog: https://pypi.org/project/agent-framework/#history
    notes: Current core agent and MCP tool composition surface.
  - name: agent-framework-foundry-hosting
    source: pypi
    version: "1.0.0b260730"
    upstream_changelog: https://pypi.org/project/agent-framework-foundry-hosting/#history
    notes: Exact prerelease containing FoundryToolbox; requires mcp>=1.24,<2.
  - name: mcp
    source: pypi
    version: "1.29.0"
    upstream_changelog: https://pypi.org/project/mcp/#history
    hold_below: "2.0.0"
    hold_reason: KI-002
    notes: Current MCP 1.x maintenance line; MCP 2 is blocked by the hosting package.
```

- [ ] **Step 2: Add the open MCP issue**

Append this entry after the existing known issue:

```yaml
  - id: KI-002
    description: agent-framework-foundry-hosting 1.0.0b260730 requires mcp>=1.24,<2, so MCP 2 cannot resolve with the canonical FoundryToolbox consumer.
    upstream_url: https://github.com/microsoft/agent-framework/issues/7446
    status: open
    workaround_location: SKILL.md § "Current API matrix"
```

Set `known_issues_count: 2`, `last_validated: 2026-08-04`, and
`validated_by: ricchi`.

- [ ] **Step 3: Replace the validation script**

```yaml
validation:
  requires: [pypi]
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv
    . .venv/bin/activate
    pip install --quiet \
      "azure-ai-projects~=2.4.0" \
      "agent-framework~=1.13.0" \
      "agent-framework-foundry-hosting==1.0.0b260730" \
      "mcp~=1.29.0"
    python - <<'PY'
    from importlib.metadata import version
    from agent_framework import MCPStreamableHTTPTool
    from agent_framework_foundry_hosting import FoundryToolbox
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import (
        ToolSearchToolboxTool,
        ToolboxSearchPreviewToolboxTool,
    )
    from mcp import ClientSession

    class OfflineCredential:
        def get_token(self, *scopes, **kwargs):
            raise RuntimeError("network is outside the import smoke")
        def close(self):
            return None

    client = AIProjectClient(
        endpoint="https://example.services.ai.azure.com/api/projects/example",
        credential=OfflineCredential(),
    )
    assert callable(client.toolboxes.create_version)
    assert callable(client.toolboxes.get_version)
    assert callable(client.toolboxes.delete)
    assert ToolSearchToolboxTool().as_dict() == {"type": "toolbox_search"}
    assert ToolboxSearchPreviewToolboxTool().as_dict()["type"] == "toolbox_search_preview"
    assert FoundryToolbox and MCPStreamableHTTPTool and ClientSession
    assert version("azure-ai-projects").startswith("2.4.")
    assert version("agent-framework").startswith("1.13.")
    assert version("mcp").startswith("1.29.")
    client.close()
    print("ok stable toolbox search")
    print("ok foundry toolbox current stack")
    PY
  expected_output:
    - "ok stable toolbox search"
    - "ok foundry toolbox current stack"
```

- [ ] **Step 4: Synchronize the human pin audit trail**

Update the package table to the same four target versions. Add:

```markdown
## Known issues

### KI-002 - MCP 2 blocked by Agent Framework hosting

`agent-framework-foundry-hosting==1.0.0b260730` requires
`mcp>=1.24,<2`. Keep MCP on the 1.29 maintenance line until
[microsoft/agent-framework#7446](https://github.com/microsoft/agent-framework/issues/7446)
is resolved by a released, live-validated hosting package.
```

- [ ] **Step 5: Verify hold structure and run pin validation**

```bash
python3 - <<'PY'
from pathlib import Path
import yaml

text = Path("skills/foundry-toolbox/references/upstream-pin.md").read_text()
data = yaml.safe_load(text.split("---", 2)[1])
mcp = next(p for p in data["packages"] if p["name"] == "mcp")
ki = next(k for k in data["known_issues"] if k["id"] == "KI-002")
assert mcp["hold_below"] == "2.0.0"
assert mcp["hold_reason"] == "KI-002"
assert ki["status"] == "open"
assert data["known_issues_count"] == 2
PY
```

Expected: the structural assertions pass.

- [ ] **Step 6: Commit and run the changed-pin validator**

```bash
git add skills/foundry-toolbox/references/upstream-pin.md
git commit -m "chore(foundry-toolbox): refresh toolbox dependency pins" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
python3 scripts/run-pin-validation.py --base=origin/main
```

Expected: both expected-output strings are present and the command exits `0`.

### Task 3: Replace the preview Tool Search contract

**Files:**
- Modify: `skills/foundry-toolbox/SKILL.md`
- Modify: `skills/foundry-toolbox/references/python/toolbox_wiring.py:1-40`

- [ ] **Step 1: Update the skill version**

Change:

```yaml
metadata:
  version: "2.1.0"
```

- [ ] **Step 2: Replace the Tool Search model example**

The stable section must contain exactly this executable core:

```python
from azure.ai.projects.models import ToolSearchToolboxTool

tool_search = ToolSearchToolboxTool()
assert tool_search.as_dict() == {"type": "toolbox_search"}
```

Delete preview language that recommends
`ToolboxSearchPreviewToolboxTool`. Keep one migration table:

```markdown
| Preview name | Stable name |
|---|---|
| `ToolboxSearchPreviewToolboxTool` | `ToolSearchToolboxTool` |
| `toolbox_search_preview` | `toolbox_search` |
```

Keep `ToolboxSearchPreviewToolboxTool` in the frontmatter trigger list for
preview consumers, but change the description's status wording to stable Tool
Search and remove Tool Search from the comma-separated preview-capabilities
list. This MINOR is justified by adding Tool Search as a supported stable
capability. The current description is 1,010 characters; count the parsed
description after editing and keep it at or below 1,024 characters.

Reconcile every body-level status surface rather than changing only the model
example:

- the introduction must call Tool Search stable while leaving skills in
  Toolboxes preview;
- split the combined status-boundary row so Tool Search is stable and skills
  remain preview;
- move Tool Search into the stable-tool diagram and remove the preview model
  from that diagram;
- remove "Tool Search preview" from the Prompt Agent consumer row and bridge
  prose; and
- remove any remaining troubleshooting/status prose that labels Tool Search
  preview.

- [ ] **Step 3: Replace current-version claims**

Replace the existing three-column **Current API matrix** rather than adding a
second table. Its replacement must list:

```markdown
| Package | Supported line |
|---|---|
| `azure-ai-projects` | `~=2.4.0` |
| `agent-framework` | `~=1.13.0` |
| `agent-framework-foundry-hosting` | `==1.0.0b260730` |
| `mcp` | `~=1.29.0` (`<2` until KI-002 closes) |
```

Update the surrounding `azure-ai-projects` 2.3/2.3.0 prose at the current
Toolbox-model warning, creation-method migration row, model-serialization
note, SDK-split note, and troubleshooting row (current lines 125, 162, 176,
760, 894, and 1106) to 2.4/2.4.0 as appropriate. Update the MAF-consumer note
near current line 217 from MAF 1.11 to MAF 1.13.

- [ ] **Step 4: Update the canonical reference header/import**

In `toolbox_wiring.py`, update version claims to the same four values. If the
file imports the preview model, replace only that import:

```python
from azure.ai.projects.models import ToolSearchToolboxTool
```

Do not add `as_skills_provider()`.

- [ ] **Step 5: Run the red probe again**

Run the Task 1 Step 2 command, then:

```bash
python3 - <<'PY'
from pathlib import Path
import re

text = Path("skills/foundry-toolbox/SKILL.md").read_text()
frontmatter, body = text.split("---", 2)[1:]
assert "ToolboxSearchPreviewToolboxTool" in frontmatter
assert "stable Tool Search" in frontmatter
assert "preview Tool Search" not in frontmatter
assert not re.search(r"preview[\s\S]{0,100}Tool Search", frontmatter)
assert body.count("ToolboxSearchPreviewToolboxTool") == 1
assert "Tool Search (preview)" not in body
assert "Tool Search preview" not in body
assert "is a preview capability" not in body
assert "Tool Search and skills in Toolboxes" not in body
assert "retain their preview support terms" not in body
assert "Tool Search -> preview" not in body
for old in (
    "2.3.0",
    "Toolbox 2.3 models",
    "`azure-ai-projects` 2.3 |",
    "1.11.0",
    "MAF 1.11",
    "1.0.0a260709",
    "1.28.1",
):
    assert old not in body, old
for new in ("2.4.0", "1.13.0", "1.0.0b260730", "1.29.0"):
    assert new in body, new
assert "MAF 1.13" in body
PY
```

Expected: it now fails only at `live stable Tool Search proof missing`.

- [ ] **Step 6: Commit**

```bash
git add skills/foundry-toolbox/SKILL.md \
  skills/foundry-toolbox/references/python/toolbox_wiring.py
git commit -m "feat(foundry-toolbox): stabilize Tool Search [skill-rewrite]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 4: Make stable Tool Search a live hard gate

**Files:**
- Modify: `skills/foundry-toolbox/test-fixture/consumer_prompt.md`

- [ ] **Step 1: Update the fixture package install**

```bash
/tmp/foundry-toolbox-venv/bin/pip install --quiet \
  "azure-ai-projects~=2.4.0" \
  "azure-identity~=1.25.3" \
  "agent-framework~=1.13.0" \
  "agent-framework-foundry-hosting==1.0.0b260730" \
  "mcp~=1.29.0"
```

- [ ] **Step 2: Replace the fixture model import and create payload**

```python
from azure.ai.projects.models import (
    CodeInterpreterToolboxTool,
    ToolSearchToolboxTool,
)
```

```python
created = project.toolboxes.create_version(
    name=toolbox_name,
    description="CI stable Tool Search smoke",
    tools=[
        ToolSearchToolboxTool(),
        CodeInterpreterToolboxTool(),
    ],
)
record(f"TOOL_SEARCH_CREATED name={created.name} version={created.version}")
```

Keep every management call under `project.toolboxes`. Add an explicit fixture
rule forbidding `project.beta.toolboxes`; beta-only acceptance is a hard
failure and triggers the rollback in the approved design.

- [ ] **Step 3: Replace `verify_functions` assertions**

```python
async def verify_functions(
    credential: DefaultAzureCredential,
    toolbox_url: str,
    toolbox_name: str,
) -> None:
    async with FoundryToolbox(
        credential,
        url=toolbox_url,
        name=toolbox_name,
    ) as toolbox:
        names = {
            getattr(function, "name", None)
            or getattr(function, "__name__", None)
            for function in toolbox.functions
        }
        names.discard(None)
        assert {"tool_search", "call_tool"} <= names, names
        record(f"TOOL_SEARCH_FUNCTIONS names={','.join(sorted(names))}")
```

After recording the function names, keep the Python Toolbox deletion inside
this same smoke program. Catch deletion exceptions, print one transcript-only
`NOTE`, and do not append a deletion sidecar record or replace completed hard
proof with cleanup failure.

- [ ] **Step 4: Replace the evidence and failure contract**

Replace the existing azd `cleanup()` trap so it preserves the entry status,
attempts both azd Toolbox deletions, and prints a transcript-only `NOTE` on
each deletion failure. Deletion must not append `AZD_TOOLBOX_DELETED` records
or change a previously successful status to failure.

Reword the transition after the azd script to say both azd Toolboxes were
cleaned up best-effort. Delete the sentence that calls Python Toolbox deletion
a hard success criterion and requires the `finally` block; replace the
`finally` deletion with the soft-pass cleanup described in Step 3.

The required sidecar records become:

```python
patterns = (
    r"AZD_SERVICE_CREATED name=ci-smoke-azdsvc-[0-9a-f]{8}",
    r"AZD_CLI_CREATED name=ci-smoke-azdcli-[0-9a-f]{8}",
    r"TOOL_SEARCH_CREATED name=ci-smoke-tbx-[0-9a-f]{8} version=\S+",
    r"TOOLBOX_RETRIEVED name=ci-smoke-tbx-[0-9a-f]{8} version=\S+",
    r"TOOL_SEARCH_FUNCTIONS names=.+",
)
```

Retain the exact-count assertion: the sidecar must contain exactly those five
hard-success records, while cleanup diagnostics remain only in stdout. The
Python smoke already asserts both required meta-tool names before recording
the fifth line. After both azd objects and the Python Toolbox have been
cleaned up best-effort, verify the sidecar and write the PASS marker.

Remove hard-failure markers for deletion and replace `Toolbox functions empty`
with:

```bash
printf 'SMOKE_RESULT=FAIL Tool Search meta-tools missing\n' > /tmp/foundry-toolbox-smoke-result
```

Keep the existing instruction forbidding tool calls after the marker.

- [ ] **Step 5: Run the local pre-metadata gates**

```bash
python3 scripts/run-pin-validation.py --base=origin/main
python3 -m pytest -q scripts/tests/
git diff --check
```

Expected: all commands exit `0`.

- [ ] **Step 6: Commit**

```bash
git add skills/foundry-toolbox/test-fixture/consumer_prompt.md
git commit -m "test(foundry-toolbox): prove stable Tool Search live" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 5: Synchronize catalog metadata and generated docs

**Files:**
- Modify: `plugin.json`
- Modify: `.github/plugin/marketplace.json`
- Modify: `README.md:131`
- Regenerate: `docs/`

- [ ] **Step 1: Update the catalog row and plugin metadata**

Replace the `foundry-toolbox` README description with:

```markdown
Use Foundry Toolbox GA with stable `AIProjectClient.toolboxes` CRUD, Toolbox-specific SDK models, authenticated `FoundryToolbox` hosted-agent wiring, immutable version promotion/rollback, the `azure_ai_search`-is-INDEX-not-KB boundary, and stable Tool Search (`ToolSearchToolboxTool`, `tool_search`, `call_tool`) without the retired preview feature header
```

Change the root `"version"` in `plugin.json` and both marketplace plugin
version fields to:

```json
"version": "4.29.4"
```

- [ ] **Step 2: Regenerate docs**

```bash
python3 scripts/build-site.py --out docs/ --validate
python3 scripts/build-plugins.py --check
python3 scripts/validate-skills.py
```

Expected: plugin metadata matches, 35 skills validate, and generation exits
`0`.

- [ ] **Step 3: Commit**

```bash
git add README.md plugin.json .github/plugin/marketplace.json
git add -u docs/
git commit -m "docs: publish foundry-toolbox 2.1.0" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 6: Obtain live Azure proof and open the PR

- [ ] **Step 1: Push and open the one-skill PR**

```bash
git push -u origin HEAD
gh pr create \
  --title "feat: refresh foundry-toolbox stable Tool Search" \
  --body "Refreshes only foundry-toolbox to Azure AI Projects 2.4, stable Tool Search, Agent Framework 1.13, hosting b260730, and MCP 1.29 with an explicit MCP 2 hold. Requires T0-T3; live evidence will be added from the foundry-toolbox matrix leg."
```

- [ ] **Step 2: Require all checks and inspect the live marker**

```bash
gh pr checks --watch
RUN_ID="$(gh run list --workflow skill-test.yml --branch "$(git branch --show-current)" --limit 1 --json databaseId --jq '.[0].databaseId')"
JOB_ID="$(gh run view "$RUN_ID" --json jobs --jq '.jobs[] | select(.name | contains("foundry-toolbox")) | .databaseId')"
gh run view "$RUN_ID" --job "$JOB_ID" --log > /tmp/foundry-toolbox-job.log
rg \
  'TOOL_SEARCH_CREATED|TOOL_SEARCH_FUNCTIONS|PASS via marker file' \
  /tmp/foundry-toolbox-job.log
```

Expected: the log contains `TOOL_SEARCH_CREATED`, a
`TOOL_SEARCH_FUNCTIONS` line containing both `call_tool` and `tool_search`,
and the deterministic PASS marker.

- [ ] **Step 3: Add evidence to the PR body**

```bash
RUN_ID="$(gh run list --workflow skill-test.yml --branch "$(git branch --show-current)" --limit 1 --json databaseId --jq '.[0].databaseId')"
JOB_ID="$(gh run view "$RUN_ID" --json jobs --jq '.jobs[] | select(.name | contains("foundry-toolbox")) | .databaseId')"
PR="$(gh pr view --json number --jq .number)"
CURRENT_BODY="$(gh pr view "$PR" --json body --jq .body)"
UPDATED_BODY="${CURRENT_BODY}"$'\n\n'"## Live Azure evidence"$'\n'"Run $RUN_ID, job $JOB_ID: stable project.toolboxes accepted ToolSearchToolboxTool; FoundryToolbox exposed call_tool and tool_search; deterministic marker passed."
gh api --method PATCH "repos/aiappsgbb/awesome-gbb/pulls/$PR" \
  -f body="$UPDATED_BODY" >/dev/null
```

Do not merge if the live Tool Search assertions are absent, even if T0-T2 are
green.
