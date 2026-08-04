# Foundry Hosted Agents Critical Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `foundry-hosted-agents` to the latest coherent Foundry-first package set and restore `azure.yaml` single-source-of-truth without changing runtime behavior.

**Architecture:** Pin Agent Framework Core 1.13, Foundry 1.10.4, hosting beta `b260730`, Azure AI Projects 2.3, and MCP 1.29 as one resolver-tested unit. Keep the complete hosted-agent configuration only in `references/yaml/azure.yaml`; the skill links to it and the live fixture copies and parity-checks it.

**Tech Stack:** Python 3.12, Microsoft Agent Framework, Azure AI Projects 2.3, MCP 1.29, azd hosted agents, Copilot-CLI Azure matrix.

---

## File map

| File | Action |
|---|---|
| `skills/foundry-hosted-agents/references/upstream-pin.md` | Refresh pins, add two holds, strengthen validation |
| `skills/foundry-hosted-agents/references/python/pyproject.toml` | Canonical coherent dependency set |
| `skills/foundry-hosted-agents/SKILL.md` | Dependency claims, SSOT link, `2.1.1` |
| `skills/foundry-hosted-agents/test-fixture/consumer_prompt.md` | Assert copied dependency set |
| `docs/` | Regenerate |

## Execution precondition

Execute only after this approved plan is merged. Use
`superpowers:using-git-worktrees` to create a fresh worktree from current
`origin/main`.

```bash
git fetch origin main
test -z "$(git status --short)"
test -z "$(git diff --name-only origin/main...HEAD)"
```

Expected: both `test` commands exit `0`. Every commit below must include
`Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>`;
the executing Copilot session must append its runtime-provided
`Copilot-Session` trailer.

### Task 1: Establish the red contract

- [ ] **Step 1: Run baseline validation**

```bash
python3 scripts/validate-skills.py
python3 -m pytest -q scripts/tests/
```

Expected: both exit `0`.

- [ ] **Step 2: Run the coherent-stack and SSOT probe**

```bash
python3 - <<'PY'
from pathlib import Path

skill = Path("skills/foundry-hosted-agents/SKILL.md").read_text()
pin = Path("skills/foundry-hosted-agents/references/upstream-pin.md").read_text()
project = Path("skills/foundry-hosted-agents/references/python/pyproject.toml").read_text()

for token in (
    "agent-framework-core~=1.13.0",
    "agent-framework-foundry~=1.10.4",
    "agent-framework-foundry-hosting==1.0.0b260730",
    "azure-ai-projects~=2.3.0",
    "mcp~=1.29.0",
):
    assert token in project, f"canonical dependency missing: {token}"
assert 'hold_below: "2.4.0"' in pin, "Azure AI Projects hold missing"
assert 'hold_below: "2.0.0"' in pin, "MCP 2 hold missing"
assert "```yaml\n# yaml-language-server:" not in skill, "azure.yaml duplicated inline"
PY
```

Expected: FAIL at the first missing current dependency.

### Task 2: Write the coherent dependency set

**Files:**
- Modify: `skills/foundry-hosted-agents/references/python/pyproject.toml:25-34`
- Modify: `skills/foundry-hosted-agents/references/upstream-pin.md`

- [ ] **Step 1: Replace canonical dependencies**

```toml
dependencies = [
    "agent-framework-core~=1.13.0",
    "agent-framework-foundry~=1.10.4",
    "agent-framework-foundry-hosting==1.0.0b260730",
    "azure-ai-projects~=2.3.0",
    "azure-identity~=1.25.3",
    "mcp~=1.29.0",
    "python-dotenv~=1.2.2",
    # OTel + gen_ai instrumentors are bundled via hosting.
]
```

Preserve `[tool.uv]` with
`prerelease = "if-necessary-or-explicit"`.

- [ ] **Step 2: Replace pin package versions and holds**

Use these exact package values:

```yaml
  - name: agent-framework-core
    source: pypi
    version: "1.13.0"
  - name: agent-framework-foundry
    source: pypi
    version: "1.10.4"
  - name: agent-framework-foundry-hosting
    source: pypi
    version: "1.0.0b260730"
  - name: azure-ai-projects
    source: pypi
    version: "2.3.0"
    hold_below: "2.4.0"
    hold_reason: KI-009
  - name: azure-identity
    source: pypi
    version: "1.25.3"
  - name: mcp
    source: pypi
    version: "1.29.0"
    hold_below: "2.0.0"
    hold_reason: KI-010
  - name: python-dotenv
    source: pypi
    version: "1.2.2"
```

Retain each package's current `upstream_changelog`.
Add a note on the Azure AI Projects entry that the 2.4 ceiling is deliberately
a MINOR boundary because Agent Framework Foundry declares `<2.4`.

- [ ] **Step 3: Add the two open known issues**

```yaml
  - id: KI-009
    description: agent-framework-foundry 1.10.4 requires azure-ai-projects>=2.2,<2.4; hosted agents prefer the current Foundry integration over Azure AI Projects 2.4-only Toolbox features.
    upstream_url: https://pypi.org/project/agent-framework-foundry/
    status: open
    workaround_location: SKILL.md § "Dependencies (pyproject.toml)"
  - id: KI-010
    description: agent-framework-foundry-hosting 1.0.0b260730 requires mcp>=1.24,<2.
    upstream_url: https://pypi.org/project/agent-framework-foundry-hosting/
    status: open
    workaround_location: SKILL.md § "Dependencies (pyproject.toml)"
```

Set `known_issues_count: 9`. Set
`last_validated: 2026-08-04` and `validated_by: ricchi`.

- [ ] **Step 4: Replace the validation install and assertions**

Keep the existing shebang, `set -euo pipefail`, virtual-environment creation,
and activation. Replace the existing install command with:

```bash
pip install --quiet \
  "agent-framework-core~=1.13.0" \
  "agent-framework-foundry~=1.10.4" \
  "agent-framework-foundry-hosting==1.0.0b260730" \
  "azure-ai-projects~=2.3.0" \
  "azure-identity~=1.25.3" \
  "mcp~=1.29.0" \
  "python-dotenv~=1.2.2"
```

Replace the existing `python -c` block with this exact heredoc:

```bash
python - <<'PY'
from importlib.metadata import version
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.ai.projects import AIProjectClient
from mcp import McpError

class OfflineCredential:
    def get_token(self, *scopes, **kwargs):
        raise RuntimeError("network is outside the import smoke")
    def close(self):
        return None

client = AIProjectClient(
    endpoint="https://example.services.ai.azure.com/api/projects/example",
    credential=OfflineCredential(),
)
assert callable(client.agents.update_details)
assert Agent and FoundryChatClient and ResponsesHostServer and McpError
assert version("agent-framework-core").startswith("1.13.")
assert version("agent-framework-foundry").startswith("1.10.")
assert version("azure-ai-projects").startswith("2.3.")
assert version("mcp").startswith("1.29.")
client.close()
print("ok hosted coherent stack")
print("ok update_details")
PY
```

Set `expected_output` to those two lines.

- [ ] **Step 5: Run pin validation and commit**

```bash
python3 - <<'PY'
from pathlib import Path
import tomllib
import yaml

pin_text = Path("skills/foundry-hosted-agents/references/upstream-pin.md").read_text()
pin = yaml.safe_load(pin_text.split("---", 2)[1])
project = tomllib.loads(
    Path("skills/foundry-hosted-agents/references/python/pyproject.toml").read_text()
)
deps = set(project["project"]["dependencies"])
expected = {
    "agent-framework-core~=1.13.0",
    "agent-framework-foundry~=1.10.4",
    "agent-framework-foundry-hosting==1.0.0b260730",
    "azure-ai-projects~=2.3.0",
    "azure-identity~=1.25.3",
    "mcp~=1.29.0",
    "python-dotenv~=1.2.2",
}
assert expected <= deps
for package, ceiling, reason in (
    ("azure-ai-projects", "2.4.0", "KI-009"),
    ("mcp", "2.0.0", "KI-010"),
):
    row = next(p for p in pin["packages"] if p["name"] == package)
    issue = next(k for k in pin["known_issues"] if k["id"] == reason)
    assert row["hold_below"] == ceiling and row["hold_reason"] == reason
    assert issue["status"] == "open"
assert pin["known_issues_count"] == 9
PY
git add skills/foundry-hosted-agents/references/upstream-pin.md \
  skills/foundry-hosted-agents/references/python/pyproject.toml
git commit -m "chore(foundry-hosted-agents): refresh coherent runtime pins" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
python3 scripts/run-pin-validation.py --base=origin/main
```

Expected: the structural assertions pass, then the changed-pin validator emits
both expected-output lines and exits `0`.

### Task 3: Restore the YAML single source of truth

**Files:**
- Modify: `skills/foundry-hosted-agents/SKILL.md:1056-1184`

- [ ] **Step 1: Set the skill version**

```yaml
metadata:
  version: "2.1.1"
```

- [ ] **Step 2: Replace dependency claims**

The dependency section must show the exact list from Task 2 and explain:

```markdown
`agent-framework-foundry==1.10.4` requires
`azure-ai-projects>=2.2,<2.4`, so this hosted-agent stack deliberately
uses `azure-ai-projects~=2.3.0`. Do not independently bump one package.
MCP remains on `~=1.29.0` because the hosting package requires `<2`.
```

Replace every stale current-stack token in the READ-FIRST callout, pitfalls,
MUST dependency text, and package table: Core 1.11, Foundry 1.10.1, hosting
`a260709`, MCP 1.28.1, and "alpha" status. The new hosting status is
**beta, pinned exact**.

In `references/upstream-pin.md`, update the hosting note and KI-008 item 2
from alpha `a260709` discipline to beta `b260730` discipline.

- [ ] **Step 3: Delete only the complete inline `azure.yaml` body**

Keep the section heading. Replace the existing MUST callout and the complete
inline `yaml` fence/body with exactly one copy of:

```markdown
> **MUST:** Copy the complete configuration verbatim from
> [`references/yaml/azure.yaml`](references/yaml/azure.yaml).
> Do not redefine it inline; that file is the canonical unified
> `host: azure.ai.agent` configuration used by the fixture.
```

Do not change `references/yaml/azure.yaml`.

- [ ] **Step 4: Run the SSOT probe**

Run Task 1 Step 2.

Expected: all assertions pass.

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-hosted-agents/SKILL.md \
  skills/foundry-hosted-agents/references/upstream-pin.md
git commit -m "fix(foundry-hosted-agents): align runtime stack and YAML SSOT [skill-rewrite]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 4: Make the fixture assert the selected stack

**Files:**
- Modify: `skills/foundry-hosted-agents/test-fixture/consumer_prompt.md:150-205`

- [ ] **Step 1: Add pyproject parity assertions after copying references**

```bash
grep -F '"agent-framework-core~=1.13.0"' "$work_dir/pyproject.toml"
grep -F '"agent-framework-foundry~=1.10.4"' "$work_dir/pyproject.toml"
grep -F '"agent-framework-foundry-hosting==1.0.0b260730"' "$work_dir/pyproject.toml"
grep -F '"azure-ai-projects~=2.3.0"' "$work_dir/pyproject.toml"
grep -F '"mcp~=1.29.0"' "$work_dir/pyproject.toml"
```

Each failed grep is a hard fixture failure. Preserve the existing rendered
`azure.yaml` byte-parity assertion, `azd up`, `update_details`, stable SDK
invoke, deterministic marker, and best-effort cleanup.

- [ ] **Step 2: Run local gates**

```bash
python3 scripts/validate-skills.py
python3 scripts/run-pin-validation.py --base=origin/main
python3 -m pytest -q scripts/tests/
git diff --check
```

Expected: all exit `0`.

- [ ] **Step 3: Commit**

```bash
git add skills/foundry-hosted-agents/test-fixture/consumer_prompt.md
git commit -m "test(foundry-hosted-agents): lock coherent container stack" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 5: Regenerate docs and obtain T3 proof

- [ ] **Step 1: Regenerate and validate**

```bash
python3 scripts/build-site.py --out docs/ --validate
python3 scripts/build-plugins.py --check
python3 scripts/validate-skills.py
git diff --check
```

Expected: all exit `0`.

- [ ] **Step 2: Commit generated docs**

```bash
git add -u docs/
git commit -m "docs: publish foundry-hosted-agents 2.1.1" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

- [ ] **Step 3: Push and open the PR**

```bash
git push -u origin HEAD
gh pr create \
  --title "fix: refresh foundry-hosted-agents coherent stack" \
  --body "Refreshes only foundry-hosted-agents to Core 1.13, Foundry 1.10.4, hosting b260730, Azure AI Projects 2.3, and MCP 1.29. Adds resolver-backed holds and removes duplicated inline azure.yaml. Requires live hosted, MCP/ACA, and GHCP fanout evidence."
gh pr checks --watch
```

- [ ] **Step 4: Inspect all required live evidence**

```bash
RUN_ID="$(gh run list --workflow skill-test.yml --branch "$(git branch --show-current)" --limit 1 --json databaseId --jq '.[0].databaseId')"
HOSTED_JOB="$(gh run view "$RUN_ID" --json jobs --jq '.jobs[] | select(.name | contains("foundry-hosted-agents")) | .databaseId')"
MCP_JOB="$(gh run view "$RUN_ID" --json jobs --jq '.jobs[] | select(.name | contains("foundry-mcp-aca")) | .databaseId')"
GHCP_JOB="$(gh run view "$RUN_ID" --json jobs --jq '.jobs[] | select(.name | contains("ghcp-hosted-agents")) | .databaseId')"
gh run view "$RUN_ID" --job "$HOSTED_JOB" --log > /tmp/foundry-hosted-agents-job.log
rg \
  'AZD_DEPLOY_SUCCEEDED|UPDATE_DETAILS_OK|INVOKE_LABEL|PASS via marker file' \
  /tmp/foundry-hosted-agents-job.log
gh run view "$RUN_ID" --json jobs --jq \
  '.jobs[] | select(.databaseId == '"$MCP_JOB"' or .databaseId == '"$GHCP_JOB"') | [.name,.conclusion] | @tsv'
```

Expected: the hosted leg contains deploy, update-details, invoke, and PASS.
The same run must show green `foundry-mcp-aca` and `ghcp-hosted-agents`
fanout legs in `gh run view "$RUN_ID"`.

- [ ] **Step 5: Attach evidence**

```bash
RUN_ID="$(gh run list --workflow skill-test.yml --branch "$(git branch --show-current)" --limit 1 --json databaseId --jq '.[0].databaseId')"
HOSTED_JOB="$(gh run view "$RUN_ID" --json jobs --jq '.jobs[] | select(.name | contains("foundry-hosted-agents")) | .databaseId')"
MCP_JOB="$(gh run view "$RUN_ID" --json jobs --jq '.jobs[] | select(.name | contains("foundry-mcp-aca")) | .databaseId')"
GHCP_JOB="$(gh run view "$RUN_ID" --json jobs --jq '.jobs[] | select(.name | contains("ghcp-hosted-agents")) | .databaseId')"
PR="$(gh pr view --json number --jq .number)"
CURRENT_BODY="$(gh pr view "$PR" --json body --jq .body)"
UPDATED_BODY="${CURRENT_BODY}"$'\n\n'"## Live Azure evidence"$'\n'"Run $RUN_ID: hosted job $HOSTED_JOB passed deploy, update_details, stable invoke, and marker; fanout jobs $MCP_JOB and $GHCP_JOB both concluded success."
gh api --method PATCH "repos/aiappsgbb/awesome-gbb/pulls/$PR" \
  -f body="$UPDATED_BODY" >/dev/null
```

Do not merge if either fanout leg fails.
