# azure-monitor-alert-baseline

Peer skill that probes Azure Monitor metric alert rules at a resource-group
scope against a published baseline, returning a structured `SRE-104` finding.
Designed to flip threadlight's OBS-203 finding from `kind: manual` to
`kind: sibling-skill`.

## Quick start

> Full contract: see [`SKILL.md`](SKILL.md).

```bash
pip install azure-mgmt-monitor azure-identity pyyaml
cd references/python
mkdir -p out
python __main__.py \
    --subscription-id <sub-id> \
    --resource-group <rg> \
    --alert-baseline-kind foundry_pilot
```

Output (stdout, also written to `out/SRE-104.json`):

```json
{
  "finding_id": "SRE-104",
  "scope": {
    "sub_id": "<sub-id>",
    "rg": "<rg>",
    "alert_baseline_kind": "foundry_pilot"
  },
  "result": "ok | needs_attention | errored",
  "observations": [],
  "remediation_hints": [],
  "confidence": 1.0,
  "probed_at": "2026-06-12T00:00:00Z",
  "error": null
}
```

## Authentication

Uses `DefaultAzureCredential` (env-var → managed identity → Azure CLI →
interactive browser chain). The caller MUST hold:

- `Microsoft.Insights/metricAlerts/read`

at the target RG scope. Reader at the RG is sufficient.

## Threadlight integration

Consumed by threadlight v0.5.3+ as the SRE-104 sibling-skill via direct
Python import (no CLI subprocess), advancing the OBS-203 gate. See
SKILL.md § Threadlight integration.

## Out of scope (v1.0.0)

- Log alerts (Log Analytics scheduled query rules) — metric alerts only
- Alert action group routing — use a separate AGT probe if needed

Both are intentional deferrals — see SKILL.md § Known limitations.

## See also

- [`SKILL.md`](SKILL.md) — full contract
- [`references/python/probe.py`](references/python/probe.py) — canonical implementation
- [`references/upstream-pin.md`](references/upstream-pin.md) — freshness pin
