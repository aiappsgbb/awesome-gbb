# Runtime audit export — operator run-book

> Source of truth for `../../SKILL.md § Runtime audit evidence`.

This document describes the exact operator flow for exporting durable,
sanitized runtime audit evidence from a governed Foundry agent. Follow
every step in order. Do NOT paste the canonical function bodies inline —
link to the source files listed in the table below instead.

---

## Canonical sources

| File | What it owns |
|------|-------------|
| [`runtime-evidence.schema.json`](runtime-evidence.schema.json) | JSON Schema (Draft 7) for the evidence envelope |
| [`python/runtime_evidence.py`](python/runtime_evidence.py) | `build_evidence()` and `write_evidence()` — copy verbatim, do NOT redefine |
| [`data/runtime-evidence.valid.json`](data/runtime-evidence.valid.json) | Valid reference fixture (used by CI contract tests) |
| [`data/runtime-evidence.invalid.json`](data/runtime-evidence.invalid.json) | Deliberately invalid fixture (schema reject test) |

---

## Prerequisites

```
pip install agent-governance-toolkit[full] agent-framework~=1.8.0
```

Policy YAML lives in `skills/foundry-agt/references/policies/`. Point
`policy_directory` at that path (or your own policy dir).

---

## Step 1 — Construct the governed agent with one shared AuditLog

Reuse **one** `AuditLog` instance across the entire session. Pass it into
`create_governance_middleware()` so every middleware layer writes to the
same chain.

```python
from agentmesh.governance import AuditLog
from agent_os.integrations.maf_adapter import create_governance_middleware
from agent_framework import Agent

# One shared log for the entire session — never create multiple instances.
audit_log = AuditLog()

middleware = create_governance_middleware(
    policy_directory="<path-to-policy-dir>",
    allowed_tools=["<allowed-tool-name>"],
    denied_tools=["<denied-tool-name>"],
    agent_id="<agent-id>",
    audit_log=audit_log,          # shared instance
    enable_rogue_detection=False,  # Known Issue #1: requires capability profile
)

agent = Agent(
    client=<azure_inference_client>,
    instructions="<system-prompt>",
    name="<agent-name>",
    middleware=middleware,
    tools=[<tool_list>],
)
```

> **Why one shared log?** Each `AuditLog` maintains its own hash-chain.
> Using multiple instances means `verify_integrity()` only covers a
> partial chain — the OWASP ASI 2026 tamper-evidence guarantee fails.

---

## Step 2 — Run the session (one allow, one deny)

Exercise at minimum:

- **One allowed tool call** — e.g., call `<allowed-tool-name>` with a
  benign payload. The middleware permits it and logs the ALLOW event.
- **One denied tool call** — e.g., attempt `<denied-tool-name>` or send
  a message that triggers the `block-sql-injection` rule. The middleware
  blocks it and logs the DENY event.

```python
# Illustrative — replace with your agent invocation pattern.
result_allow = await agent.run("<benign-request-that-uses-allowed-tool>")
result_deny  = await agent.run("<request-that-triggers-denied-tool>")
```

Both events are accumulated in `audit_log` automatically by
`AuditTrailMiddleware`.

---

## Step 3 — Export sanitized metadata to persistent audit sink

Export the hash-chain as OTel CloudEvents and send to Application Insights:

```python
import asyncio
import sys
sys.path.insert(0, "<repo-root>/skills/foundry-agt/references/python")
from runtime_evidence import extract_cloudevent_payload

# Bounded async telemetry queue — prevents unbounded memory growth
# and provides backpressure when the sink is slow.
_TELEMETRY_QUEUE: asyncio.Queue[dict] = asyncio.Queue(maxsize=256)

async def _drain_to_sink(q: asyncio.Queue, app_insights_client) -> None:
    """Worker: dequeue events and forward to the sink."""
    while True:
        try:
            event = q.get_nowait()
        except asyncio.QueueEmpty:
            break
        # extract_cloudevent_payload handles both flat and CloudEvent-envelope
        # forms.  It raises ValueError for non-mapping input or non-mapping
        # `data`, so malformed entries are caught here rather than silently
        # emitting empty telemetry.
        try:
            safe = extract_cloudevent_payload(event)
        except ValueError:
            q.task_done()
            continue
        app_insights_client.track_event("<agt-audit-event>", safe)
        q.task_done()

# Enqueue CloudEvents from the audit log (do NOT iterate raw event objects
# — use export_cloudevents() so AGT strips internal fields).
for cloud_event in audit_log.export_cloudevents():
    try:
        _TELEMETRY_QUEUE.put_nowait(dict(cloud_event))
    except asyncio.QueueFull:
        # Backpressure: drop the oldest entry and re-enqueue current.
        _TELEMETRY_QUEUE.get_nowait()
        _TELEMETRY_QUEUE.task_done()
        _TELEMETRY_QUEUE.put_nowait(dict(cloud_event))

# Flush synchronously before process exit.
asyncio.run(_drain_to_sink(_TELEMETRY_QUEUE, <app_insights_client>))
```

The persistent audit sink (Application Insights / append-only blob) receives
the full sanitized CloudEvents stream. **This sink is the detailed log** and
must NOT be committed to source control.

---

## Step 4 — Verify chain integrity

```python
ok = audit_log.verify_integrity()
assert ok, "AuditLog integrity check failed — chain may be tampered"
```

Pass the boolean result as `integrity_verified` in the next step.

---

## Step 5 — Build and write the committed evidence record

Import the canonical helpers — do NOT redefine them inline:

```python
import sys
sys.path.insert(0, "<repo-root>/skills/foundry-agt/references/python")
from runtime_evidence import build_evidence, write_evidence
```

Collect sanitized metadata from the audit log and call `build_evidence()`.
Pass **only** the fields declared in `REQUIRED_FIELDS` (from `runtime_evidence`)
— never pass prompt text, model responses, tool arguments, credentials, or
personal data.

`redaction_policy` and `retention_policy` MUST be **non-empty
repository-relative path strings** pointing to the actual policy documents in
your repository (e.g. `"docs/pii-redaction.md"`, `"infra/monitoring.bicep"`).
Inline policy objects are not accepted — Threadlight path-presence verification
resolves these paths at gate time.

```python
from datetime import timezone, datetime

# Collect only safe per-event metadata from the audit log.
safe_events = []
for entry in audit_log.entries:          # AGT internal list
    safe_events.append({
        "event_id":     str(entry.event_id),
        "timestamp":    entry.timestamp.isoformat(),
        "event_type":   str(entry.event_type),
        "agent_id":     str(entry.agent_id),
        "session_id":   str(entry.session_id or ""),
        "policy_name":  str(entry.policy_name or ""),
        "tool_name":    str(entry.tool_name or ""),
        "decision":     str(entry.decision),
        "reason":       str(entry.reason or ""),
        "evaluation_ms": float(entry.evaluation_ms or 0),
    })

evidence = build_evidence(
    safe_events,
    policy_version="<semver-or-date-stamp>",
    redaction_policy="docs/pii-redaction.md",
    retention_policy="infra/monitoring.bicep",
    integrity_verified=ok,
    captured_at=datetime.now(tz=timezone.utc).isoformat(),
)
```

---

## Step 6 — Write `specs/agt-runtime-evidence.json`

```python
write_evidence("specs/agt-runtime-evidence.json", evidence)
```

`write_evidence()` creates parent directories and writes deterministic
sorted JSON. The file is safe to commit — it contains no sensitive data.

---

## Retention policy

The committed evidence record carries `retention_policy` as a
**repository-relative path string** (e.g. `"infra/monitoring.bicep"`).  The
referenced document — not the evidence JSON — is where the full policy lives.
That document MUST declare:

| Concern | What to declare |
|---------|-----------------|
| **Lifecycle** | Expiry mechanism (e.g. auto-expire-after-days, manual deletion) |
| **Throughput scaling** | How the sink scales under load (e.g. per-session, per-tenant) |
| **Backpressure** | What happens when the queue is full (e.g. drop-oldest, block) |

Only the path is committed to source control.  Threadlight path-presence
verification will resolve it at gate time.

---

## Bounded async telemetry queue — design rationale

The queue in Step 3 is bounded (`maxsize=256`) to prevent the telemetry
path from consuming unbounded memory when the downstream sink is slow or
unavailable.

**Backpressure behaviour:** When the queue reaches `maxsize`, the oldest
entry is evicted (`drop-oldest`) and the current entry is accepted. This
preserves the most recent events — the ones most likely to be needed for
incident response — while guaranteeing that the agent process never blocks
indefinitely waiting for the sink.

**Explicit shutdown flush:** Call `asyncio.Queue.join()` (or the synchronous
`asyncio.run(_drain_to_sink(...))` pattern above) before process exit to
flush any remaining events. Never rely on process-exit finalizers for
telemetry delivery.

---

## What is NOT in the committed artifact

The following are **never** written to `specs/agt-runtime-evidence.json`
or committed to source control:

- Prompt text or system messages
- Model responses
- Tool argument values (including any placeholders that could infer sensitive data)
- Credentials, API keys, tokens, secrets
- Personal data (user identifiers, email addresses, IP addresses)
- Raw CloudEvents payloads (those go to the configured sink only)

---

## Verification

After writing `specs/agt-runtime-evidence.json`, verify it satisfies the
schema and the non-sensitive-data contract:

```python
import json, pathlib

evidence = json.loads(pathlib.Path("specs/agt-runtime-evidence.json").read_text())

assert evidence["schema"] == "foundry-agt-runtime-evidence/v1"
assert evidence["allow_count"] >= 1
assert evidence["deny_count"] >= 1
assert evidence["integrity_verified"] is True

SENTINEL_SECRETS = ["DROP TABLE", "credential-leak-sentinel-7f9c", "api_key="]
payload = json.dumps(evidence)
for sentinel in SENTINEL_SECRETS:
    assert sentinel not in payload, f"Sentinel value found in evidence: {sentinel!r}"
```
