---
name: foundry-rbac-audit
description: >
  Probes Azure RBAC role assignments at a resource-group scope for
  privilege-escalation risks (Owner, User Access Administrator, RBAC
  Administrator). Returns a spec §4.3.1 sibling-skill dict with
  finding_id "IAM-101", observations, remediation hints, confidence,
  and never raises. USE FOR: threadlight IAM-101 sibling-skill flip,
  rbac audit on a Foundry-adjacent resource group, least privilege
  review before spoke onboarding, over-privileged detection after team
  offboarding, role assignment audit for spoke security probe, scheduled
  CI security check on a Foundry project RG. DO NOT USE FOR: granting
  or revoking roles — use az role assignment create/delete instead; DO
  NOT USE FOR: Foundry-internal agent identity or per-agent-instance MI
  RBAC — use foundry-agt; DO NOT USE FOR: hub-side Citadel security
  checks — use citadel-spoke-onboarding probe_hub_contract.
metadata:
  version: "1.0.0"
---

# foundry-rbac-audit

Peer skill that probes Azure RBAC assignments at a resource-group scope for
privilege-escalation risks, returning a structured `IAM-101` finding. It wraps
`AuthorizationManagementClient` via `DefaultAzureCredential` and never raises —
errors are captured in the returned dict. Threadlight v0.5.3+ consumes this as
the IAM-101 sibling-skill check in its `threadlight-production-ready` SEC-301
gate.

## When to use

- **Threadlight IAM-101 sibling-skill flip** — threadlight's apply-plan reasoner
  calls `probe()` directly to satisfy the SEC-301 → IAM-101 check.
- **Pre-pilot security review** of a Foundry-adjacent resource group before spoke
  onboarding — confirms no over-privileged principals hold Owner or equivalent roles.
- **Scheduled CI check after team offboarding** — detects residual privilege
  assignments; orphan-principal detection (deleted Entra IDs) is explicitly out of
  scope for v1.0.0.

## When NOT to use

- **Granting or revoking role assignments** — use `az role assignment create` /
  `az role assignment delete` directly.
- **Foundry-internal agent identity or per-agent-instance MI RBAC** — use the
  `foundry-agt` skill for identity lifecycle on hosted agents.
- **Hub-side Citadel checks** — use `citadel-spoke-onboarding` and its
  `probe_hub_contract` for APIM/hub-scope governance.

## Probe contract

The probe returns a dict matching the design spec §4.3.1 sibling-skill
contract. Signature and shape are stable across `1.x` releases:

| Field               | Type                                            | Notes                                   |
|---------------------|-------------------------------------------------|-----------------------------------------|
| `finding_id`        | str                                             | Always literal `"IAM-101"`              |
| `scope`             | dict (sub_id, rg)                               | Nested; not a string                    |
| `result`            | enum `ok` / `needs_attention` / `errored`       | Never anything else                     |
| `observations`      | list[dict]                                      | Empty when `result == "ok"`             |
| `remediation_hints` | list[str]                                       | Empty when observations empty           |
| `confidence`        | 0.0 / 0.5 / 1.0                                 | See Confidence heuristic below          |
| `probed_at`         | ISO-8601 UTC with `Z`                           | tz-aware                                |
| `error`             | str \| None                                     | `None` on success; `"<Type>: <msg>"` on errored |

**Never raises.** Any Azure exception is caught and surfaced via
`result["error"]` with `result["result"] = "errored"` and `confidence = 0.0`.

### Confidence heuristic

The catalog-wide §4.3.1 confidence convention (documented here so
threadlight's apply-plan reasoning is reproducible):

- `1.0` — probe completed AND at least one role assignment matched the
  principal-type filter (whether or not any were privilege-escalation).
- `0.5` — probe completed but no assignments matched the filter
  (ambiguous: empty RG vs Reader-masked enumeration).
- `0.0` — probe raised internally and was caught.

### Observation rows

Each observation row has these keys (all populated on every row):

| Field                | Notes                                              |
|----------------------|----------------------------------------------------|
| `principal_id`       | The assignee object ID                             |
| `role_definition_id` | Full SDK resource path                             |
| `role_name`          | Friendly name (e.g. "Owner")                       |
| `principal_type`     | SDK raw value (e.g. "User")                        |
| `severity`           | `"critical"` or `"high"`                           |
| `scope`              | The assignment's scope as reported by Azure        |

The probe currently flags assignments at three privilege-escalation roles:

| Role GUID                                | Friendly name                              | Severity   |
|------------------------------------------|--------------------------------------------|------------|
| `8e3af657-a8ff-443c-a75c-2fe8c4bcb635`   | Owner                                      | critical   |
| `18d7d88d-d35e-4fb5-a5c3-7773c20a72d9`   | User Access Administrator                  | critical   |
| `f58310d9-a9f6-439a-9e8d-f62e7b41a168`   | Role Based Access Control Administrator    | high       |

## Probe Reference

> **MUST:** Read the canonical probe at
> [`references/python/probe.py`](references/python/probe.py). Do NOT
> re-paste its body here — the validator enforces single-source-of-truth.

## CLI

```bash
cd skills/foundry-rbac-audit/references/python
mkdir -p out
python __main__.py \
    --subscription-id <sub-id> \
    --resource-group <rg> \
    --target-principal-types user,service_principal
```

Result is printed to stdout as JSON. The manifest is also written to
`out/IAM-101.json` (relative to CWD). Same-finding-ID writes overwrite
the prior manifest by design (threadlight reads the file by literal
finding-id name).

Authentication uses `DefaultAzureCredential`. The caller must hold
`Microsoft.Authorization/roleAssignments/read` and
`Microsoft.Authorization/roleDefinitions/read` at the target RG scope.

## Threadlight integration

Threadlight v0.5.3+ consumes this probe for the IAM-101 sibling-skill
flip (`kind: sibling-skill`). It calls `probe()` directly (no CLI
subprocess) with `target_principal_types` passed by keyword. The manifest
file at `out/IAM-101.json` is the cross-process handoff for
threadlight's apply-plan reasoner.

## Known limitations (v1.0.0)

- Orphan principal detection (assignments to deleted Entra IDs) is
  **out of scope** for v1. Threadlight has not requested it.
- Only RG scope is supported. Subscription-scope and management-group
  audits are intentionally excluded — the threadlight use case is
  spoke-RG-bounded.
- The privilege-escalation role list is hard-coded (3 GUIDs). Custom
  roles equivalent to Owner are NOT detected. A v1.1.0 release can add
  a `custom_role_guids: list[str]` kwarg if a customer asks.

## See also

- [Threadlight `threadlight-production-ready` SEC-301 → IAM-101 sibling-skill flip](https://github.com/aiappsgbb/threadlight-skills/blob/main/skills/threadlight-production-ready/references/sibling-skills-map.md)
- [`azure-mgmt-authorization` SDK](https://learn.microsoft.com/python/api/azure-mgmt-authorization/)
- [AGENTS.md §4.3.1 sibling-skill probe contract](../../AGENTS.md) (for catalog maintainers)
