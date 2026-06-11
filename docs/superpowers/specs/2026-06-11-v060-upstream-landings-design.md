# v0.6.0 Upstream Landings — Design Spec

**Date:** 2026-06-11
**Status:** Approved (design phase). Implementation plans pending via writing-plans.
**Branch:** `unsafecode/v060-upstream-planning`
**Tracker (downstream):** [`aiappsgbb/threadlight-skills#35`](https://github.com/aiappsgbb/threadlight-skills/issues/35) — v0.6.0 critical path
**Catalog issues in scope (10):** #248, #268, #246, #245, #272, #247, #267, #271, #269, #270

---

## 1 · Problem

`threadlight-production-ready` v0.5.0 shipped a 21-finding pre-pilot
audit framework but most rule kinds are still wired with `kind: manual`
(human-in-the-loop). The downstream tracker
[`threadlight-skills#35`](https://github.com/aiappsgbb/threadlight-skills/issues/35)
flips them to `kind: sibling-skill` finding-by-finding as the upstream
helper code lands in this catalog. v0.6.0 ("credible customer-pilot
ready") is gated on 8 of those flips, which in turn are gated on 10
issues in `aiappsgbb/awesome-gbb`:

| Threadlight finding | Awesome-gbb issue | Skill | Slice |
|---|---|---|---|
| AGT-V4-001..007 (cross-cutting) | #248 (extension) | foundry-agt | A |
| KQL probes (cross-cutting) | #245 (extension) | foundry-observability | A |
| EVAL-201 (last-run summary) | #247 (extension) | foundry-evals | A |
| NET-501/502 | #246 (extension) | citadel-spoke-onboarding | B |
| IAM-101 | #268 (NEW skill) | foundry-rbac-audit | C |
| SRE-104 | #272 (NEW skill) | azure-monitor-alert-baseline | C |
| REL-007 | #267 (NEW skill) | azure-backup-readiness | D |
| OBS-106 | #271 (NEW skill) | azure-resource-diagnostics | D |
| MDL-010 (deferrable) | #269 (extension) | foundry-iq | E (v0.7.0) |
| MDL-011 (deferrable) | #270 (extension) | foundry-hosted-agents | E (v0.7.0) |

Threadlight has already authored inline reference implementations for
the 4 EXTENSION issues marked `# TODO: extract to <skill> when issue
#NNN ships` — the catalog's job is to lift those into proper SKILL.md
helpers with public APIs that match the contracts in threadlight's
[sibling-skills-map.md](https://github.com/aiappsgbb/threadlight-skills/blob/main/skills/threadlight-production-ready/references/sibling-skills-map.md).
For the 4 NEW skills, the contracts are likewise locked by threadlight
— we build to spec, no contract negotiation.

The macro problem is **release shape**: 10 issues × per-issue PR would
be ~3 weeks of CI noise and merge churn; 1 mega-PR would block all
intermediate threadlight flips and have an unreviewable diff. We need
a 4-slice cut that lets threadlight ship intermediate v0.5.x flip
releases as each slice lands.

---

## 2 · Goals + Non-Goals

**Goals**
- Land all 8 v0.6.0-critical issues (#248, #245, #247, #246, #268, #272, #267, #271) in 4 reviewable PR slices.
- Each slice MUST be self-contained: no slice's tests depend on another slice's code.
- Each slice MUST unblock a clearly-named threadlight v0.5.x flip release.
- Defer #269 and #270 to v0.7.0 with a documented rationale (slice E).
- All 4 NEW skills MUST follow AGENTS.md §10.3 add-a-skill workflow end-to-end (SKILL.md → pin file → E2E test → cross-refs → `CATEGORIES` → adversarial review → live Azure validation → docs rebuild → plugin bumps).
- All 4 EXTENSIONS MUST follow AGENTS.md §7 SSOT rule (Python helpers in `references/python/`, not duplicated inline in SKILL.md).
- Match this repo's existing conventions verbatim — no new file layouts, no new CI gate shapes, no new credential patterns.

**Non-Goals**
- Not touching `aiappsgbb/threadlight-skills` — flips happen in a separate session per threadlight's flip-protocol runbook.
- Not landing #244 (Citadel revamp). #244 is currently parked on the MAF/GHCP wave (#261); Slice B lands independently and #244 rebases on top later.
- Not changing the threadlight contract (input keys, output shape, finding IDs). The contracts in sibling-skills-map.md are the spec; we build to them.
- Not collapsing the 4 NEW skills into one umbrella. They are 4 peer skills per the threadlight dispatch contract.
- Not adding new credential libraries. `DefaultAzureCredential` is the canonical for all 4 NEW skills.
- Not refactoring host-skill SKILL.md prose during EXTENSIONs (Slice A, B). Surgical adds only.

---

## 3 · Slicing — the locked cut

```
┌─────────────────────────────────────────────────────────────────────┐
│  SLICE A  ──  Hidden-multiplier helpers (3 extensions)              │
│  Skills: foundry-agt, foundry-observability, foundry-evals          │
│  Issues: #248, #245, #247                                           │
│  Shape: 1 multi-skill PR  (commit tag: [multi-skill])               │
│  Threadlight unlock: v0.5.1 — 7+ recipes flip to sibling-skill      │
│  Why first: highest ROI per round (per tracker planner-notes);      │
│  zero coordination cost; all extensions; no new skill scaffolding.  │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│  SLICE B  ──  Citadel spoke hub-probe (1 extension)                 │
│  Skill:  citadel-spoke-onboarding                                   │
│  Issues: #246                                                        │
│  Shape: 1 single-skill PR  (commit tag: [skill-rewrite])            │
│  Threadlight unlock: v0.5.2 — NET-501/502 self-verify               │
│  Why second: independent of A; coordination risk with #244 (parked) │
│  resolved by landing first; #244 rebases on top.                    │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│  SLICE C  ──  RBAC + alert baseline (2 NEW skills)                  │
│  Skills: foundry-rbac-audit, azure-monitor-alert-baseline           │
│  Issues: #268, #272                                                  │
│  Shape: 1 multi-skill PR  (commit tags: [multi-skill] + [skill-rewrite]) │
│  Threadlight unlock: v0.5.3 — IAM-101 + SRE-104                     │
│  Why third: 2 NEW skills share the probe-an-RG-emit-JSON template;  │
│  share scaffolding cost, share E2E test infra, share docs rebuild.  │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────┐
│  SLICE D  ──  Backup + resource diagnostics (2 NEW skills)          │
│  Skills: azure-backup-readiness, azure-resource-diagnostics         │
│  Issues: #267, #271                                                  │
│  Shape: 1 multi-skill PR  (commit tags: [multi-skill] + [skill-rewrite]) │
│  Threadlight unlock: v0.5.4 — REL-007 + OBS-106 (→ v0.6.0 final)    │
│  Why fourth: same template shape as Slice C; Slice C's harness      │
│  proves the pattern before Slice D scales it.                       │
└─────────────────────────────────────────────────────────────────────┘

           ─── DEFERRED to v0.7.0 ───

┌─────────────────────────────────────────────────────────────────────┐
│  SLICE E  ──  PE-posture audit + thread retention (2 extensions)    │
│  Skills: foundry-iq, foundry-hosted-agents                          │
│  Issues: #269, #270                                                  │
│  Rationale: tracker explicitly marks both as "deferrable"; neither  │
│  unblocks the v0.6.0 cut; threadlight can ship v0.6.0 with these    │
│  findings remaining kind: manual.                                    │
└─────────────────────────────────────────────────────────────────────┘
```

**Locked decisions (user-approved):**
1. 4 + 1 slices, in this order, with these contents.
2. Slice B lands independently of #244 (#244 rebases on top).
3. 4 NEW skills are peer skills, not an umbrella.
4. Canonical auth is `DefaultAzureCredential` for all 4 NEW skills.
5. Output schema is **both** stdout JSON (debug) and manifest file at `out/<finding-id>.json` (deterministic CI grading per Pattern 12).
6. One design spec + 4 implementation plans (one per slice).

---

## 4 · Per-slice specs

### 4.1 · Slice A — Hidden-multiplier helpers

**Issues closed:** #248, #245, #247
**Skills touched:** `skills/foundry-agt/`, `skills/foundry-observability/`, `skills/foundry-evals/`
**PR shape:** one multi-skill PR; commit message MUST include `[multi-skill]` per AGENTS.md §10.3
**Threadlight unlock:** v0.5.1 — 7+ recipes flip from `kind: manual` to `kind: sibling-skill`

#### 4.1.1 · #248 — foundry-agt canonical capability detector

**Public API (locked by issue #248 body):**

```python
from foundry_agt.capability_detector import detect

caps = detect(repo_root=".")
# Returns dict with keys (every key always present):
#   version_detected: str | None         # e.g. "4.0.0" or None if not pinned
#   detection_confidence: float          # 0.0..1.0
#   package_pins: dict[str, str]         # {"foundry-agt": "==4.0.0", ...}
#   intervention_points_present: bool    # any V4_DIST_REGEX hits in code
#   policy_yaml_path: str | None         # discovered AGT policy YAML
#   deny_path_present: bool              # AGT deny-list present
#   audit_fields_in_verifier_json: list[str]  # field names found
#   ci_action_pinned: bool               # GitHub Action SHA pinned
#   evidence_globs_scanned: list[str]    # glob patterns we walked
```

**Source of truth:** lift verbatim from threadlight's
`scripts/production_ready.py` `_detect_agt_profile()` + the AGT-V4-001..007
regexes (`V4_DIST_REGEX`, `V4_POLICY_REGEX`, `V4_DYNAMIC_REGEX`). Place
in `skills/foundry-agt/references/python/capability_detector.py` per
AGENTS.md §7 SSOT rule. SKILL.md gets a new "Using the canonical
capability detector" section that cross-links to the reference file
("MUST copy verbatim from `references/python/capability_detector.py`")
and does **not** duplicate the code body inline.

**Threadlight call site:**
```python
from foundry_agt.capability_detector import detect
caps = detect(repo_root=str(repo_root))
# Map to AGT-V4-001..007 findings via the field names above.
```

**Tests (Slice A unit-test budget):**
- `scripts/tests/test_foundry_agt_capability_detector.py` — pytest unit tests with synthetic repo trees (tmp_path fixtures). NO Azure dependency, NO Copilot-CLI fixture. AGENTS.md §9.8 tier T0 only.
- Cases: empty repo (every flag False, every list []), full v4 repo (every flag True), mixed-version repo (detection_confidence < 1.0), missing policy YAML (`policy_yaml_path is None`), pinned but missing SHA on CI action.

**Pin file:** N/A — this is a pure-Python helper, no external SDK version to track. The host skill's existing pin (if any) is untouched.

**Versioning:** `foundry-agt` SKILL.md MINOR bump (new documented section + new public helper).

#### 4.1.2 · #245 — foundry-observability KQL probe helpers

**Public API (locked by issue #245 body):**

```python
from foundry_observability.kql_probes import (
    trace_freshness, exception_rate, rai_denials,
    agt_denials, rate_limit_events,
)
# Every helper signature:
#   def trace_freshness(workspace_id: str, app_name: str, *, since="1h", credential=None) -> dict
# Returns:
#   {"result": <typed primitive>, "confidence": 0.0..1.0,
#    "last_probe_at": "ISO8601", "error": str | None}
# Never raises. Catches every exception, returns error key with reason.
```

Sync variants live in `kql_probes`; async variants live in
`kql_probes.aio` with identical signatures but `async def`. Both share
the same internal KQL query strings (one source of truth per probe).

**Source of truth:** lift verbatim from threadlight's
`scripts/production_ready.py` `_kql_*` helpers (~150 LOC across 5
probes). Place in `skills/foundry-observability/references/python/kql_probes.py`
and `kql_probes_aio.py` (or one file with both, decided per executor
preference during implementation).

**SKILL.md addition:** new "Reusable KQL probe helpers" section with
a table mapping each helper to its threadlight call site and a
cross-link to the reference file (no inline code body).

**Tests (Slice A unit-test budget):**
- `scripts/tests/test_foundry_observability_kql_probes.py` — pytest with a fake Azure Monitor query client (no real workspace required). Verifies signature, return shape, never-raises contract.
- E2E happy-path: hits the existing `<ci-monitor-workspace>` (or skips if not provisioned in CI yet — depend on AGENTS.md §9.7 fixture inventory at execution time).

**Pin file:** existing `foundry-observability/references/upstream-pin.md` gets `azure-monitor-query` package added to `packages[]` if not already present; version bumped to MINOR.

**Versioning:** `foundry-observability` SKILL.md MINOR bump.

#### 4.1.3 · #247 — foundry-evals last-run introspection

**Public API (locked by issue #247 body):**

```python
from foundry_evals.last_run import last_run_summary

summary = last_run_summary(
    evals_dir: str = "evals/",
    spec_section_9: dict | None = None,
)
# Returns None if no eval has ever run. Otherwise a dict:
#   ran_at: ISO8601
#   run_id: str
#   scenarios_total: int
#   scenarios_passed: int
#   scenarios_failed: int
#   threshold_breaches: list[str]  # human-readable breach descriptions
#   p50_latency_ms: float | None
#   p95_latency_ms: float | None
#   confidence: 0.0..1.0
#   stale: bool                     # last run > 7 days ago
#   source: str                     # path or run-store identifier
```

**Source of truth:** lift verbatim from threadlight's
`scripts/production_ready.py` `_foundry_evals_last_run()` (~60 LOC).
Place in `skills/foundry-evals/references/python/last_run.py`.

**SKILL.md addition:** new "Programmatic last-run introspection"
section cross-linking to the reference file.

**Tests (Slice A unit-test budget):**
- `scripts/tests/test_foundry_evals_last_run.py` — pytest with synthetic
  evals/ directory in tmp_path. Cases: empty dir (returns None), one
  green run (all flags right), one red run (threshold_breaches
  populated), stale run (>7 days old → `stale: True`).

**Pin file:** existing `foundry-evals/references/upstream-pin.md` is
untouched (this is a pure-Python helper).

**Versioning:** `foundry-evals` SKILL.md MINOR bump.

#### 4.1.4 · Slice A cross-cutting

- **Commit tag:** `[multi-skill]` required. Body lists each touched skill + bump category.
- **Plugin version:** `plugin.json` + `marketplace.json` PATCH bump (no new skills added, just MINOR SKILL.md bumps).
- **Fixture bloat (#243):** zero Copilot-CLI fixtures in Slice A. Pure pytest unit tests only. No TPM impact.
- **Identifier scrub (#256/#260):** no new identifiers introduced. Tests use `tmp_path` and fake clients.

---

### 4.2 · Slice B — Citadel spoke hub-probe

**Issues closed:** #246
**Skills touched:** `skills/citadel-spoke-onboarding/`
**PR shape:** one single-skill PR; commit tag `[skill-rewrite]` (new public section + new Python module)
**Threadlight unlock:** v0.5.2 — NET-501/502 self-verify (Foundry⇄Citadel hub access-contract probe)

#### 4.2.1 · Public API (locked by issue #246 body)

```python
from citadel_spoke.access_contract_probe import probe_hub_contract

result = probe_hub_contract(
    hub_rg: str,
    apim_name: str | None = None,        # auto-discover if RG has 1 APIM
    spoke_id: str,
    subscription: str | None = None,     # default: current
)
# Returns:
#   api_present: bool
#   product_assigned: bool
#   foundry_connection_status: "ok" | "missing" | "errored"
#   subscription_key_present: bool
#   rate_limit_policy: dict | None
#   last_probe_at: ISO8601
#   confidence: 0.0..1.0
#   missing_perms: list[str]   # role names the caller lacks, if any
# Never raises. Backwards-compat: also reads env var TL_CITADEL_HUB_RG
# when hub_rg is the empty string.
```

#### 4.2.2 · Source of truth

Lift verbatim from threadlight's `scripts/production_ready.py`
`_citadel_access_contract_probe()` (~80 LOC). Place in
`skills/citadel-spoke-onboarding/references/python/access_contract_probe.py`.

#### 4.2.3 · SKILL.md addition

New "Hub-side Access Contract probe" subsection under existing
"Probing the deployed spoke" section (already exists per inspection).
Cross-link to the reference file; no inline code body. Document the
`TL_CITADEL_HUB_RG` env-var fallback.

#### 4.2.4 · Tests

- `scripts/tests/test_citadel_access_contract_probe.py` — pytest with mocked APIM client. Cases: API present + product assigned + subscription key present (full happy path), APIM not found in RG (`api_present: False` + clear error), permission denied on product read (`missing_perms` populated, confidence < 1.0), env-var fallback works when `hub_rg=""`.
- E2E: skip in this slice. The fixture would need a real Citadel hub deployed in `<ci-resource-group>` and that isn't provisioned per AGENTS.md §9.7. Document as "manual validation against a dev hub" in the PR description per AGENTS.md §2.9.

#### 4.2.5 · #244 coordination

Decision (user-approved): **Slice B lands first, independent of #244.**

Rationale:
- #244 is parked on the MAF/GHCP wave (#261) and won't dispatch soon.
- Slice B is a NEW Python module + a NEW subsection — surgical, additive only. Doesn't touch any section #244 plans to revamp.
- When #244 dispatches later, its SKILL.md rebase will absorb our subsection as a "kept" diff with low conflict risk.
- If a conflict does emerge during #244 review, the #244 author resolves it (their PR is bigger; we don't block their schedule by gating on us).

If Slice B is somehow blocked at PR time by an active #244 in flight,
fall back to coordinating with the #244 author (don't block their PR;
land afterward).

#### 4.2.6 · Slice B cross-cutting

- **Commit tag:** `[skill-rewrite]` required (new SKILL.md section is body content per AGENTS.md §4).
- **Plugin version:** `plugin.json` + `marketplace.json` PATCH bump.
- **Versioning:** `citadel-spoke-onboarding` SKILL.md MINOR bump.
- **Fixture bloat (#243):** no Copilot-CLI fixture in Slice B (no E2E).
- **Identifier scrub:** no new identifiers; mocks use placeholder names.

---

### 4.3 · Slice C — RBAC + alert baseline (2 NEW skills)

**Issues closed:** #268, #272
**Skills added:** `skills/foundry-rbac-audit/`, `skills/azure-monitor-alert-baseline/`
**PR shape:** one multi-skill PR; commit tags `[multi-skill]` + `[skill-rewrite]`
**Threadlight unlock:** v0.5.3 — IAM-101 + SRE-104

#### 4.3.1 · Shared template (both NEW skills follow this shape)

Both skills implement the **probe-an-RG-emit-JSON** template:

```python
# skills/<skill>/references/python/probe.py
from azure.identity import DefaultAzureCredential

def probe(
    subscription_id: str,
    resource_group: str,
    **kwargs,          # skill-specific
) -> dict:
    """Probe Azure resources in <resource_group>; return finding-shaped dict.

    Returns:
        {
            "finding_id": "<IAM-101 | SRE-104 | REL-007 | OBS-106>",
            "scope": {"subscription_id": ..., "resource_group": ...},
            "result": "ok" | "needs_attention" | "errored",
            "observations": [{"resource_id": ..., "issue": ..., ...}, ...],
            "remediation_hints": [...],
            "confidence": 0.0..1.0,
            "probed_at": ISO8601,
            "error": str | None,
        }

    Never raises.
    """
    credential = DefaultAzureCredential()
    # ... per-skill logic
```

Each skill ALSO ships a CLI entry point that:

1. Takes `--subscription-id`, `--resource-group`, plus skill-specific flags.
2. Prints the finding dict as JSON to **stdout** (machine-readable, jq-friendly).
3. **Also writes** the same dict to `out/<finding-id>.json` (matches Pattern 12 marker shape for deterministic CI grading).

```bash
$ python -m foundry_rbac_audit \
    --subscription-id $SUB \
    --resource-group rg-pilot \
    --target-principal-types user,service_principal
{"finding_id": "IAM-101", "result": "needs_attention", ...}

$ cat out/IAM-101.json
{"finding_id": "IAM-101", "result": "needs_attention", ...}
```

**Threadlight reads the manifest file**, not stdout. Stdout is for
human/Copilot-CLI debug only.

#### 4.3.2 · #268 — foundry-rbac-audit

**Contract (locked by threadlight sibling-skills-map.md IAM-101):**

```python
def probe(
    subscription_id: str,
    resource_group: str,
    target_principal_types: list[str],  # ["user", "service_principal", "group", "managed_identity"]
) -> dict
```

**What it does:** lists role assignments in `<resource_group>` whose
principal type matches the filter; flags overly-broad assignments
(Owner / Contributor at RG scope on non-IaC-deployed identities); flags
guest users with privileged roles; flags MIs with cross-RG Owner
inheritance.

**Backing SDKs:**
- `azure-mgmt-authorization` (role assignments + role definitions)
- `azure-mgmt-resource` (resource introspection for inheritance)
- `azure-identity.DefaultAzureCredential`

**Caller RBAC required:** `Reader` on the resource group +
`Microsoft.Authorization/roleAssignments/read` (typically via `Reader`
or `User Access Administrator`). Document explicitly in SKILL.md.

#### 4.3.3 · #272 — azure-monitor-alert-baseline

**Contract (locked by threadlight sibling-skills-map.md SRE-104):**

```python
def probe(
    subscription_id: str,
    resource_group: str,
    alert_baseline_kind: str,    # "foundry_pilot" | "spoke_minimum" | "production"
) -> dict
```

**What it does:** lists Azure Monitor alert rules in `<resource_group>`;
compares against the baseline kind's expected set (e.g. for
`foundry_pilot`: token-rate spike, RAI denial spike, hosted-agent
error rate, KI freshness lag); reports missing alerts + alerts
configured at unsafe thresholds.

**Backing SDKs:**
- `azure-mgmt-monitor` (alert rules + metric alerts)
- `azure-mgmt-resource`
- `azure-identity.DefaultAzureCredential`

**Caller RBAC required:** `Monitoring Reader` on the resource group.

**Baseline definitions:** ship under `references/baselines/<kind>.yaml`
(e.g. `foundry_pilot.yaml` lists the 4-5 required alert kinds + safe
threshold ranges). Threadlight calls with `alert_baseline_kind="foundry_pilot"`
during the pre-pilot audit.

#### 4.3.4 · Per-skill file layout (both skills follow this)

```
skills/<skill>/
├── SKILL.md                      # frontmatter (≤1024 char desc) + body
├── README.md                     # optional extended docs
├── references/
│   ├── upstream-pin.md           # schema v2; tier: B (SDK wrapper); auto if pin runnable
│   ├── python/
│   │   ├── probe.py              # the public probe() function
│   │   └── __main__.py           # the CLI entry (python -m <skill>)
│   └── baselines/                # azure-monitor-alert-baseline only
│       ├── foundry_pilot.yaml
│       ├── spoke_minimum.yaml
│       └── production.yaml
└── test-fixture/
    └── consumer_prompt.md        # Copilot-CLI fixture (see §6.4 budget)
```

#### 4.3.5 · Tests

- `scripts/tests/test_foundry_rbac_audit.py` — pytest unit tests with mocked `azure-mgmt-authorization` client. Cases: empty RG, single benign assignment, broad assignment flagged, guest user flagged, never-raises on auth failure.
- `scripts/tests/test_azure_monitor_alert_baseline.py` — same shape; cases per baseline kind.
- `scripts/tests/test_e2e_foundry_rbac_audit.py` — Azure E2E per AGENTS.md §2.8. Runs the probe against `<ci-resource-group>`; verifies credential chain + API surface + finding shape against real Azure.
- `scripts/tests/test_e2e_azure_monitor_alert_baseline.py` — same shape.
- Copilot-CLI fixture per skill at `skills/<skill>/test-fixture/consumer_prompt.md` — minimal happy-path consumer that runs the CLI entry against `<ci-resource-group>`, checks the manifest file exists and parses, writes Pattern 12 marker.

#### 4.3.6 · Slice C cross-cutting

- **Commit tags:** `[multi-skill]` + `[skill-rewrite]` both required.
- **Plugin version:** `plugin.json` MINOR bump (adds 2 skills) + `marketplace.json` MINOR matched.
- **CATEGORIES:** add both skills to `scripts/build-site.py` `CATEGORIES` per AGENTS.md §10.3 step 5.
- **skill-deps.yml:** add both with `depends_on: []` per AGENTS.md §10.3 (Pattern 24 carry rule).
- **AGENTS.md §12.5 counts:** bump total skills 27 → 29; auto-tier pin count +2.
- **Fixture bloat (#243):** each fixture's per-turn upload MUST stay ≤ 150K tokens per AGENTS.md §9.7 Pattern 19 addendum. Use `Step −1` audit-grep evidence pattern (lightweight `echo skills/<name>/SKILL.md` Bash step, NOT `view SKILL.md`).
- **Identifier scrub (#256/#260):** all CI resource names referenced via placeholders only. NO concrete `rg-awesome-gbb-ci` etc. in tracked files.
- **Docs site rebuild:** required per AGENTS.md §10.3 step 9.

---

### 4.4 · Slice D — Backup + resource diagnostics (2 NEW skills)

**Issues closed:** #267, #271
**Skills added:** `skills/azure-backup-readiness/`, `skills/azure-resource-diagnostics/`
**PR shape:** one multi-skill PR; commit tags `[multi-skill]` + `[skill-rewrite]`
**Threadlight unlock:** v0.5.4 — REL-007 + OBS-106 → v0.6.0 final cut

#### 4.4.1 · Same shared template as Slice C

Both Slice D skills follow the §4.3.1 probe-an-RG-emit-JSON template
verbatim. The template is now battle-tested by Slice C; Slice D is a
scale-out, not a redesign.

#### 4.4.2 · #267 — azure-backup-readiness

**Contract (locked by sibling-skills-map.md REL-007):**

```python
def probe(
    subscription_id: str,
    resource_group: str,
    protected_item_types: list[str],  # ["storage_account", "key_vault", "postgres", ...]
) -> dict
```

**What it does:** enumerates resources of `protected_item_types` in
`<resource_group>`; for each, checks whether a Recovery Services vault
OR Backup vault has the resource protected; flags unprotected items;
reports retention policy mismatches against pilot baseline (90 days
GRS, etc.).

**Backing SDKs:**
- `azure-mgmt-recoveryservices`
- `azure-mgmt-recoveryservicesbackup`
- `azure-mgmt-dataprotection` (Backup vault new path per AGENTS.md `azurebackup` tool group)
- `azure-mgmt-resource`
- `azure-identity.DefaultAzureCredential`

**Caller RBAC required:** `Backup Reader` on the resource group +
`Reader` on the protected items.

#### 4.4.3 · #271 — azure-resource-diagnostics

**Contract (locked by sibling-skills-map.md OBS-106):**

```python
def probe(
    subscription_id: str,
    resource_group: str,
    target_resource_types: list[str],  # ["storage_account", "key_vault", "container_app", ...]
) -> dict
```

**What it does:** enumerates resources of `target_resource_types` in
`<resource_group>`; for each, checks whether diagnostic settings are
configured (logs going somewhere — LAW, EH, or Storage); flags
resources with no diagnostic settings; flags settings that don't
include the recommended log categories.

**Backing SDKs:**
- `azure-mgmt-monitor` (diagnostic settings)
- `azure-mgmt-resource`
- `azure-identity.DefaultAzureCredential`

**Caller RBAC required:** `Monitoring Reader` on the resource group.

#### 4.4.4 · Per-skill file layout

Identical to §4.3.4. Each skill has:
```
skills/<skill>/
├── SKILL.md
├── README.md
├── references/
│   ├── upstream-pin.md
│   └── python/
│       ├── probe.py
│       └── __main__.py
└── test-fixture/
    └── consumer_prompt.md
```

(`azure-backup-readiness` does NOT need a `baselines/` dir — pilot
baseline values live inline in `probe.py`. `azure-resource-diagnostics`
similarly inlines recommended log categories per resource type.)

#### 4.4.5 · Tests

Same shape as Slice C: unit tests with mocked clients + E2E pytest
under `scripts/tests/test_e2e_<name>.py` + Copilot-CLI fixture per
skill.

#### 4.4.6 · Slice D cross-cutting

Identical to §4.3.6:
- `[multi-skill]` + `[skill-rewrite]` tags
- `plugin.json` + `marketplace.json` MINOR matched
- `CATEGORIES` + `.github/skill-deps.yml` entries
- AGENTS.md §12.5 counts 29 → 31; auto-tier pin count +2
- Fixture budget ≤ 150K per turn
- Identifier scrub placeholders only
- Docs site rebuild

---

### 4.5 · Slice E — Deferred to v0.7.0

**Issues:** #269 (foundry-iq PE-posture audit), #270 (foundry-hosted-agents thread retention)

**Rationale for deferral:**

1. **Tracker explicitly marks both as "deferrable."** The user's task framing repeats this: "Items 7-8 are deferrable. Don't force them into the v0.6.0 release if the rest is the natural cut-line."
2. **Neither blocks the v0.6.0 cut.** Threadlight ships v0.6.0 with MDL-010 and MDL-011 remaining `kind: manual`; the customer-pilot test can still proceed with those two findings requiring human verification.
3. **#269 has nested complexity.** It needs to introspect AI Search backings of each KI plus PE state — touches `foundry-iq` + private-endpoint discovery, which intersects `foundry-vnet-deploy` (a §9.8 "issue_only" skill the catalog already treats as manual-validation). Doing this right needs a separate design conversation.
4. **#270 is a contract negotiation.** The issue body lists either `foundry-hosted-agents` OR `foundry-memory` as the host skill. Choosing requires a sub-decision threadlight hasn't fully committed to. Defer until threadlight resolves.

**What to commit in this catalog now:** a one-paragraph "Planned for v0.7.0" note in each host skill's README.md pointing at the issues. No code, no SKILL.md changes, no pin updates. Total Slice E scope: 2 README appends, 1 commit, no version bumps.

(If the user later wants Slice E in v0.6.0, it gets its own design conversation.)

---

## 5 · Cross-cutting concerns

### 5.1 · Auth model (canonical for NEW skills)

`DefaultAzureCredential` from `azure-identity`. Reasoning:
- AGENTS.md §9.7 CI uses OIDC-federated UAMI → `DefaultAzureCredential` picks up via the `ManagedIdentityCredential` link in the chain.
- Local dev uses `az login` → picks up via `AzureCliCredential` in the chain.
- Matches `foundry-observability` E2E test pattern (the existing precedent in `scripts/tests/test_e2e_foundry_observability.py` if present, or the closest neighbor).
- Single import, no per-environment branching in SKILL.md prose.

SKILL.md for each NEW skill MUST document:
- "This skill uses `DefaultAzureCredential` from `azure-identity`. In CI, that resolves to the OIDC UAMI. Locally, run `az login` first."
- The list of RBAC roles the caller needs (from §4.3.2, §4.3.3, §4.4.2, §4.4.3 above).

### 5.2 · Output schema (locked)

Every probe emits **both**:
1. **stdout** — single-line JSON object matching the §4.3.1 schema. Human and Copilot-CLI friendly. Useful during fixture authoring and debug.
2. **manifest file** — same JSON dict written to `out/<finding-id>.json` relative to CWD. Threadlight reads this. Determinism is per Pattern 12 marker contract (write via Python file I/O, not via prose).

Threadlight contract: it pipes the CLI invocation, captures the
manifest file by path, and parses it. Stdout is ignored downstream.

### 5.3 · Fixture-bloat budget (#243 / Pattern 19 addendum)

Per AGENTS.md §9.7 Pattern 19 addendum:
- Per-turn upload **≤ 150K tokens** for any Copilot-CLI fixture.
- Use **Step −1** lightweight audit-grep evidence (`echo skills/<name>/SKILL.md`) instead of `view SKILL.md`.
- Forbid recursive `copilot` invocations (Pattern 27).
- All NEW fixtures inherit the SHARED CI HARDENING preamble at `.github/ci-shared-preamble.md`.

### 5.4 · Identifier scrub (#256/#260)

- All concrete CI resource names live in repo Secrets and `.env.ci` (gitignored).
- Tracked files use placeholders: `<ci-resource-group>`, `<ci-foundry-account>`, `<ci-monitor-workspace>`, etc.
- NEW skills must not introduce new leaks. NEW E2E test files reference secrets via env vars, not literals.

### 5.5 · CI gates (no new ones added)

All 4 slices ride the existing 6 gates per AGENTS.md §9.6:
1. `skill-validation.yml` (T0 lint)
2. `automation-pr-gate.yml` (multi-skill tag, no normalization)
3. `pin-validation.yml` (T1 pin script run for NEW pins in Slices C+D)
4. `skill-freshness.yml` (no action; runs weekly)
5. `skill-test.yml` (T2 import smoke + T3 E2E Azure for Slices C+D)
6. `auto-merge-copilot.yml` (no action; not a Copilot-authored PR)

No CI workflow changes are in scope. The matrix builder picks up
new skills automatically via `.github/skill-deps.yml` per AGENTS.md
§10.3.

### 5.6 · Plugin + marketplace versioning

- Slice A: `plugin.json` PATCH bump (no new skills); `marketplace.json` matched.
- Slice B: `plugin.json` PATCH bump (no new skills); `marketplace.json` matched.
- Slice C: `plugin.json` MINOR bump (+2 skills); `marketplace.json` matched.
- Slice D: `plugin.json` MINOR bump (+2 skills); `marketplace.json` matched.

After all 4 slices land, catalog grows 27 → 31 skills.

### 5.7 · AGENTS.md §12.5 stats updates

Each Slice C and D PR updates the table at AGENTS.md §12.5:
- Total skills count
- Auto-tier pin count (+1 per NEW skill that ships a `runnable: true` pin)
- E2E Azure tests count (+1 per NEW skill with `test_e2e_<name>.py`)

---

## 6 · Coordination + risks

### 6.1 · #244 (Citadel revamp) ↔ Slice B

**Status:** Parked. Will dispatch after MAF/GHCP wave (#261) clears.
**Decision:** Slice B lands first, #244 rebases on top.
**Fallback:** If #244 dispatches before Slice B is reviewed, coordinate with #244 author to land Slice B as a follow-up rather than blocking #244.

### 6.2 · #261 (MAF 1.8 cascade) ↔ Slices C+D

**Status:** In flight (M2-M5 + foundry-agt 4.0 wave).
**Concern:** #261 produces fixture-heavy CI traffic. Slice C and D add 2-4 more fixtures each. Combined load could surface Pattern 19 TPM saturation more often.
**Mitigation:**
- Slice C and D Copilot-CLI fixtures each use the `Step −1` lightweight-evidence pattern (saves ~5K tokens per fixture vs `view SKILL.md`).
- Per AGENTS.md §9.7 Pattern 22, matrix max-parallel: 2 is already enforced.
- If TPM throttling surfaces, fall back to Pattern 26 second-retry leg (already in `skill-test.yml`).

### 6.3 · #265 (//build 2026 audit waves) ↔ all slices

**Status:** Multi-wave audit campaign in flight.
**Concern:** None of the 10 issues here conflicts with the audit waves' target skills (per the audit-wave tracker's scope).
**Action:** Standard PR review process catches any wave-internal collision.

### 6.4 · Wider catalog risk: 4 NEW skills × Pattern 24 fanout

Per AGENTS.md §9.7 Pattern 24, every PR runs the `--changed-only`
matrix. Adding 4 NEW skills means 4 NEW matrix legs for any future PR
that touches them. Estimated CI cost per slice:
- Slice A: 0 matrix legs (no fixtures) → ~5 min total.
- Slice B: 0 matrix legs (no fixture) → ~5 min total.
- Slice C: 2 matrix legs (1 per skill) → ~30-40 min wall-clock per CI run.
- Slice D: 2 matrix legs (1 per skill) → ~30-40 min wall-clock per CI run.

Total catalog-wide weekly cost increases by ~4 matrix legs (skill-test.yml
weekly cron). Acceptable per AGENTS.md §12.5 budget (current load is
14 legs).

### 6.5 · Threadlight v0.6.0 flip timing

Each catalog slice unlocks a threadlight v0.5.x flip. Threadlight's
flip-protocol runbook says flips happen in a separate session after
the catalog slice merges. The catalog side is fire-and-forget once
merged — no callback into threadlight needed.

---

## 7 · Open questions (none blocking)

The 5 brainstorming questions are all resolved (§3 locked decisions).
Remaining items that don't block planning but the executor should
re-confirm at implementation time:

### Q-A1 · Slice A pin file scope

Does `foundry-observability/references/upstream-pin.md` already list
`azure-monitor-query`? If yes, version-bump only. If no, add to
`packages[]` and pick `~=X.Y.Z` cap per AGENTS.md §9.5 pin-cap policy.
**Resolved at impl time** by `grep azure-monitor-query` on the pin
file.

### Q-A2 · Slice A — async variants for #245

Issue #245 specifies sync + async variants. Decide at impl time
whether to ship them as `kql_probes.py` + `kql_probes/aio.py` (Azure
SDK convention) or as a single module with `def` + `async def` pairs.
Either is acceptable; pick what matches the existing
`foundry-observability` file layout.

### Q-C1 · Slice C — alert-baseline YAML schema

The baseline YAML schema for `azure-monitor-alert-baseline` isn't
locked. Propose at impl time:
```yaml
# references/baselines/foundry_pilot.yaml
required_alerts:
  - name: token_rate_spike
    severity_max: 2
    threshold_min: 0.8   # of TPM quota
    eval_window: 5m
  - name: rai_denial_spike
    ...
```
Threadlight only consumes the probe's output, not the YAML directly,
so internal schema flexibility is OK.

### Q-C2 · Slice C — testing the YAML

Should the YAML files have their own schema validator? **Recommend:**
yes, a `scripts/tests/test_alert_baselines_schema.py` that loads each
YAML and validates against a `jsonschema` definition. Cheap.

### Q-D1 · Slice D — backup-vault vs RSV ambiguity

AGENTS.md `azurebackup` tool router notes Backup vault (DPP/Data
Protection) and Recovery Services vault (RSV) coexist. #267's probe
should check **both** types (don't pick one). Doc this explicitly.

### Q-D2 · Slice D — diagnostics: which destinations count?

`azure-resource-diagnostics` flags resources with no diagnostic
settings. **Question:** does "configured" mean any destination (LAW,
EH, Storage, partner) or only LAW? **Recommend at impl:** any
destination counts as "configured"; emit a hint if it's Storage-only
(useful but rarely queried).

### Q-E1 · Slice E — README anchor

Where in the `foundry-iq` and `foundry-hosted-agents` README do the
"Planned for v0.7.0" appends go? **Recommend:** new "Roadmap" section
at the end, just before "See also."

---

## 8 · Out of scope

- Threadlight-side `kind` flips (separate session per threadlight runbook).
- #244 (Citadel revamp) — separate work item, parked.
- New CI workflows or gate shapes.
- Changes to `skill-freshness.yml`, `automation-pr-gate.yml`, or `auto-merge-copilot.yml`.
- Refactors to host skills outside the scope of each issue.
- New credential libraries beyond `DefaultAzureCredential`.
- An umbrella `azure-platform-*` skill (explicitly rejected; 4 NEW skills stay peer).
- Cross-region testing or multi-tenant CI scope changes.
- Documentation updates beyond what AGENTS.md §10.3 requires (no marketing-style explainers).

---

## 9 · Success criteria

The design is "done" when all 4 implementation plans are produced and
the user approves them. Each plan's success is defined per its own
"Done" criteria (TDD-shaped: every task ends green; CI gates pass;
docs rebuilt; plugin + marketplace + AGENTS.md §12.5 stats updated).

The full v0.6.0 critical path is "done" when all 4 slices land on
`main` in this catalog AND threadlight has flipped the 8 gated
findings to `kind: sibling-skill` in a follow-up session AND the
v0.6.0 customer-pilot dry-run passes end-to-end with all 8 findings
self-verifying.

---

## 10 · Implementation plans

Per locked decision #6: **one plan per slice**, written next via the
`superpowers:writing-plans` skill. Files:

- `docs/superpowers/plans/2026-06-11-v060-slice-a-hidden-multipliers.md`
- `docs/superpowers/plans/2026-06-11-v060-slice-b-citadel-spoke-probe.md`
- `docs/superpowers/plans/2026-06-11-v060-slice-c-rbac-and-alerts.md`
- `docs/superpowers/plans/2026-06-11-v060-slice-d-backup-and-diagnostics.md`

Slice E (deferred) gets no plan in this cycle; it's a 2-README-append
follow-up best handled inline by a future executor when the v0.7.0
timing is set.

---

## Appendix · Reference URLs (for the executor)

- Tracker (downstream): https://github.com/aiappsgbb/threadlight-skills/issues/35
- Sibling-skills-map (contracts): https://raw.githubusercontent.com/aiappsgbb/threadlight-skills/main/skills/threadlight-production-ready/references/sibling-skills-map.md
- AGENTS.md (this repo) — §2.4 frontmatter, §2.7 azd default, §2.8 E2E mandatory, §2.9 live testing, §4 mass-edit rules, §5 SemVer, §7 SSOT, §9.6 CI gates, §9.7 Patterns 1-27, §10.3 add-a-skill, §12.5 stats
- Upstream pin template: `scripts/templates/upstream-pin.template.md`
- Plugin manifest: `plugin.json` (single, repo-root)
- Marketplace: `.github/plugin/marketplace.json`
- Matrix builder: `scripts/build-test-matrix.py`
- Skill deps: `.github/skill-deps.yml`
- Validate skills: `scripts/validate-skills.py`
- Build site (docs rebuild): `scripts/build-site.py`

Per-issue references (the 10):
- #248: https://github.com/aiappsgbb/awesome-gbb/issues/248
- #245: https://github.com/aiappsgbb/awesome-gbb/issues/245
- #247: https://github.com/aiappsgbb/awesome-gbb/issues/247
- #246: https://github.com/aiappsgbb/awesome-gbb/issues/246
- #268: https://github.com/aiappsgbb/awesome-gbb/issues/268
- #272: https://github.com/aiappsgbb/awesome-gbb/issues/272
- #267: https://github.com/aiappsgbb/awesome-gbb/issues/267
- #271: https://github.com/aiappsgbb/awesome-gbb/issues/271
- #269 (deferred): https://github.com/aiappsgbb/awesome-gbb/issues/269
- #270 (deferred): https://github.com/aiappsgbb/awesome-gbb/issues/270

Coordination:
- #244 (Citadel revamp, parked): https://github.com/aiappsgbb/awesome-gbb/issues/244
- #261 (MAF 1.8 cascade, in flight): https://github.com/aiappsgbb/awesome-gbb/issues/261
- #265 (//build 2026 audit waves): https://github.com/aiappsgbb/awesome-gbb/issues/265
- #243 (fixture bloat constraints): https://github.com/aiappsgbb/awesome-gbb/issues/243
- #256 (preamble/scrub collision): https://github.com/aiappsgbb/awesome-gbb/issues/256
- #260 (identifier scrub epic): https://github.com/aiappsgbb/awesome-gbb/issues/260
