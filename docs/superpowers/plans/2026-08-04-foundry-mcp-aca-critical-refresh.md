# Foundry MCP on ACA Critical Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh `foundry-mcp-aca` to MCP 1.29, App Containers 5, and Cosmos 4.16.3 while machine-enforcing the incompatible MCP 2 boundary.

**Architecture:** Keep FastMCP 2.14.7 and MCP 1.29 as the transport stack, with separate machine holds for FastMCP 3 and MCP 2. Adopt the App Containers 5 hybrid model and encode its alias behavior in T2; extend the existing ACR-remote-build plus `azd provision` fixture to read the deployed app through the 5.0 management SDK after the wire-protocol hard gates pass.

**Tech Stack:** Python 3.12, FastMCP 2.14, MCP 1.29, Azure Container Apps SDK 5.0, Azure Cosmos 4.16, azd, ACA, Copilot-CLI T3.

---

## File map

| File | Action |
|---|---|
| `skills/foundry-mcp-aca/references/upstream-pin.md` | Refresh seven pins, add `KI-002`, strengthen model/query probes |
| `skills/foundry-mcp-aca/SKILL.md` | Cap MCP below 2 and bump `1.2.4` |
| `skills/foundry-mcp-aca/test-fixture/consumer_prompt.md` | Live App Containers 5 retrieval |
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

- [ ] **Step 1: Run baseline**

```bash
python3 scripts/validate-skills.py
python3 -m pytest -q scripts/tests/
```

Expected: both exit `0`.

- [ ] **Step 2: Run the refresh probe**

```bash
python3 - <<'PY'
from pathlib import Path

skill = Path("skills/foundry-mcp-aca/SKILL.md").read_text()
pin = Path("skills/foundry-mcp-aca/references/upstream-pin.md").read_text()
fixture = Path("skills/foundry-mcp-aca/test-fixture/consumer_prompt.md").read_text()

assert "mcp>=1.24.0,<2.0.0" in skill, "MCP upper bound missing"
assert 'version: "1.29.0"' in pin, "MCP 1.29 pin missing"
assert 'hold_below: "2.0.0"' in pin, "MCP 2 hold missing"
assert 'version: "5.0.0"' in pin, "App Containers 5 pin missing"
assert 'version: "4.16.3"' in pin, "Cosmos 4.16.3 pin missing"
assert "ContainerAppsAPIClient" in fixture, "live SDK retrieval missing"
PY
```

Expected: FAIL at `MCP upper bound missing`.

### Task 2: Refresh pins and add executable compatibility probes

**Files:**
- Modify: `skills/foundry-mcp-aca/references/upstream-pin.md:11-135`

- [ ] **Step 1: Set the exact package contract**

```yaml
packages:
  - name: fastmcp
    source: pypi
    version: "2.14.7"
    hold_below: "3.0.0"
    hold_reason: KI-001
  - name: mcp
    source: pypi
    version: "1.29.0"
    hold_below: "2.0.0"
    hold_reason: KI-002
  - name: azure-mgmt-appcontainers
    source: pypi
    version: "5.0.0"
  - name: azure-cosmos
    source: pypi
    version: "4.16.3"
  - name: azure-identity
    source: pypi
    version: "1.25.3"
  - name: aiohttp
    source: pypi
    version: "3.13.5"
  - name: azure-keyvault-secrets
    source: pypi
    version: "4.11.0"
```

Preserve each package's existing changelog URL and update its note to match
the selected version.

- [ ] **Step 2: Add MCP `KI-002`**

```yaml
  - id: KI-002
    description: No released FastMCP line supports MCP 2; FastMCP 2.14.7 and current FastMCP 3.x require mcp>=1.24,<2.
    upstream_url: https://py.sdk.modelcontextprotocol.io/migration/
    status: open
    workaround_location: SKILL.md § "Pin `fastmcp<3.0.0`"
```

Set `known_issues_count: 2`, `last_validated: 2026-08-04`, and
`validated_by: ricchi`.

- [ ] **Step 3: Replace validation install commands**

```bash
pip install --quiet \
  "fastmcp~=2.14.7" \
  "mcp~=1.29.0" \
  "azure-mgmt-appcontainers~=5.0.0" \
  "azure-cosmos~=4.16.3" \
  "azure-identity~=1.25.3" \
  "azure-keyvault-secrets~=4.11.0" \
  "aiohttp~=3.13.5"
```

- [ ] **Step 4: Add exact model and SDK assertions**

```python
from importlib.metadata import version
import aiohttp
from fastmcp import FastMCP
from mcp import ClientSession
from azure.cosmos.aio import CosmosClient
from azure.cosmos.aio import ContainerProxy
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.mgmt.appcontainers import ContainerAppsAPIClient
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
assert hasattr(CosmosClient, "get_database_client")
assert callable(ContainerProxy.query_items)
query_doc = ContainerProxy.query_items.__doc__ or ""
assert "partition_key" in query_doc and "max_item_count" in query_doc
assert hasattr(ContainerAppsAPIClient, "close")
assert FastMCP and ClientSession and DefaultAzureCredential and SecretClient
assert aiohttp.ClientSession
assert version("mcp").startswith("1.29.")
assert version("azure-mgmt-appcontainers").startswith("5.")
assert version("azure-cosmos").startswith("4.16.")
print("ok mcp1 compatible stack")
print("ok appcontainers5 hybrid model")
print("ok cosmos416 async surface")
```

Set all three print lines as `expected_output`.

- [ ] **Step 5: Correct the human pin table**

The table below frontmatter must show exactly:

```markdown
| `fastmcp` | PyPI | **2.14.7** | Known-good 2.x line; keep `<3.0.0` |
| `mcp` | PyPI | **1.29.0** | Keep `<2.0.0` until KI-002 closes |
| `azure-mgmt-appcontainers` | PyPI | **5.0.0** | ACA hybrid management SDK |
| `azure-cosmos` | PyPI | **4.16.3** | Async Cosmos SDK |
| `azure-identity` | PyPI | **1.25.3** | Keyless auth |
| `azure-keyvault-secrets` | PyPI | **4.11.0** | Secret metadata tool |
| `aiohttp` | PyPI | **3.13.5** | Async HTTP transport |
```

- [ ] **Step 6: Run pin validation and commit**

```bash
python3 - <<'PY'
from pathlib import Path
import yaml

text = Path("skills/foundry-mcp-aca/references/upstream-pin.md").read_text()
frontmatter, body = text.split("---", 2)[1:]
data = yaml.safe_load(frontmatter)
rows = {p["name"]: p for p in data["packages"]}
assert rows["fastmcp"]["hold_reason"] == "KI-001"
assert rows["mcp"]["hold_below"] == "2.0.0"
assert rows["mcp"]["hold_reason"] == "KI-002"
issues = {k["id"]: k for k in data["known_issues"]}
assert issues["KI-001"]["status"] == "open"
assert issues["KI-002"]["status"] == "open"
assert data["known_issues_count"] == 2
for name, version in (
    ("fastmcp", "2.14.7"),
    ("mcp", "1.29.0"),
    ("azure-mgmt-appcontainers", "5.0.0"),
    ("azure-cosmos", "4.16.3"),
    ("azure-identity", "1.25.3"),
    ("azure-keyvault-secrets", "4.11.0"),
    ("aiohttp", "3.13.5"),
):
    assert f"| `{name}` | PyPI | **{version}** |" in body
PY
git add skills/foundry-mcp-aca/references/upstream-pin.md
git commit -m "chore(foundry-mcp-aca): refresh compatible SDK pins" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
python3 scripts/run-pin-validation.py --base=origin/main
```

Expected: the structural assertions pass, then all three expected-output lines
appear from the changed-pin validator.

### Task 3: Tighten the consumer dependency contract

**Files:**
- Modify: `skills/foundry-mcp-aca/SKILL.md:130-197,483-486`

- [ ] **Step 1: Set PATCH version**

```yaml
metadata:
  version: "1.2.4"
```

- [ ] **Step 2: Replace the requirements fragment**

The dependency lines must be:

```text
fastmcp>=2.14.7,<3.0.0
mcp>=1.24.0,<2.0.0
azure-cosmos[aio]>=4.16.3,<5.0.0
azure-identity>=1.25.3,<2.0.0
azure-keyvault-secrets>=4.11.0,<5.0.0
aiohttp>=3.13.5,<4.0.0
```

Add immediately below:

```markdown
MCP 2 is not currently installable with any released FastMCP line.
Keep the explicit `<2.0.0` ceiling until `KI-002` closes; do not let an
unbounded direct `mcp` dependency override FastMCP's resolver constraint.
```

Do not add App Containers model code to the skill; that behavior is a pin
regression assertion only.

Apply the same bounded versions to the second requirements fragment near the
MCP server deployment section (`SKILL.md:483-486`). Verify no unbounded
`mcp>=1.10.0`, `azure-cosmos>=4.15.0`, or old Azure Identity line remains.

- [ ] **Step 3: Run the refresh probe**

Run Task 1 Step 2.

Expected: all assertions pass except `live SDK retrieval missing`.

- [ ] **Step 4: Commit**

```bash
git add skills/foundry-mcp-aca/SKILL.md
git commit -m "fix(foundry-mcp-aca): cap MCP below incompatible v2 [skill-rewrite]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 4: Prove App Containers 5 against the deployed app

**Files:**
- Modify: `skills/foundry-mcp-aca/test-fixture/consumer_prompt.md`

- [ ] **Step 1: Extend the hard-gate list**

After the existing ACR remote build, `azd provision`, optional auth gate, and
MCP HTTP roundtrip, add:

```markdown
3. **App Containers SDK 5 retrieves the deployed app** and reports a
   non-empty provisioning state or latest revision name.
```

- [ ] **Step 2: Correct the deployment-path prose**

Replace the stale `azd up` success/failure claims at the fixture introduction,
hard-gate list, Step 4 preamble, failure-marker list, and final warning (current
lines 6, 158-159, 197, 677, and 713) with the actual existing path:

```markdown
ACR remote build followed by `azd provision`
```

Do not replace the working deployment commands in Step 4. Preserve the current
performance comparison near line 453, where saying `azd provision` is faster
than `azd up` is accurate rather than stale.

- [ ] **Step 3: Add the workspace-scoped SDK environment**

```bash
python3 -m venv "$PROJECT_DIR/.venv-sdk"
"$PROJECT_DIR/.venv-sdk/bin/pip" install --quiet \
  "azure-mgmt-appcontainers~=5.0.0" \
  "azure-identity~=1.25.3"
```

- [ ] **Step 4: Add the exact live retrieval program**

```python
import os

from azure.identity import DefaultAzureCredential
from azure.mgmt.appcontainers import ContainerAppsAPIClient

app_name = os.environ["APP_NAME"]
with DefaultAzureCredential() as credential:
    client = ContainerAppsAPIClient(
        credential,
        os.environ["AZURE_SUBSCRIPTION_ID"],
    )
    app = client.container_apps.get("rg-awesome-gbb-ci", app_name)
    state = app.properties.provisioning_state
    revision = app.properties.latest_revision_name
    assert state or revision, app.as_dict()
    print(f"APPCONTAINERS5_GET name={app.name} state={state} revision={revision}")
    client.close()
```

Write that program to `$PROJECT_DIR/verify_appcontainers.py`, then run:

```bash
export APP_NAME
"$PROJECT_DIR/.venv-sdk/bin/python" "$PROJECT_DIR/verify_appcontainers.py"
```

`APP_NAME` is set by the existing deployment block earlier in the same fixture;
export that existing value rather than inventing a second app name.

Treat SDK install, auth, retrieval, and the assertion as hard failures. Add
`APPCONTAINERS5_GET` to the fixture evidence sidecar/verification, add a
matching `SMOKE_RESULT=FAIL App Containers 5 retrieval failed` command, and
write the deterministic PASS marker only after this program succeeds. Keep
cleanup best-effort.

- [ ] **Step 5: Run local gates**

```bash
python3 scripts/validate-skills.py
python3 scripts/run-pin-validation.py --base=origin/main
python3 -m pytest -q scripts/tests/
git diff --check
```

Expected: all exit `0`.

- [ ] **Step 6: Commit**

```bash
git add skills/foundry-mcp-aca/test-fixture/consumer_prompt.md
git commit -m "test(foundry-mcp-aca): prove App Containers 5 live" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 5: Regenerate docs and obtain T3 proof

- [ ] **Step 1: Regenerate and commit**

```bash
python3 scripts/build-site.py --out docs/ --validate
python3 scripts/build-plugins.py --check
python3 scripts/validate-skills.py
git add -u docs/
git commit -m "docs: publish foundry-mcp-aca 1.2.4" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

- [ ] **Step 2: Push and open the PR**

```bash
git push -u origin HEAD
gh pr create \
  --title "fix: refresh foundry-mcp-aca compatible SDK stack" \
  --body "Refreshes only foundry-mcp-aca to MCP 1.29, App Containers 5.0, and Cosmos 4.16.3. MCP 2 remains blocked by FastMCP and is machine-held below 2. T3 proves ACA deploy, MCP initialize/tools-list, and App Containers 5 live retrieval; Cosmos remains T2 signature coverage because CI has no standing Cosmos account."
gh pr checks --watch
```

- [ ] **Step 3: Inspect and attach live evidence**

```bash
RUN_ID="$(gh run list --workflow skill-test.yml --branch "$(git branch --show-current)" --limit 1 --json databaseId --jq '.[0].databaseId')"
JOB_ID="$(gh run view "$RUN_ID" --json jobs --jq '.jobs[] | select(.name | contains("foundry-mcp-aca")) | .databaseId')"
gh run view "$RUN_ID" --job "$JOB_ID" --log > /tmp/foundry-mcp-aca-job.log
rg 'initialize HTTP=200' /tmp/foundry-mcp-aca-job.log
rg 'tools/list HTTP=200' /tmp/foundry-mcp-aca-job.log
rg 'APPCONTAINERS5_GET' /tmp/foundry-mcp-aca-job.log
rg 'PASS via marker file' /tmp/foundry-mcp-aca-job.log
RUN_ID="$(gh run list --workflow skill-test.yml --branch "$(git branch --show-current)" --limit 1 --json databaseId --jq '.[0].databaseId')"
JOB_ID="$(gh run view "$RUN_ID" --json jobs --jq '.jobs[] | select(.name | contains("foundry-mcp-aca")) | .databaseId')"
PR="$(gh pr view --json number --jq .number)"
CURRENT_BODY="$(gh pr view "$PR" --json body --jq .body)"
UPDATED_BODY="${CURRENT_BODY}"$'\n\n'"## Live Azure evidence"$'\n'"Run $RUN_ID, job $JOB_ID: ACR remote build plus azd provision, MCP initialize/tools-list, App Containers 5 live retrieval, and deterministic marker passed. Cosmos 4.16.3 is T2 import/signature coverage only; no live Cosmos claim is made."
gh api --method PATCH "repos/aiappsgbb/awesome-gbb/pulls/$PR" \
  -f body="$UPDATED_BODY" >/dev/null
```

Do not merge if `APPCONTAINERS5_GET` or the MCP roundtrip evidence is absent.
