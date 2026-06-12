# foundry-rbac-audit

Peer skill that probes Azure RBAC role assignments at a resource group scope
for privilege-escalation risks. Designed to flip threadlight's IAM-101
finding from `kind: manual` to `kind: sibling-skill`.

## Quick start

> Full contract: see [`SKILL.md`](SKILL.md).

```bash
pip install azure-mgmt-authorization azure-identity
cd references/python
mkdir -p out
python __main__.py \
    --subscription-id <sub-id> \
    --resource-group <rg> \
    --target-principal-types user,service_principal
```

Output (stdout, also written to `out/IAM-101.json`):

```json
{
  "finding_id": "IAM-101",
  "scope": { "sub_id": "<sub-id>", "rg": "<rg>" },
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

- `Microsoft.Authorization/roleAssignments/read`
- `Microsoft.Authorization/roleDefinitions/read`

at the target RG scope. Reader at the RG is sufficient.

## Threadlight integration

Consumed by threadlight v0.5.3+ as the IAM-101 sibling-skill via direct
Python import (no CLI subprocess). See SKILL.md § Threadlight integration.

## Out of scope (v1.0.0)

- Orphan principal detection
- Subscription scope and management-group scope audits

Both are intentional deferrals — see SKILL.md § Known limitations.

## See also

- [`SKILL.md`](SKILL.md) — full contract
- [`references/python/probe.py`](references/python/probe.py) — canonical implementation
- [`references/upstream-pin.md`](references/upstream-pin.md) — freshness pin
