---
schema_version: 2
freshness_tier: B
automation_tier: auto

upstream:
  type: pypi_package
  notes: |
    Routines are a PREVIEW feature exposed under the `client.beta.routines`
    surface in azure-ai-projects 2.2.0+. The SDK proxy auto-injects the
    `Foundry-Features: Routines=V1Preview` REST header on every call.
    Regional preview: East US, East US 2, West US, West US 2, West Central
    US, North Central US, Sweden Central, Japan East.

packages:
  - name: azure-ai-projects
    source: pypi
    version: "2.3.0"
    upstream_changelog: https://pypi.org/project/azure-ai-projects/#history
    notes: |
      First version that ships the routines surface (client.beta.routines)
      with the _OperationMethodHeaderProxy that auto-sets the
      Foundry-Features header. Earlier 2.1.x versions do NOT have
      client.beta.routines and raise AttributeError.
  - name: azure-identity
    source: pypi
    version: "1.25.3"
    upstream_changelog: https://pypi.org/project/azure-identity/#history
    notes: |
      DefaultAzureCredential for authentication. Stable, low churn.

docs_to_revalidate:
  - https://learn.microsoft.com/azure/foundry/agents/concepts/routines
  - https://learn.microsoft.com/azure/foundry/agents/how-to/use-routines
  - https://pypi.org/project/azure-ai-projects/

known_issues:
  - id: KI-001
    title: "azd ai routine create --trigger schedule inline form not supported in preview"
    description: |
      The azd extension's `--trigger schedule --cron …` inline-flag form
      is timer-only in preview. Schedule (recurring) routines MUST be
      created from a YAML manifest via `azd ai routine create --file
      routine.yaml` OR via the Python SDK (preferred per Pattern 16 —
      the preview CLI flag surface drifts between releases).
    upstream_url: null
    status: documented
    notes: Documented in SKILL.md § 8 limitation 7.
  - id: KI-002
    title: "azd ai routine does not list run history"
    description: |
      The preview azd extension exposes `routine list` and routine CRUD
      but NOT a `routine list-runs` (or equivalent). Use the Python SDK
      (`client.beta.routines.list_runs(routine_name=...)`), the REST API,
      or the Foundry portal to inspect run history.
    upstream_url: null
    status: documented
    notes: Documented in SKILL.md § 6 and § 8 limitation 8.
  - id: KI-003
    title: "Regional preview — eight regions only"
    description: |
      Routines are not available in every Foundry region. The 8 preview
      regions are: East US, East US 2, West US, West US 2, West Central US,
      North Central US, Sweden Central, Japan East. Project creation in
      any other region will not expose the routines surface even after
      installing azure-ai-projects 2.2.0.
    upstream_url: null
    status: documented
    notes: Documented in SKILL.md § 2 and § 8 limitation 4.
  - id: KI-004
    title: "Prompt-only agents without configured agent identity are rejected"
    description: |
      The service rejects a routine action whose `agent_name` resolves to
      a prompt-only agent without a configured agent identity. The agent
      must be a prompt-agent version published via `agents.create_version`
      OR a hosted agent deployed via foundry-hosted-agents. Both shapes
      provide the agent identity routines require.
    upstream_url: null
    status: documented
    notes: Documented in SKILL.md § 2 prereq 2 and § 8 limitation 6.

validation:
  requires:
    - pypi
  runnable: true
  script: |
    #!/usr/bin/env bash
    set -euo pipefail
    python -m venv .venv-routines
    . .venv-routines/bin/activate
    pip install --quiet "azure-ai-projects~=${PINNED_VERSION:-2.3.0}" "azure-identity~=1.25"
    python -c "
    import azure.ai.projects as _m
    print(f'azure-ai-projects=={_m.__version__}')

    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    # Instantiate against a no-op endpoint to access the .beta.routines proxy
    c = AIProjectClient(endpoint='https://example.invalid', credential=DefaultAzureCredential())
    assert hasattr(c.beta, 'routines'), 'client.beta.routines missing'

    ro = c.beta.routines
    # Confirm proxy auto-injects the Foundry-Features header
    assert type(ro).__name__ == '_OperationMethodHeaderProxy', \
        f'expected proxy, got {type(ro).__name__}'

    # Confirm the full method surface this skill documents
    expected = {'create_or_update', 'dispatch', 'enable', 'disable',
                'get', 'list', 'list_runs', 'delete'}
    actual = {m for m in dir(ro) if not m.startswith('_')}
    missing = expected - actual
    assert not missing, f'missing routine methods: {missing}'

    print('routines-surface-ok')
    print('routines-methods:', sorted(expected))
    "
  expected_output:
    - "azure-ai-projects==2.3.0"
    - "routines-surface-ok"
    - "routines-methods:"

last_validated: 2026-07-02
validated_by: copilot-bot
known_issues_count: 4
---

# Upstream pin — `foundry-routines` skill

This file is the **machine-readable validation contract** for the
`foundry-routines` skill. The YAML front-matter above is parsed by
`scripts/check-freshness.py` weekly; the prose below is the human
audit trail. Keep them in sync.

---

## 1. Pin

| Field | Value |
|-------|-------|
| **Upstream** | `azure-ai-projects` (PyPI) |
| **Pinned version** | **2.2.0** (preview routines surface) |
| **Cap window** | `~=2.2.0` ≡ `>=2.2.0, <2.3.0` |
| **License** | MIT |
| **First authored against** | 2026-06-15 |
| **Last re-validated** | 2026-06-15 |

The skill wraps the **routines preview surface** added in
`azure-ai-projects` 2.2.0 (`client.beta.routines`). The SDK proxy
auto-injects the `Foundry-Features: Routines=V1Preview` REST header
on every call, so consumers do not need to set it manually.

---

## 2. Pinned packages

| Package | Source | Pinned version | Notes |
|---------|--------|----------------|-------|
| `azure-ai-projects` | PyPI | **2.2.0** | First version with `client.beta.routines`. Earlier 2.1.x raises `AttributeError`. |
| `azure-identity` | PyPI | **1.25.3** | `DefaultAzureCredential`. Stable, low churn. |

---

## 3. Verification checklist (the executable contract)

The `validation.script` above runs a pure PyPI import smoke against the
pinned `azure-ai-projects` version. It proves:

1. The SDK installs cleanly within its `~=2.2.0` cap window.
2. `client.beta.routines` exists (the preview surface is present).
3. The accessor returns a `_OperationMethodHeaderProxy` (the wrapper
   that auto-injects the `Foundry-Features: Routines=V1Preview`
   header) — so SKILL.md's claim that consumers don't need to set
   the header manually still holds.
4. All 8 documented methods (`create_or_update`, `dispatch`, `enable`,
   `disable`, `get`, `list`, `list_runs`, `delete`) are exposed on
   the proxy.

**Expected output** must contain (substring match):

- `azure-ai-projects==2.2.0`
- `routines-surface-ok`
- `routines-methods:`

**Failure signatures** (treat as upstream regression — report distinctly):

- `AttributeError: 'BetaOperations' object has no attribute 'routines'`
  → the routines surface was removed (catastrophic — re-author the skill)
- `missing routine methods: {…}` → a documented method was renamed or
  removed (update SKILL.md and bump MAJOR)

> **Live Azure E2E** is covered by the fixture at
> `skills/foundry-routines/test-fixture/consumer_prompt.md`, which runs
> in the `copilot-cli-matrix` job of `.github/workflows/skill-test.yml`
> against the project at `aif-awesome-gbb-ci`. That fixture proves the
> end-to-end create → dispatch → list → cleanup cycle works against a
> real Foundry deployment. This pin script is the import-surface gate
> for weekly drift detection.

---

## 4. Live smoke results (last successful run)

| Check | Result | Evidence |
|-------|--------|----------|
| `azure-ai-projects~=2.2.0` install | ✅ | `azure-ai-projects==2.2.0` |
| `client.beta.routines` surface present | ✅ | `routines-surface-ok` |
| 8-method proxy intact | ✅ | `routines-methods: ['create_or_update', 'delete', 'disable', 'dispatch', 'enable', 'get', 'list', 'list_runs']` |
| Live E2E (Sweden Central) | ✅ | See `copilot-cli-matrix` job log for `foundry-routines` leg |

Captured at `last_validated: 2026-06-15` by `copilot-bot`.

---

## 5. Known issues at this pin

### KI-001 — `azd ai routine create --trigger schedule` inline form not supported

**Upstream tracker:** none (preview-CLI gap, documented in
`learn.microsoft.com/azure/foundry/agents/how-to/use-routines`)
**Status:** documented

The azd extension's inline-flag form (`--trigger schedule --cron …`) is
**timer-only** in preview. Recurring schedule routines MUST be created
from a YAML manifest:

```bash
azd extension install azure.ai.routines
azd ai routine create --file routine.yaml
```

**Workaround (preferred):** use the Python SDK
`client.beta.routines.create_or_update(...)` — see SKILL.md § 3. Per
catalog Pattern 16, preview-CLI flag surfaces drift between releases;
the SDK is the GA-stable contract.

### KI-002 — `azd ai routine` does not list run history

**Upstream tracker:** none
**Status:** documented

The preview azd extension does not surface `list_runs`. To inspect run
history use:

- Python SDK: `client.beta.routines.list_runs(routine_name=...)`
- REST: `GET {endpoint}/routines/{name}/runs` with
  `Foundry-Features: Routines=V1Preview` header
- Foundry portal: routine detail page run table

### KI-003 — Regional preview (8 regions only)

**Upstream tracker:** none (regional rollout in progress)
**Status:** documented

Available regions as of the pin date:

- East US, East US 2
- West US, West US 2
- West Central US, North Central US
- Sweden Central
- Japan East

Provisioning a Foundry project in any other region will not expose the
routines surface even with `azure-ai-projects` 2.2.0 installed. The CI
infrastructure for this catalog (`aif-awesome-gbb-ci` in Sweden Central)
qualifies; verify your customer project's region before quoting routines.

### KI-004 — Prompt-only agents without configured agent identity are rejected

**Upstream tracker:** none (documented preview limitation)
**Status:** documented

The service rejects a routine `action` whose `agent_name` resolves to a
prompt-only agent without a configured agent identity. Use:

- A prompt-agent version published via `project.agents.create_version(...)`
  (see `foundry-prompt-agents` § 3) — these have an agent identity by default.
- A hosted agent deployed via `azd up` (see `foundry-hosted-agents`).

---

## 6. Re-pin procedure

When `azure-ai-projects` advances:

1. **Check PyPI for new version**:
   ```bash
   pip index versions azure-ai-projects
   ```
2. **Inspect changelog** at
   <https://pypi.org/project/azure-ai-projects/#history> — look for any
   notes on `client.beta.routines` or routines-related fixes.
3. **Update front-matter**: set `packages[0].version` to the new
   version. If the new pin is still in the `>=2.2.0,<2.3.0` cap window
   (e.g. 2.2.1, 2.2.2, …) leave the existing `~=2.2.0` cap alone — the
   compatible-release operator auto-covers patches. If the new pin
   crosses the cap (e.g. 2.3.0), bump the cap AND update the version
   pin.
4. **Run the validation script**:
   ```bash
   PINNED_VERSION=<new> bash -c "$(yq '.validation.script' upstream-pin.md)"
   ```
5. **Verify expected output**: each `expected_output[]` substring must
   appear in the script's stdout.
6. **Re-run the live fixture** in CI by pushing an empty commit to
   trigger the `foundry-routines` leg of `skill-test.yml`. The leg
   MUST emit `PASS via marker file (deterministic)`.
7. **Update audit trail**:
   - `last_validated: <today>`
   - `validated_by: <handle>`
8. **Bump SKILL.md `metadata.version` PATCH** (e.g., `1.0.0` → `1.0.1`)
   per AGENTS.md § 5. PATCH unless the SDK surface changed (then MAJOR).
9. **Open PR**: title `chore(foundry-routines): re-pin → <new-version>`.
   Touch ONLY `references/upstream-pin.md` and `SKILL.md` frontmatter.
   The `automation-pr-gate.yml` workflow enforces this.

---

## 7. URLs to re-validate (link-rot detector input)

- <https://learn.microsoft.com/azure/foundry/agents/concepts/routines>
- <https://learn.microsoft.com/azure/foundry/agents/how-to/use-routines>
- <https://pypi.org/project/azure-ai-projects/>

---

## 8. Notes for the coding agent

> **If you're GHCP picking up a refresh issue for this skill:**
>
> 1. The `validation.script` in the front-matter is your spec. Run it.
>    Substitute `PINNED_VERSION` with the candidate new version.
> 2. If it passes, update front-matter (`packages[0].version`,
>    `last_validated`, `validated_by: copilot-bot`) and bump SKILL.md
>    `metadata.version` PATCH. Touch nothing else unless the issue body
>    explicitly asks for a body rewrite.
> 3. If the script fails because the SDK surface changed (e.g. a
>    routine method was renamed), STOP. Comment on the issue with the
>    failure output. Do **not** open a PR rewriting SKILL.md without
>    `[skill-rewrite]` in the commit message — the
>    `automation-pr-gate.yml` workflow will reject it.
> 4. The live E2E fixture (`test-fixture/consumer_prompt.md`) is the
>    other gate. If your refresh succeeds at the import level but the
>    fixture fails in CI, the SDK surface drift may have broken a
>    runtime contract the import smoke can't catch. Re-read the
>    fixture's failure log and either fix the fixture (if the SDK
>    legitimately changed) or hand-back to a human.
