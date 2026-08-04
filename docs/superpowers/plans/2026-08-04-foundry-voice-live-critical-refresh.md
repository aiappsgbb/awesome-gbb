# Foundry Voice Live Critical Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh `foundry-voice-live` to OpenAI 2.53 and Voice Live SDK 1.3 while preserving the live-proven `2026-04-10` API and holding the incompatible Gradio 6 line.

**Architecture:** Pin the current compatible Voice Live, OpenAI, FastRTC, Gradio 5, and Identity packages as one set. Detect that Voice Live 1.3 defaults to `2026-07-15`, but pass `2026-04-10` explicitly in canonical and live paths so default drift cannot silently change behavior.

**Tech Stack:** Python 3.12, Azure Voice Live 1.3, OpenAI 2.53, FastRTC 0.0.34, Gradio 5.50, Azure Identity 1.25, live Voice Live WSS.

---

## File map

| File | Action |
|---|---|
| `skills/foundry-voice-live/references/upstream-pin.md` | Refresh pins, add Gradio hold, assert new SDK default |
| `skills/foundry-voice-live/SKILL.md` | Current SDK claims and explicit API-version contract |
| `skills/foundry-voice-live/test-fixture/consumer_prompt.md` | SDK 1.3 plus explicit 2026-04-10 WSS proof |
| `README.md` | Replace stale GA date and three-rung summary |
| `plugin.json` | Validator-required minimal PATCH `4.29.4` to `4.29.5` |
| `.github/plugin/marketplace.json` | Match both version fields to `4.29.5` |
| `docs/` | Regenerate |

## Execution precondition

Execute only after this approved plan is merged. Use
`superpowers:using-git-worktrees` to create a fresh worktree from current
`origin/main`.

```bash
git fetch origin main
test -z "$(git status --short)"
test -z "$(git diff --name-only origin/main...HEAD)"
grep -q '"version": "4.29.4"' plugin.json
```

Expected: both `test` commands and the serialized-wave plugin-base check exit
`0`. Every commit below must include
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

- [ ] **Step 2: Run the migration probe**

```bash
python3 - <<'PY'
from pathlib import Path

skill = Path("skills/foundry-voice-live/SKILL.md").read_text()
pin = Path("skills/foundry-voice-live/references/upstream-pin.md").read_text()
fixture = Path("skills/foundry-voice-live/test-fixture/consumer_prompt.md").read_text()

assert 'version: "2.53.0"' in pin, "OpenAI 2.53 pin missing"
assert 'version: "1.3.0"' in pin, "Voice Live 1.3 pin missing"
assert 'hold_below: "6.0.0"' in pin, "Gradio 6 hold missing"
assert 'api_version="2026-04-10"' in skill, "canonical explicit API version missing"
assert 'api_version="2026-04-10"' in fixture, "fixture explicit API version missing"
assert "2026-07-15" in pin, "SDK 1.3 default assertion missing"
PY
```

Expected: FAIL at `OpenAI 2.53 pin missing`.

### Task 2: Refresh the compatible pin

**Files:**
- Modify: `skills/foundry-voice-live/references/upstream-pin.md`

- [ ] **Step 1: Set exact package entries**

```yaml
  - name: openai
    version: "2.53.0"
    specifier: "~=2.53.0"
    source: pypi
  - name: azure-identity
    version: "1.25.3"
    specifier: "~=1.25.3"
    source: pypi
  - name: fastrtc
    version: "0.0.34"
    specifier: "~=0.0.34"
    source: pypi
  - name: gradio
    version: "5.50.0"
    specifier: "~=5.50.0"
    source: pypi
    hold_below: "6.0.0"
    hold_reason: KI-001
  - name: azure-ai-voicelive
    version: "1.3.0"
    specifier: "~=1.3.0"
    source: pypi
```

- [ ] **Step 2: Add the open Gradio issue**

```yaml
known_issues:
  - id: KI-001
    description: FastRTC 0.0.34 requires gradio>=4,<6, so Gradio 6 cannot resolve with the documented WebRTC stack.
    upstream_url: https://github.com/gradio-app/fastrtc/issues/428
    status: open
    workaround_location: SKILL.md § "Dependencies"
```

Set `known_issues_count: 1`, `last_validated: "2026-08-04"`, and
`validated_by: "ricchi"`.

Add the human audit section after Validation:

```markdown
## Known issues

### KI-001 - FastRTC blocks Gradio 6

FastRTC 0.0.34 requires `gradio>=4,<6`. Keep Gradio on the compatible
5.50 line until [FastRTC issue 428](https://github.com/gradio-app/fastrtc/issues/428)
is resolved by a released, live-validated FastRTC version.
```

- [ ] **Step 3: Replace validation install versions**

```bash
pip install --quiet \
  "openai~=2.53.0" \
  "azure-identity~=1.25.3" \
  "fastrtc~=0.0.34" \
  "gradio~=5.50.0" \
  "azure-ai-voicelive[aiohttp]~=1.3.0"
```

- [ ] **Step 4: Replace the Voice Live and OpenAI signature assertions**

```python
import inspect
from importlib.metadata import version

import gradio
from fastrtc import AsyncStreamHandler, WebRTC, wait_for_item
from openai import AsyncAzureOpenAI
from azure.ai.voicelive.aio import connect
from azure.ai.voicelive.models import AzureSemanticVad

connect_sig = inspect.signature(connect)
for name in ("endpoint", "credential", "api_version", "model"):
    assert name in connect_sig.parameters
assert connect_sig.parameters["api_version"].default == "2026-07-15"

openai_sig = inspect.signature(AsyncAzureOpenAI.__init__)
for name in (
    "azure_endpoint",
    "azure_deployment",
    "api_version",
    "websocket_base_url",
):
    assert name in openai_sig.parameters
assert hasattr(AsyncAzureOpenAI, "realtime")
assert AsyncStreamHandler and WebRTC and wait_for_item
assert version("openai").startswith("2.53.")
assert version("azure-identity").startswith("1.25.")
assert version("fastrtc").startswith("0.0.")
assert version("azure-ai-voicelive").startswith("1.3.")
assert version("gradio").startswith("5.50.")
fields = (
    {field.name for field in AzureSemanticVad.__attrs_attrs__}
    if hasattr(AzureSemanticVad, "__attrs_attrs__")
    else set(dir(AzureSemanticVad))
)
for field in ("create_response", "auto_truncate", "interrupt_response"):
    assert field in fields
print("voicelive-sdk-13-default-2026-07-15")
print("openai-253-realtime-surface")
print("fastrtc-gradio5-compatible")
```

Replace `expected_output` with this exact set so no marker from the removed
signature blocks remains orphaned:

```yaml
  expected_output:
    - "openai.AsyncAzureOpenAI OK"
    - "azure.identity.aio OK"
    - "fastrtc OK"
    - "gradio OK"
    - "voicelive-sdk-13-default-2026-07-15"
    - "openai-253-realtime-surface"
    - "fastrtc-gradio5-compatible"
    - "VALIDATION_PASSED"
```

In `docs_to_revalidate`, replace:

```yaml
  - "https://learn.microsoft.com/azure/ai-foundry/openai/concepts/audio"
```

with:

```yaml
  - "https://learn.microsoft.com/azure/foundry-classic/openai/concepts/audio"
```

Keep the 2026-04-10 API reference. Do not add a 2026-07-15 URL while it
returns 404.

- [ ] **Step 5: Correct the human pin table**

```markdown
| `openai` | `~=2.53.0` | Azure realtime client and websocket parameters |
| `azure-identity` | `~=1.25.3` | Async default credential and token provider |
| `fastrtc` | `~=0.0.34` | WebRTC handler; requires Gradio `<6` |
| `gradio` | `~=5.50.0` | Held below 6 until KI-001 closes |
| `azure-ai-voicelive` | `~=1.3.0` | Native connect; skill explicitly uses API `2026-04-10` |
```

- [ ] **Step 6: Run pin validation and commit**

```bash
python3 - <<'PY'
from pathlib import Path
import yaml

text = Path("skills/foundry-voice-live/references/upstream-pin.md").read_text()
data = yaml.safe_load(text.split("---", 2)[1])
gradio = next(p for p in data["packages"] if p["name"] == "gradio")
issue = next(k for k in data["known_issues"] if k["id"] == "KI-001")
assert gradio["hold_below"] == "6.0.0"
assert gradio["hold_reason"] == "KI-001"
assert issue["status"] == "open"
assert data["known_issues_count"] == 1
PY
git add skills/foundry-voice-live/references/upstream-pin.md
git commit -m "chore(foundry-voice-live): refresh compatible SDK pins" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
python3 scripts/run-pin-validation.py --base=origin/main
```

Expected: the structural assertions pass, then all expected-output strings
appear from the changed-pin validator.

### Task 3: Preserve the proven API version explicitly

**Files:**
- Modify: `skills/foundry-voice-live/SKILL.md`

- [ ] **Step 1: Set MINOR version**

```yaml
metadata:
  version: "1.4.0"
```

- [ ] **Step 2: Update all current-version prose**

Replace claims that Voice Live 1.2 is current with:

```markdown
The current validated native stack uses
`azure-ai-voicelive[aiohttp]~=1.3.0`. SDK 1.3 defaults
`connect()` to API `2026-07-15`, but this skill deliberately passes
`api_version="2026-04-10"` to preserve the live-proven GA contract.
Do not remove the explicit argument until a separate 2026-07-15 migration
is tested end-to-end.
```

Update OpenAI claims to `~=2.53.0`, Azure Identity to `~=1.25.3`, and retain
FastRTC `~=0.0.34` with Gradio `~=5.50.0`.

Apply those updates to every stale occurrence:

- the Rung 4 status paragraph near line 164;
- the Rung 4 explicit-version comment near line 195;
- the native install callout near line 244;
- the Dependencies fragment near lines 849-859;
- the aiohttp troubleshooting row near line 885; and
- the API-version scope text at the start of section 12.

The Dependencies fragment must use these exact bounded direct dependencies
while preserving the unrelated AV, settings, HTTP, and server dependencies:

```toml
"openai~=2.53.0",
"azure-identity~=1.25.3",
"fastrtc~=0.0.34",
"gradio~=5.50.0",
"azure-ai-voicelive[aiohttp]~=1.3.0",
```

Replace the opening of section 12 with:

```markdown
These features are live-proven on API `2026-04-10`. SDK 1.3 defaults to
`2026-07-15`, so every Rung 4 `connect()` call passes `2026-04-10`
explicitly; Rungs 2-3 continue to send equivalent payloads through the
OpenAI shim.
```

Under `### Dependencies`, add:

```markdown
> **Compatibility hold:** FastRTC `0.0.34` requires Gradio `<6`.
> Keep `gradio~=5.50.0` until `KI-001` closes; Gradio 6 is not an
> independently installable upgrade for this stack.
```

- [ ] **Step 3: Verify every Rung 4 connect call is explicit**

Each existing canonical `connect(...)` call must include this exact keyword
between `credential=` and `model=`:

```python
api_version="2026-04-10",
```

Preserve the existing session construction and event loop. Do not add a
`2026-07-15` runtime example.

Run this negative check before committing:

```bash
python3 - <<'PY'
from pathlib import Path

skill = Path("skills/foundry-voice-live/SKILL.md").read_text()
for old in (
    '"openai>=2.0.0"',
    '"azure-identity>=1.24.0"',
    '"fastrtc>=0.0.34"',
    '"gradio>=5.42.0"',
    'azure-ai-voicelive[aiohttp]~=1.2.0',
    "stable `1.2.0`",
    "# default in 1.2.0",
    "~=1.2.0",
):
    assert old not in skill, old
PY
```

- [ ] **Step 4: Commit**

```bash
git add skills/foundry-voice-live/SKILL.md
git commit -m "feat(foundry-voice-live): preserve GA API on SDK 1.3 [skill-rewrite]" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 4: Update the live WSS fixture

**Files:**
- Modify: `skills/foundry-voice-live/test-fixture/consumer_prompt.md:1-180`

- [ ] **Step 1: Replace broad skill loading with the audit echo**

The first required Bash action must be:

```bash
echo "skills/foundry-voice-live/SKILL.md"
```

State that the fixture is self-contained and the agent must not open the
whole skill file or invoke `copilot` recursively.

- [ ] **Step 2: Replace the package install**

```bash
python3 -m pip install --quiet \
  "azure-ai-voicelive[aiohttp]~=1.3.0" \
  "azure-identity~=1.25.3"
```

- [ ] **Step 3: Replace the false default comment and call**

Replace the fixture's current statement that `2026-04-10` is the SDK default
and must not be overridden with:

```markdown
The API version is `2026-04-10`, passed explicitly because SDK 1.3 now
defaults to `2026-07-15`.
```

```python
# SDK 1.3 defaults to 2026-07-15. This fixture deliberately preserves
# the skill's live-proven 2026-04-10 contract.
async with connect(
    endpoint=voicelive_endpoint,
    credential=cred,
    api_version="2026-04-10",
    model="gpt-realtime",
) as conn:
```

Preserve the text-turn payload, accepted event family, explicit error-event
failure, and deterministic marker. Emit runtime-only evidence after the WSS
opens and when the first accepted event arrives:

```python
print("VOICELIVE_CONNECT api_version=2026-04-10 sdk=1.3")
print(f"VOICELIVE_EVENT type={event.type}")
```

These strings must not appear in explanatory fixture prose outside the Python
program.

- [ ] **Step 4: Add negative migration assertions**

```bash
python3 - <<'PY'
from pathlib import Path

skill = Path("skills/foundry-voice-live/SKILL.md").read_text()
fixture = Path("skills/foundry-voice-live/test-fixture/consumer_prompt.md").read_text()
assert "~=1.2.0" not in fixture
assert 'SDK defaults: api_version="2026-04-10"' not in fixture
assert "the SDK default" not in fixture
assert "do not override" not in fixture
assert 'api_version="2026-04-10"' in skill
assert 'api_version="2026-04-10"' in fixture
PY
```

- [ ] **Step 5: Run local pre-metadata gates**

```bash
python3 scripts/run-pin-validation.py --base=origin/main
python3 -m pytest -q scripts/tests/
git diff --check
```

Expected: all exit `0`.

- [ ] **Step 6: Run the migration probe and commit**

Run Task 1 Step 2.

Expected: all assertions pass.

```bash
git add skills/foundry-voice-live/test-fixture/consumer_prompt.md
git commit -m "test(foundry-voice-live): prove explicit GA API on SDK 1.3" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 5: Synchronize plugin metadata and docs

- [ ] **Step 1: Set all plugin metadata versions to `4.29.5`**

Replace the complete `foundry-voice-live` README table row with:

```markdown
| [**foundry-voice-live**](skills/foundry-voice-live/) | Build real-time voice agents with Azure Voice Live (GA 2026-04-10) through a four-rung migration from Azure OpenAI Realtime to the native Voice Live SDK. Covers semantic VAD, echo cancellation, Neural HD voices, Foundry agent routing, benchmark patterns, and the FastRTC 0.0.34 plus Gradio 5.50 compatibility boundary |
```

This plan assumes the approved critical-wave order, where the Toolbox PR has
already moved the plugin to `4.29.4`. Set root and marketplace versions to:

```json
"version": "4.29.5"
```

If the merge-base plugin is not `4.29.4`, stop and rebase; do not invent a
different target inside this plan.

- [ ] **Step 2: Regenerate and validate**

```bash
python3 scripts/build-site.py --out docs/ --validate
python3 scripts/build-plugins.py --check
python3 scripts/validate-skills.py
git diff --check
```

Expected: all exit `0`.

- [ ] **Step 3: Commit**

```bash
git add README.md plugin.json .github/plugin/marketplace.json
git add -u docs/
git commit -m "docs: publish foundry-voice-live 1.4.0" \
  -m "Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
```

### Task 6: Obtain live WSS proof and open the PR

- [ ] **Step 1: Push and open the one-skill PR**

```bash
git push -u origin HEAD
gh pr create \
  --title "feat: refresh foundry-voice-live compatible SDK stack" \
  --body "Refreshes only foundry-voice-live to OpenAI 2.53 and Voice Live SDK 1.3. FastRTC keeps Gradio below 6 under KI-001. The runtime continues to pass API 2026-04-10 explicitly; 2026-07-15 adoption is deferred pending separate live proof."
gh pr checks --watch
```

- [ ] **Step 2: Inspect live WSS evidence**

```bash
RUN_ID="$(gh run list --workflow skill-test.yml --branch "$(git branch --show-current)" --limit 1 --json databaseId --jq '.[0].databaseId')"
JOB_ID="$(gh run view "$RUN_ID" --json jobs --jq '.jobs[] | select(.name | contains("foundry-voice-live")) | .databaseId')"
gh run view "$RUN_ID" --job "$JOB_ID" --log > /tmp/foundry-voice-live-job.log
rg 'VOICELIVE_CONNECT api_version=2026-04-10 sdk=1.3' /tmp/foundry-voice-live-job.log
rg 'VOICELIVE_EVENT type=' /tmp/foundry-voice-live-job.log
rg 'PASS via marker file' /tmp/foundry-voice-live-job.log
```

Expected: the fixture log shows the explicit API version, at least one
accepted server event, and the deterministic PASS marker.

- [ ] **Step 3: Attach evidence**

```bash
RUN_ID="$(gh run list --workflow skill-test.yml --branch "$(git branch --show-current)" --limit 1 --json databaseId --jq '.[0].databaseId')"
JOB_ID="$(gh run view "$RUN_ID" --json jobs --jq '.jobs[] | select(.name | contains("foundry-voice-live")) | .databaseId')"
PR="$(gh pr view --json number --jq .number)"
CURRENT_BODY="$(gh pr view "$PR" --json body --jq .body)"
UPDATED_BODY="${CURRENT_BODY}"$'\n\n'"## Live Azure evidence"$'\n'"Run $RUN_ID, job $JOB_ID: Voice Live SDK 1.3 opened WSS with explicit API 2026-04-10, received an accepted server event, and passed the deterministic marker. API 2026-07-15 was not exercised or adopted."
gh api --method PATCH "repos/aiappsgbb/awesome-gbb/pulls/$PR" \
  -f body="$UPDATED_BODY" >/dev/null
```

Do not merge if the fixture relies on the SDK default or the accepted event is
absent.
