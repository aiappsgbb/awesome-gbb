---
name: azure-monitor-alert-baseline
description: >
  Probes Azure Monitor metric alert rules in a resource-group scope against
  one of three published baselines (foundry_pilot, spoke_minimum, production),
  returning a spec §4.3.1 sibling-skill dict with finding_id "SRE-104",
  observations, remediation hints, confidence, and never raises.
  USE FOR: threadlight SRE-104 sibling-skill flip, alert baseline audit before
  pilot handover, alert rule drift detection in a Foundry RG, observability
  readiness probe, post-deploy alert configuration check, threshold tightness
  validation against published baselines, baselined alert rule audit, monitoring
  baseline check.
  DO NOT USE FOR: creating or updating alert rules — use az monitor metrics
  alert create instead; DO NOT USE FOR: App Insights traces or logs — use
  foundry-observability; DO NOT USE FOR: Azure Service Health alerts —
  different API surface; DO NOT USE FOR: log alerts (Log Analytics scheduled
  query rules) — metric alerts only.
metadata:
  version: "1.0.0"
---

# azure-monitor-alert-baseline

Peer skill that probes Azure Monitor metric alert rules at a resource-group
scope against one of three published baselines, returning a structured
`SRE-104` finding. It wraps `MonitorManagementClient` via
`DefaultAzureCredential` and never raises — errors are captured in the returned
dict. Threadlight v0.5.3+ consumes this as the SRE-104 sibling-skill check in
its `threadlight-production-ready` OBS-203 gate.

## When to use

- **Threadlight OBS-203 sibling-skill flip** — threadlight's apply-plan
  reasoner calls `probe()` directly to satisfy the OBS-203 → SRE-104 check
  (`kind: sibling-skill`), advancing a pilot handover from manual to automated.
- **Pre-pilot observability review** of a Foundry-adjacent resource group —
  confirms the correct alert rules are configured and thresholds are within
  the baseline's prescribed maximums before spoke onboarding.
- **Scheduled CI drift check** — detects alert rule removal or threshold
  relaxation after a deployment; runnable as a CI step with no interactive auth.

## When NOT to use

- **Creating or modifying alert rules** — use `az monitor metrics alert create`
  / `az monitor metrics alert update` directly.
- **App Insights traces, logs, or availability tests** — use the
  `foundry-observability` skill for that surface.
- **Azure Service Health alerts or activity log alerts** — those use a
  different ARM API (`Microsoft.Insights/activityLogAlerts`) and are not
  covered by this probe.

## Probe contract

The probe returns a dict matching the design spec §4.3.1 sibling-skill
contract. Signature and shape are stable across `1.x` releases:

| Field               | Type                                      | Notes                                          |
|---------------------|-------------------------------------------|------------------------------------------------|
| `finding_id`        | str                                       | Always literal `"SRE-104"`                     |
| `scope`             | dict (sub_id, rg, alert_baseline_kind)    | Nested; not a string                           |
| `result`            | enum `ok` / `needs_attention` / `errored` | Never anything else                            |
| `observations`      | list[dict]                                | Empty when `result == "ok"`                    |
| `remediation_hints` | list[str]                                 | Empty when observations empty                  |
| `confidence`        | 0.0 / 0.5 / 1.0                           | See Confidence heuristic below                 |
| `probed_at`         | ISO-8601 UTC with `Z`                     | tz-aware                                       |
| `error`             | str \| None                               | `None` on success; `"<Type>: <msg>"` on errored |

**Never raises.** Any Azure exception or `ValueError` (unknown baseline kind)
is caught and surfaced via `result["error"]` with `result["result"] = "errored"`
and `confidence = 0.0`.

### Confidence heuristic

The catalog-wide §4.3.1 confidence convention (documented here so
threadlight's apply-plan reasoning is reproducible):

- `1.0` — probe completed AND `len(live_alerts) >= 1` (at least one metric
  alert exists in the RG, whether or not it matches the baseline).
- `0.5` — probe completed AND `len(live_alerts) == 0` (ambiguous: either no
  alerts configured, or RBAC-masked enumeration returned empty).
- `0.0` — probe raised internally and was caught.

### Observation rows

Each observation row has exactly one of two shapes (no others):

| Shape                  | Fields                                                             |
|------------------------|--------------------------------------------------------------------|
| `kind: missing`        | `alert_name` (str), `severity` (int), `max_threshold` (float)     |
| `kind: threshold_mismatch` | `alert_name` (str), `expected` (float), `actual` (float)      |

`result == "needs_attention"` whenever one or more `missing` or
`threshold_mismatch` observations exist. `result == "ok"` when the
observation list is empty.

### Baseline kinds

`alert_baseline_kind` must be one of the three YAML stems in
`references/baselines/`:

| Kind            | File                  | Alert count | Notes                                                                  |
|-----------------|-----------------------|-------------|------------------------------------------------------------------------|
| `foundry_pilot` | `foundry_pilot.yaml`  | 5           | HighErrorRate, LowAvailability + TokenRateSpike, RAIDenialSpike, HostedAgentInvokeError |
| `spoke_minimum` | `spoke_minimum.yaml`  | 3           | BasicErrorRate, ChatCompletion401Spike, ChatCompletionLatencyP95       |
| `production`    | `production.yaml`     | 6           | HighErrorRate (sev 1), LowAvailability, HighLatencyP99 + TokenThrottle429Rate, CostPerHourSpike, EmbeddingErrorRate |

Any other value raises `ValueError("unknown alert_baseline_kind: …")` inside
`_load_baseline`, which is caught and surfaced as `result == "errored"`.

## Probe Reference

> **MUST:** Read the canonical probe at
> [`references/python/probe.py`](references/python/probe.py). Do NOT
> re-paste its body here — the validator enforces single-source-of-truth.

## CLI

```bash
cd skills/azure-monitor-alert-baseline/references/python
mkdir -p out
python __main__.py \
    --subscription-id <sub-id> \
    --resource-group <rg> \
    --alert-baseline-kind foundry_pilot
```

Result is printed to stdout as JSON. The manifest is also written to
`out/SRE-104.json` (relative to CWD). Same-finding-ID writes overwrite the
prior manifest by design — threadlight reads the file by the literal
finding-id filename. Authentication uses `DefaultAzureCredential` (env-var →
managed identity → Azure CLI → interactive browser). The caller must hold
`Microsoft.Insights/metricAlerts/read` at the target RG scope; Reader at the
RG is sufficient.

## Threadlight integration

Threadlight v0.5.3+ consumes this probe for the SRE-104 sibling-skill flip
(`kind: sibling-skill`), advancing the OBS-203 gate from `kind: manual` to
`kind: sibling-skill`. It calls `probe()` directly (no CLI subprocess) with
`alert_baseline_kind` passed by keyword. The manifest file at
`out/SRE-104.json` is the cross-process handoff for threadlight's apply-plan
reasoner.

## Known limitations (v1.0.0)

- Only **metric alerts** are checked. Log alerts (Log Analytics scheduled
  query rules via `Microsoft.Insights/scheduledQueryRules`) are NOT covered.
  v1.1.0 can add them if asked.
- Only **RG scope** is supported. Subscription scope and management-group
  audits are intentionally excluded — the threadlight use case is
  spoke-RG-bounded.
- **Alert action group routing** (who gets paged) is NOT validated. Use a
  separate AGT probe if needed.

## See also

- [Threadlight `threadlight-production-ready` OBS-203 → SRE-104 sibling-skill flip](https://github.com/aiappsgbb/threadlight-skills/blob/main/skills/threadlight-production-ready/references/sibling-skills-map.md)
- [`azure-mgmt-monitor` SDK docs](https://learn.microsoft.com/python/api/azure-mgmt-monitor/)
- [AGENTS.md §4.3.1 sibling-skill probe contract](../../AGENTS.md) (for catalog maintainers)
