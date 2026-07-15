# Evidence retention policy

> Referenced by `retention_policy` in the `build_evidence()` call
> (see `../runtime-audit-export.md § Step 5`).

This document defines how AGT runtime evidence is retained, how the
telemetry queue handles backpressure, and when evidence expires.

---

## Retention mode

**Mode:** `retained` — evidence files committed to source control are kept
indefinitely until explicitly deleted. Evidence is never auto-deleted from
the repository.

---

## Maximum age (telemetry sink)

| Sink | Default maximum age | Mechanism |
|------|--------------------|----|
| Application Insights | 90 days | Built-in workspace retention setting |
| Append-only blob | Operator-controlled | Azure Blob lifecycle management rule |

Operators MUST configure the Application Insights workspace retention to
match their data-governance requirements before going to production.

---

## Throughput scaling

The bounded async telemetry queue (see `../runtime-audit-export.md § Step 3`)
scales **per-session**: each agent session owns one queue instance with
`maxsize=256`. This prevents a single long-running session from consuming
unbounded memory.

For multi-tenant deployments, provision one queue per tenant context to
avoid cross-tenant queue contention.

---

## Backpressure strategy

**Strategy:** `drop-oldest` — when the queue reaches `maxsize`, the oldest
entry is evicted and the current entry is accepted. This preserves the most
recent events (most useful for incident response) while guaranteeing the
agent process never blocks indefinitely on a slow sink.

Alternative strategies by use-case:

| Strategy | When to use |
|----------|------------|
| `drop-oldest` (default) | Incident-response priority; most recent events matter most |
| `block` | Compliance scenarios where zero event loss is mandatory (accept latency risk) |
| `drop-newest` | Immutable-log scenarios where ordering matters more than recency |

---

## Expiry mechanism

**Mechanism:** `auto-expire-after-days` — configure Azure Blob lifecycle
management or the Application Insights retention slider; do not rely on
manual deletion.

Committed evidence files (`specs/agt-runtime-evidence.json`) are subject to
standard Git history retention and are NOT auto-expired by this policy.
Remove them via `git filter-repo` if required by a data-subject deletion
request.
