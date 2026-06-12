# awesome-gbb v0.6.0 critical-path design

> **Status:** Draft, pending human ratification.
> **Companion plans:** `docs/superpowers/plans/2026-06-12-v0-6-0-slice-{1..5}-*.md`
> **Tracker:** [aiappsgbb/threadlight-skills#35](https://github.com/aiappsgbb/threadlight-skills/issues/35)
> **Branch:** `unsafecode/plan-v0-6-0-critical-path`

## 1 · Problem

`threadlight-production-ready` v0.5.0 shipped 61 must-fix recipes but
**cannot pass a credible real-customer pilot** until 10 upstream
landings in `awesome-gbb` are complete. The threadlight side will
flip each `kind: manual → kind: sibling-skill` recipe as the
corresponding awesome-gbb item ships; that flip work is **out of
scope here** and lives in the threadlight repo's
`sibling-skill-flip-protocol.md` runbook.

This design covers **only the awesome-gbb side**: the 10 upstream
issues sliced into **5 PRs for v0.6.0 + 1 deferred plan for v0.6.x**,
with the contracts (Python module API, CLI shim, JSON output, fixture
shape) each skill must expose so threadlight can consume them.

## 2 · Slicing

The 10 issues map to slices along **skill boundaries + ROI tiers**:

| Slice | PR shape | Skills | Issues | ROI rank (from tracker) |
|---|---|---|---|---|
| **1** | Multi-skill extensions (3) | `foundry-observability`, `foundry-evals`, `foundry-agt` | #245, #247, #248 | 1, 4, 6 |
| **2** | Single-skill extension | `citadel-spoke-onboarding` | #246 | 3 |
| **3** | Single-skill NEW | `foundry-rbac-audit` | #268 | 2 |
| **4** | Single-skill NEW | `azure-monitor-alert-baseline` | #272 | 5 |
| **5** | Multi-skill NEW (2) | `azure-backup-readiness`, `azure-resource-diagnostics` | #267, #271 | 7, 7 |
| **Deferred** | Separate spec, picked up post-v0.6.0 | `foundry-iq`, `foundry-hosted-agents` | #269, #270 | 8, 8 |

### 2.1 · Why this shape

- **Slice 1 groups the three extensions** because they share a
  literal commit pattern (`scripts/<module>.py` + SKILL.md § + PATCH
  bump + one new import line in the existing fixture). One PR with
  `[multi-skill]` commit tag costs ~3 matrix legs but ships three
  hidden-multiplier flips in one threadlight-side update round —
  the tracker's highest-ROI move.
- **Slice 2 is solo** because of the Citadel coordination zone
  (#244 is OPEN, queued behind the MAF wave). Keeping #246 narrow
  and additive (a new `scripts/` module + new §) means it does NOT
  rebase-conflict with #244's planned SHA refresh + section adds.
- **Slices 3 and 4 are solo NEW** because each ships a `plugin.json`
  MINOR bump, a new fixture, and registration in
  `.github/skill-deps.yml` — collapsing them into one PR doubles
  reviewer cost without saving CI cost (matrix fans out per-leg
  anyway).
- **Slice 5 bundles two NEW** because both are Order-7 (lowest
  urgency), both produce JSON probes from a Python module + CLI shim
  (identical shape), and one shared `plugin.json` MINOR bump is
  cheaper than two stacked bumps.
- **Deferred slice ships a spec but no plan** so a future session
  can pick up #269 + #270 without re-deriving contracts. Per the
  tracker: "Pick up opportunistically when working on those skills
  for other reasons."

### 2.2 · What this slicing intentionally does NOT do

- **No mega-PR.** All 10 in one PR violates AGENTS.md § 4
  (mass-edit playbook) and triggers full-matrix fanout that the
  catalog cannot afford after the Pattern 19/22 budget incidents.
- **No "one PR per issue" ten-way split.** Threadlight's flip
  cadence wants intermediate v0.5.x releases, not 10 sequential
  v0.5.{1..10}. Grouping by skill boundary preserves the
  "ship → flip → ship → flip" rhythm without churning threadlight
  10 times.
- **No NEW-skill umbrella.** Four `azure-*` and `foundry-rbac-*`
  NEW skills could in principle live under one `azure-platform-readiness`
  umbrella, but the threadlight `sibling-skills-map.md` names each
  by its specific skill identifier. Umbrella would force a
  threadlight-side rename of every `sibling_skill:` entry. Not
  worth it.

## 3 · Shared contracts (apply across all slices)

### 3.1 · Auth model

**Default:** `azure.identity.DefaultAzureCredential`.

Matches threadlight's posture (keyless-by-mandate per the
threadlight design rules) and the existing `foundry-iq/scripts/`
package convention. The chain resolves to whatever the calling
context provides (UAMI in CI, AzureCliCredential in dev,
managed identity in customer pilot).

**Override:** A helper MAY fall back to `az` CLI shell-out when the
relevant Azure surface has no stable SDK (e.g., the
`Microsoft.Insights/activityLogAlerts` REST surface is exposed via
azure-mgmt-monitor but `az monitor activity-log alert list` is the
more battle-tested path). Each fallback MUST be called out in the
helper's docstring with the SDK alternative noted.

### 3.2 · Python module + CLI shim contract (NEW skills)

Every NEW skill ships **both**:

1. **Importable module** at `skills/<name>/scripts/<module>.py`,
   exposing a single `probe(...)` function (sync) and an `aprobe(...)`
   async variant. Returns a typed dict (see § 4 per slice).
2. **CLI shim** at `skills/<name>/scripts/__main__.py` so
   `python -m <skill-name>.scripts <args> --json` emits a single
   JSON object to stdout (the same dict the function returns).

This matches `foundry-iq`'s `scripts/` package precedent (the only
existing skill that ships importable Python with `__init__.py` +
multiple modules + `.env.sample`).

**Why both forms.** Threadlight has two consumption paths:

- **In-process** — `production_ready.py` imports the module
  directly. Faster, no subprocess, no JSON marshalling. Used when
  threadlight is invoked in an environment that already pip-installed
  the skill's deps.
- **Skill-tool-dispatched** — threadlight's apply-plan emits
  `kind: sibling-skill`, the agent reads the skill's `SKILL.md`,
  follows the documented contract, runs the CLI, parses the JSON
  from stdout. Used when threadlight is operator-driven in a
  Copilot CLI session.

Both consumption modes hit the **same Python implementation**.
Single source of truth.

### 3.3 · Output schema (NEW-skill JSON contract)

Every NEW skill's CLI emits exactly one JSON object to stdout:

```json
{
  "skill": "<skill-name>",
  "skill_version": "<semver from SKILL.md metadata.version>",
  "probed_at": "<ISO 8601 UTC>",
  "inputs": { "subscription_id": "...", "resource_group": "...", ... },
  "result": { /* skill-specific shape — see § 4 per slice */ },
  "confidence": "high|medium|low",
  "missing_perms": ["..."],
  "errors": []
}
```

Threadlight's `production_ready.py` consumer reads `result` for the
finding-specific verdict, `confidence` for whether to surface as
`pass`/`fail` vs `not-verified`, and `missing_perms` for the
remediation recipe.

**Errors never raise.** The helper catches every exception and
records it in `errors[]` with the exception class + message. If
`errors` is non-empty AND `result` is `None`, the consumer treats
the call as `not-verified` (data unavailable, not necessarily
failing).

### 3.4 · Extension contract (existing skills)

Slices 1 + 2 do NOT add CLIs — they extend existing skills with
importable modules only. The threadlight side imports them as:

```python
from foundry_observability.kql_probes import trace_freshness
from foundry_evals.last_run import last_run_summary
from foundry_agt.capability_detector import detect
from citadel_spoke.access_contract_probe import probe_hub_contract
```

**Import path.** Each module's top-level package matches the host
skill's underscored name (`foundry-observability` →
`foundry_observability`). Module path = `skills/<name>/scripts/<module>.py`
relative to repo root.

**Catalog convention** (discovered from `foundry-iq` survey, the
only existing skill that ships an importable Python package): every
extended / NEW skill ships:

- `skills/<name>/scripts/__init__.py` (makes `scripts/` a package;
  may be empty or export the public API surface)
- `skills/<name>/scripts/<module>.py` (the actual module)
- `skills/<name>/requirements.txt` (sibling-of-scripts, pinned
  upstream deps)

**No `pyproject.toml`.** No existing skill ships one as an
installable manifest; the only `pyproject.toml` in the catalog
(`skills/ghcp-hosted-agents/references/pyproject.toml`) is a
copy-paste reference, not an installable. Consumers (threadlight,
in-process tests) import via:

```python
import sys
sys.path.insert(0, "skills/foundry-observability/scripts")
from kql_probes import trace_freshness
```

OR by running in a venv where `pip install -r skills/<name>/requirements.txt`
+ `PYTHONPATH=skills/<name>/scripts` is the activation contract. The
threadlight-side import shim already does this; consumers extend the
same pattern.

### 3.5 · Test strategy

Per AGENTS.md § 2.7 + § 9.8 testing tiers:

| Slice | T0 (lint) | T1 (pin) | T2 (import) | T3 (live Azure) |
|---|---|---|---|---|
| 1 — extensions sweep | ✅ enforced by CI | ✅ each extended skill's pin re-runs | ✅ added to validation.script | **Extend** existing fixtures with one `import …` assertion |
| 2 — citadel hub probe | ✅ | ✅ | ✅ | **Skipped.** Skill is currently fixture-less (matches `citadel-hub-deploy` / `foundry-vnet-deploy` posture). Unit tests only. Document in PR description per § 2.9 manual evidence rule. |
| 3 — foundry-rbac-audit | ✅ | ✅ | ✅ | **New fixture** at `skills/foundry-rbac-audit/test-fixture/consumer_prompt.md`, registered in skill-deps.yml |
| 4 — azure-monitor-alert-baseline | ✅ | ✅ | ✅ | **New fixture** (same shape) |
| 5 — backup-readiness + diagnostics | ✅ | ✅ | ✅ | **Two new fixtures** (one per skill) |

### 3.6 · Fixture bloat budget (#243)

NEW-skill fixtures (Slices 3, 4, 5) MUST stay **≤ 8 KB** (≈ 170
lines). Per AGENTS.md Pattern 19 addendum v2, fixtures exceeding
150K tokens per turn cause CAPI 429 cascades; the catalog reference
budget for a probe-shaped fixture is `foundry-memory` (172 lines /
8.2 KB / chars).

Fixture shape:

- **Step 0:** Auth context (show, don't assert) — copy verbatim from
  `foundry-memory/test-fixture/consumer_prompt.md` lines 14–29.
- **Step 1:** Single-sentence goal — "probe X via the skill, write
  the result, exit."
- **Step 2:** Marker contract — same Pattern 12 file-write to
  `/tmp/<skill>-smoke-result`.
- **No deploy.** Probe skills do not provision Azure infra; they
  query what's already in `<ci-resource-group>`. Soft-PASS (Pattern
  13) when the probe-target resource genuinely doesn't exist in CI.

### 3.7 · Description budget tightness

Extension targets are at or near the 1024-char description limit:

| Skill | Current | Headroom |
|---|---|---|
| foundry-observability | 1020 | 4 chars |
| foundry-hosted-agents | 1013 | 11 chars |
| foundry-agt | 986 | 38 chars |
| foundry-evals | 945 | 79 chars |
| foundry-iq | 785 | 239 chars |
| citadel-spoke-onboarding | 698 | 326 chars |

**Implication:** Any new USE FOR / DO NOT USE FOR triggers added by
an extension MUST be balanced by trimming. Slice 1 plans explicitly
budget trim+add deltas to keep every touched description ≤ 1024.

### 3.8 · Plugin / marketplace bumps

| Slice | plugin.json + marketplace.json |
|---|---|
| 1 (extensions only) | PATCH bump (e.g., 4.18.0 → 4.18.1) |
| 2 (extension only) | PATCH bump |
| 3 (1 NEW skill) | MINOR bump (4.18.x → 4.19.0); skill count 31 → 32 |
| 4 (1 NEW skill) | MINOR bump (4.19.0 → 4.20.0); skill count → 33 |
| 5 (2 NEW skills) | MINOR bump (4.20.0 → 4.21.0); skill count → 35 (two skills, one bump per AGENTS.md § 5.1) |

Each PR updates AGENTS.md § 12.5 skill counts. **Note:** AGENTS.md
§ 12.5 currently shows `Total skills | 27` but the live filesystem
has 31 `skills/<name>/SKILL.md` files. Slice 3 (first PR to touch
the counts table) MUST reconcile this — bump from the live count
(31), not the stale table value, and add a one-line note in the
commit body. Plugin + marketplace versions MUST match;
CI enforces.

### 3.9 · Commit tag policy

| Slice | Required tag(s) |
|---|---|
| 1 | `[multi-skill]` (touches 3 skills) + `[skill-rewrite]` (new SKILL.md §) |
| 2 | `[skill-rewrite]` |
| 3 | none required (new skill, no mass-edit gate) |
| 4 | none required |
| 5 | `[multi-skill]` (touches 2 NEW skills) |

Tags enforced by `.github/workflows/automation-pr-gate.yml`.

## 4 · Per-slice contracts

### 4.1 · Slice 1 — Hidden-multiplier extensions sweep

Closes #245, #247, #248.

#### 4.1.1 · `foundry_observability.kql_probes` (#245)

**File:** `skills/foundry-observability/scripts/kql_probes.py`.

**Public API:**

```python
from foundry_observability.kql_probes import (
    trace_freshness, exception_rate,
    rai_denials, agt_denials, rate_limit_events,
)

# Sync:
result = trace_freshness(app_insights_id="<resource-id>", hours=24)
# Async (same args):
result = await async_trace_freshness(...)
```

**Each helper returns:**

```python
{
    "metric": "trace_freshness",
    "result": { ... },           # helper-specific shape; see below
    "confidence": "high|medium|low",
    "last_probe_at": "ISO 8601",
    "stale": bool,               # only for freshness helpers
    "error": str | None,         # never raises
}
```

**Per-helper `result` shapes:**

- `trace_freshness`: `{"freshest_at": ISO, "cloud_RoleName": str, "stale": bool}`
- `exception_rate`: `{"count_per_hour": float, "window_hours": int, "breakdown_by_role": {...}}`
- `rai_denials`: `{"count": int, "window_hours": int, "by_category": {...}}`
- `agt_denials`: `{"count": int, "by_policy_id": {policy_id: int}, "by_deny_path": {deny_path: int}}`
- `rate_limit_events`: `{"count": int, "by_model": {model: int}}`

**Implementation source:** Threadlight's
`scripts/production_ready.py` `_kql_*` helpers (~150 LOC, marked
`# TODO: extract to foundry-observability`). Lift verbatim as v1.

**SKILL.md § to add:** "Reusable KQL probe helpers" — documents the
5-helper API, includes the `from … import …` form, names the
minimum RBAC (`Log Analytics Reader` on the LA workspace), and
points to `references/queries/*.kql` files for the raw query text.

**Version bump:** foundry-observability 1.1.5 → 1.1.6 (PATCH —
new helper, no breaking change).

**Description trim:** No new USE FOR triggers needed (consumers
discover via the new § anchor); 4-char headroom intact.

#### 4.1.2 · `foundry_evals.last_run` (#247)

**File:** `skills/foundry-evals/scripts/last_run.py`.

**Public API:**

```python
from foundry_evals.last_run import last_run_summary

summary = last_run_summary(
    evals_dir="evals/",
    spec_section_9=None,        # optional SPEC § 9 dict for threshold comparison
    freshness_hours=168,        # 7 days default
)
# → dict with the shape documented in issue #247, OR None if no eval ever ran.
```

**Read order:**

1. Local files under `evals_dir/` (latest by mtime; handles
   `azure-ai-evals` JSON shape AND `foundry-evals` native shape).
2. **Fallback:** App Insights `customEvents | where name == "EvalRunCompleted"`
   (skip if `APPLICATIONINSIGHTS_CONNECTION_STRING` not set).

**Never raises.** Returns `None` if no eval ever ran; returns dict
with `error: <msg>` if local files exist but are malformed.

**Implementation source:** Threadlight's `_foundry_evals_last_run()`
(~60 LOC). Lift verbatim.

**SKILL.md § to add:** "Last-run introspection API" — points to
`scripts/last_run.py`, documents the dict shape, names the
conventional `evals/` folder layout.

**Version bump:** foundry-evals 1.2.0 → 1.2.1 (PATCH).

#### 4.1.3 · `foundry_agt.capability_detector` (#248)

**File:** `skills/foundry-agt/scripts/capability_detector.py`.

**Public API:**

```python
from foundry_agt.capability_detector import detect

caps = detect(repo_root=".")
# → dict per issue #248 (version_detected, intervention_points_present,
#   policy_yaml_path, deny_path_present, audit_fields_in_verifier_json,
#   ci_action_pinned, evidence_globs_scanned)
```

**Behavior:** Scans `repo_root` for AGT signals using the same
regex set threadlight currently maintains
(`AGT_DIST_REGEX`, `V4_POLICY_REGEX`, `V4_DYNAMIC_REGEX` from
`production_ready.py`). Returns the capability dict; never raises.

**Unit tests against 4 fixtures:**

- `tests/fixtures/v3_7_only/` — pyproject pinned to AGT 3.7
- `tests/fixtures/v4_1_only/` — pyproject pinned to AGT 4.1 + intervention points
- `tests/fixtures/mixed/` — both present (migration in progress)
- `tests/fixtures/none/` — no AGT signals at all

**SKILL.md § to add:** "Canonical capability detector" — replaces
the prose "how to detect AGT presence" block with a one-line
import + dict shape.

**Version bump:** foundry-agt 1.2.0 → 1.2.1 (PATCH).

#### 4.1.4 · Fixture extensions for Slice 1

Each touched skill's fixture gets ONE new step at the end:

```markdown
### Step N+1 — Validate scripts/ module import (Slice 1 contract)

Verify the extension shipped:

  python -c "from foundry_observability.kql_probes import trace_freshness; print('import-ok')"

Expected stdout: `import-ok`. If the import fails, write
SMOKE_RESULT=FAIL with reason `kql_probes import failed: <error>`.
```

**Token cost per fixture:** ~150 bytes. No bloat-budget risk.

#### 4.1.5 · `requirements.txt` additions

Each of the 3 touched skills gets a sibling `requirements.txt`
naming only what the new `scripts/` module imports. Pinned with
`~=X.Y.Z` per AGENTS.md § 9.5 cap policy.

Example for `foundry-observability/requirements.txt`:

```
azure-monitor-query~=1.4.0
azure-identity~=1.19.0
```

`foundry-evals` and `foundry-agt` get matching minimal lists. No
`pyproject.toml` (matches catalog convention — see § 3.4).

### 4.2 · Slice 2 — Citadel hub probe (#246)

**File:** `skills/citadel-spoke-onboarding/scripts/access_contract_probe.py`.

**Public API:**

```python
from citadel_spoke.access_contract_probe import probe_hub_contract

result = probe_hub_contract(
    hub_rg="<hub-rg-name>",
    apim_name="<apim-name>",           # optional — auto-discovers if RG has one
    spoke_id="<spoke-id-or-foundry-account>",
    subscription="<hub-subscription>", # optional — defaults to current az ctx
)
# → dict per issue #246 (api_present, product_assigned,
#   foundry_connection_status, subscription_key_present, rate_limit_policy,
#   last_probe_at, confidence, missing_perms)
```

**Behavior:**
- Calls `az apim api list`, `az apim product list`,
  `az apim api operation list` (or SDK equivalents).
- Auto-discovers APIM when `hub_rg` has exactly one; explicit
  `apim_name` required otherwise.
- Never raises. Missing `API Management Service Reader` →
  `confidence: low` + `missing_perms: ["API Management Service Reader"]`.

**Env var compat:** Reads `TL_CITADEL_HUB_RG` as default for
`hub_rg` parameter if caller passes `None`, so the threadlight
operator UX (stub message tells operators to set `TL_CITADEL_HUB_RG`)
continues to work post-extraction.

**Implementation source:** Threadlight's v0.3.0 inline
`_citadel_access_contract_probe()` (~80 LOC). Lift verbatim.

**SKILL.md § to add:** "Hub-side Access Contract probe" — documents
the API + minimum RBAC (`API Management Service Reader` on hub
APIM) + the `TL_CITADEL_HUB_RG` compat.

**Version bump:** citadel-spoke-onboarding 1.1.1 → 1.2.0 (MINOR —
new documented capability per § 5 SemVer rules).

**No fixture.** Matches current posture of this skill (it has no
fixture today). Unit tests against 4 mocked APIM JSON shapes
(happy path, API missing, product missing, all perms missing).

**Citadel coordination zone (#244).** This PR adds files only
(`scripts/access_contract_probe.py` + `pyproject.toml` + a new §
in SKILL.md + a new entry in `references/upstream-pin.md` known
issues). It does NOT touch the upstream-pin SHA or any of the
sections #244 plans to rewrite. Stack ordering: this PR can land
in either order with #244 if both are open simultaneously, and
neither will rebase-conflict the other.

### 4.3 · Slice 3 — `foundry-rbac-audit` NEW (#268)

**Skill dir:** `skills/foundry-rbac-audit/`.

**Files:**
- `SKILL.md` (frontmatter + body, target ≤ 700 lines, description
  ≤ 800 chars)
- `scripts/__init__.py`
- `scripts/audit.py` — `probe(subscription_id, resource_group, target_principal_types) → dict`
- `scripts/__main__.py` — CLI shim
- `pyproject.toml`
- `references/upstream-pin.md` — pin file (likely
  `freshness_tier: B`, packages `azure-mgmt-authorization` + `azure-identity`)
- `test-fixture/consumer_prompt.md` (≤ 8 KB)
- `requirements.txt` (matches pyproject deps)  ← single source for deps; no pyproject.toml per § 3.4

**Public API:**

```python
from foundry_rbac_audit import audit

result = audit(
    subscription_id="<sub>",
    resource_group="<rg>",
    target_principal_types=("User", "ServicePrincipal", "Group", "ManagedIdentity"),
)
# → dict (see § 3.3 NEW-skill JSON shape) with result containing:
#   {
#     "foundry_account_assignments": [...],
#     "foundry_project_assignments": [...],
#     "wildcard_assignments": [...],   # Contributor/Owner on Foundry resources
#     "account_level_cog_users": [...], # should be narrowed to project-level
#     "remediation_commands": ["az role assignment create ..."],
#   }
```

**CLI shim:**

```bash
python -m foundry_rbac_audit \
  --subscription-id <sub> \
  --resource-group <rg> \
  --target-principal-types User,ServicePrincipal \
  --json
```

**SKILL.md description shape:**

```
Audit project-level RBAC on Foundry account + Cognitive Services
workspace. Diffs declared RBAC (SPEC § 12 or supplied dict) against
live `az role assignment list` output at account + project scopes.
Flags wildcard / broad assignments (Contributor, Owner) and account-
level `Cognitive Services User` assignments that should be narrowed
to `Azure AI Project*` project-level roles.
USE FOR: foundry rbac, project rbac, role assignment audit, ai
project role, cognitive services user narrow, foundry iam, declared
rbac diff, wildcard role flag, threadlight MDL-009.
DO NOT USE FOR: Entra patterns (out of scope), VNet IAM (use
azure-tenant-isolation), broader Azure RBAC (use az-platform tools).
```

**Fixture goal:** "Use the `foundry-rbac-audit` skill to probe the
CI Foundry account `aif-awesome-gbb-ci` and confirm the JSON output
shape matches the schema § 3.3 above. Soft-PASS if no assignments
are returned (genuine zero, not failure)."

**pin file:** `freshness_tier: B`,
`automation_tier: auto`, `validation.runnable: true`,
`validation.requires: [github_only, pypi]`,
`validation.script` does `pip install` + `python -c "from foundry_rbac_audit import audit; print('import-ok')"`.

### 4.4 · Slice 4 — `azure-monitor-alert-baseline` NEW (#272)

**Skill dir:** `skills/azure-monitor-alert-baseline/`.

**Files:** Same shape as Slice 3.

**Public API:**

```python
from azure_monitor_alert_baseline import probe

result = probe(
    subscription_id="<sub>",
    resource_group="<rg>",
    alert_baseline_kind="threadlight-pilot",  # or "minimal", "regulated"
)
# → dict (§ 3.3 shape) with result containing:
#   {
#     "configured_alerts": [...],
#     "baseline_alerts_for_kind": [...],
#     "missing_alerts": [...],
#     "extra_alerts": [...],
#     "bicep_remediation": "module ...{}",  # Bicep snippet for missing
#   }
```

**Baseline catalog:** Ships 3 baselines:
- `minimal` — Service Health + Resource Health on RG
- `threadlight-pilot` — minimal + Policy state-change + IAM role
  assignment changes
- `regulated` — threadlight-pilot + every Microsoft.* resource
  CRUD activity-log

**CLI shim, fixture, pin file:** Same shape as Slice 3.

**Cross-ref to azure-sre-agent #250:** SKILL.md DO NOT USE FOR
clause: "alert response automation (use azure-sre-agent
threadlight-production-handover recipe — these alerts feed it)."

### 4.5 · Slice 5 — `azure-backup-readiness` + `azure-resource-diagnostics` NEW (#267, #271)

Both skills follow the same shape as Slices 3 + 4. One PR,
`[multi-skill]` tag, one plugin.json MINOR bump.

#### 4.5.1 · `azure-backup-readiness` (#267)

**Public API:**

```python
from azure_backup_readiness import probe

result = probe(
    subscription_id="<sub>",
    resource_group="<rg>",
    protected_item_types=("VM", "AzureFiles", "Blob", "PostgreSQL"),
    drill_freshness_days=90,
)
# → dict (§ 3.3 shape) with result:
#   {
#     "rsv_vaults": [{name, last_restore_point, items: [...]}],
#     "backup_vaults": [{name, last_restore_point, items: [...]}],
#     "restore_drill_artefacts": [{path, dated, fresh: bool}],
#     "missing_drill": bool,
#   }
```

**Probes:** `az backup recoverypoint list` (RSV) +
`az dataprotection backup-instance list-recovery-points`
(Backup Vault) + filesystem scan for `tests/restore-drill-*.md` or
`docs/restore-drill.md`.

#### 4.5.2 · `azure-resource-diagnostics` (#271)

**Public API:**

```python
from azure_resource_diagnostics import probe

result = probe(
    subscription_id="<sub>",
    resource_group="<rg>",
    target_resource_types=("Microsoft.CognitiveServices/accounts",
                            "Microsoft.KeyVault/vaults"),
)
# → dict (§ 3.3 shape) with result:
#   {
#     "resources_with_diag_settings": [...],
#     "resources_missing_diag_settings": [...],
#     "diag_settings_not_la_destination": [...],
#     "bicep_remediation_per_resource": {resource_id: "..."},
#   }
```

**Probes:** `az monitor diagnostic-settings list --resource <id>`
per resource enumerated in the RG. Emits Bicep snippet template per
resource missing.

#### 4.5.3 · Shared

Both skills register in `.github/skill-deps.yml` as
`depends_on: []` (no catalog-internal deps). Both fixtures use the
same Step 0 / Step 1 / Step 2 marker pattern. Plugin.json bumps
once for both NEW skills.

### 4.6 · Deferred — `foundry-iq` PE-posture + `foundry-hosted-agents` retention

Both are MINOR extensions to existing skills with their own pyproject
posture already shipped (`foundry-iq/requirements.txt`, hosted-agents'
`references/python/pyproject.toml`).

#### 4.6.1 · `foundry-iq` PE-posture (#269)

**File:** `skills/foundry-iq/scripts/pe_posture_audit.py`.

**Public API:** `audit_ki_pe_posture(project_endpoint, subscription, resource_group) → dict`.

**Inspects** each KI's backing AI Search resource:
`publicNetworkAccess` + `privateEndpointConnections`. Flags any
KI with a publicly-reachable backing search as `must-fix` for
`target_posture: citadel-spoke|agt`.

**Version bump:** foundry-iq 1.3.2 → 1.4.0 (MINOR — new documented
capability).

#### 4.6.2 · `foundry-hosted-agents` thread retention (#270)

**Decision:** Home is **`foundry-hosted-agents`** (NOT foundry-memory),
because thread API ownership lives in the hosted-agent client.

**File:** `skills/foundry-hosted-agents/scripts/thread_retention.py`.

**Public API:** `audit_thread_retention(project_endpoint, agent_name, declared_retention_days) → dict`.

**Enumerates** live thread counts per agent, diffs oldest-thread
age against declared retention, returns deletion-recipe stub.

**Version bump:** foundry-hosted-agents 1.11.0 → 1.12.0 (MINOR).
**Cross-ref note in foundry-memory SKILL.md:** "Thread retention
hygiene → see foundry-hosted-agents scripts/thread_retention.py."

## 5 · Open questions (for human ratification)

These were resolvable from the issue bodies + threadlight tracker
to a **default** with rationale, but the human may override:

1. **Slice 1 multi-skill PR vs 3 separate PRs.** Default: multi-skill
   (one threadlight flip round, one matrix run with `[multi-skill]`
   tag). Override would be 3 separate PRs for cleaner reviews at
   the cost of 3 matrix runs + 3 flip rounds. **Recommendation:
   multi-skill.**

2. **Slice 5 multi-skill NEW PR vs 2 separate NEW PRs.** Default:
   multi-skill (one MINOR plugin bump, one matrix fanout with 2 new
   legs). Override would be 2 sequential PRs each with their own
   MINOR bump. **Recommendation: multi-skill given identical shape +
   shared "Order-7 lowest urgency" classification.**

3. **#270 home pick.** Default: `foundry-hosted-agents` (thread API
   owner). Alternative: `foundry-memory` (memory hygiene grouping).
   **Recommendation: hosted-agents** — but flag to confirm because
   the issue body lists both.

4. **Citadel timing (#246 vs #244).** Default: ship Slice 2 in
   parallel with #244 if both are open. Add files only, no overlap
   with #244's planned SHA refresh. Alternative: explicitly serial
   after #244 lands. **Recommendation: parallel** (the file scope
   is orthogonal) — but flag for confirmation since #244 author may
   prefer freezing the skill.

5. **NEW-skill output contract — "module + CLI + JSON" vs simpler
   alternatives.** Default: ship both (matches `foundry-iq`
   precedent; gives threadlight both consumption paths). Alternatives:
   (a) module-only (threadlight always imports), (b) prose-only
   SKILL.md (agent constructs ad-hoc calls per skill guidance).
   **Recommendation: both** — but flag because it's the contract
   surface area the most consumers will touch.

6. **Should #244 (Citadel revamp) gate Slice 2?** The tracker says
   "schedule after wave settles" for citadel work. The wave is M2-M5
   (`foundry-doc-vision-speech`, `foundry-skill-catalog`,
   `foundry-toolbox`, `foundry-hosted-agents` — recent commit
   `fc09cf7` shows M5 already landed). MAF cascade may be far enough
   along to dispatch citadel work. **Recommendation: confirm with
   #244 author whether they consider the wave settled enough.**

## 6 · Non-goals

Per the cross-session prompt's "stop conditions" + constraints:

- **No threadlight-skills repo changes.** Every flip
  (`kind: manual → kind: sibling-skill`) is owned by the threadlight
  side per `sibling-skill-flip-protocol.md`. This plan only ships
  the upstream surface area.
- **No #244 Citadel revamp work.** Tracked separately; Slice 2 is
  intentionally narrow to avoid conflict.
- **No #261 MAF cascade overlap.** Slice 1 touches foundry-evals,
  foundry-observability, foundry-agt — none of which are in the M2-M5
  refresh list. Slice deferred touches foundry-hosted-agents (M5
  target) but is intentionally post-M5.
- **No mass-edit of existing SKILL.md prose.** Extensions ADD new §
  only; no rewriting of existing sections.
- **No matrix-builder / CI workflow changes.** Each NEW skill
  registers in `.github/skill-deps.yml` per the existing add-skill
  protocol; CI fans out automatically.

## 7 · Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| #244 Citadel author rejects parallel Slice-2 dispatch | Medium | Open question #6 — confirm before Slice 2 fires |
| Description budget breach on Slice 1 extension targets | Low | Plan enforces no new USE FOR triggers (consumers discover via new §) |
| NEW-skill fixture trips Pattern 19 CAPI 429 | Medium | Fixture bloat budget ≤ 8 KB per § 3.6 |
| Citadel hub probe fails in CI (no APIM in `<ci-resource-group>`) | Low | Slice 2 ships no fixture — unit tests with mocks only |
| #270 home pick conflict if user prefers foundry-memory | Low | Deferred slice; not blocking v0.6.0 |
| Threadlight-side flip cadence can't keep up with 5 PRs | Low | Slice 1 multi-skill compresses 3 flips into one round |

## 8 · References

- Tracker: [aiappsgbb/threadlight-skills#35](https://github.com/aiappsgbb/threadlight-skills/issues/35)
- Sibling-skills-map: `skills/threadlight-production-ready/references/sibling-skills-map.md` (in threadlight-skills repo)
- Flip protocol: `skills/threadlight-production-ready/references/runbooks/sibling-skill-flip-protocol.md` (in threadlight-skills repo)
- Per-issue contracts: #245, #246, #247, #248, #267, #268, #269, #270, #271, #272 in `aiappsgbb/awesome-gbb`
- AGENTS.md § 2.4 (frontmatter), § 2.7–2.9 (test tiers), § 4 (mass-edit), § 5 (SemVer), § 9.8 (testing tiers), § 9.7 Pattern 19/22/13 (fixture conventions), § 10.3 (adding a new skill), § 12.5 (catalog metrics)
