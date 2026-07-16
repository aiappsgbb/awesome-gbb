# Customer goal — `foundry-agt` execution smoke

Prove the `foundry-agt` in-process governance and runtime-evidence producer
work against the pinned AGT and Microsoft Agent Framework packages. This
smoke is local-only: it uses no Azure resources, model deployments, ACA
resources, or dataplane calls.

**This is an EXECUTION-ONLY smoke, not an authoring or catalog-maintenance
task.** You MUST run every Bash block below exactly as written and in order.
Do not rewrite, reinterpret, or replace the commands.

- Do NOT edit any file except the runtime artifacts written by the exact
  blocks below.
- Do NOT invoke `apply_patch` or any other file-editing tool.
- Do NOT inspect repository files with view, read, cat, sed, grep, rg, find,
  or directory-listing tools. This fixture is self-contained.
- Do NOT run tests, validators, linters, or package/catalog checks.
- Do NOT rebuild docs or inspect generated documentation.
- Do NOT run any `git` command, including status, diff, log, or rev-parse.
- Do NOT finish with a prose-only response. A Bash tool call that writes the
  marker file must be your final action.
- Do NOT invoke `copilot` recursively. You are already the running Copilot
  CLI process; the workflow captures your output with its outer `tee`.

The marker file is the only success source. Assistant prose, transcript text,
test output, and repository changes cannot make this smoke pass. If any block
fails, stop executing later smoke blocks and make the
failure-marker Bash write in Step 4 your next and final action.

---

## Step 0 — Acknowledge the skill contract

Run this exact block first. It supplies the workflow's post-hoc skill-usage
evidence without reading the large SKILL.md into model context.

```bash
echo "Loading execution contract: skills/foundry-agt/SKILL.md"
echo "Fixture: skills/foundry-agt/test-fixture/consumer_prompt.md"
echo "Mode: execution-only"
```

---

## Step 1 — Install the pinned packages and verify the AGT CLI

Run this exact block. Do not substitute package versions or install into the
repository.

```bash
set -euo pipefail
cd "$GITHUB_WORKSPACE"
rm -rf /tmp/foundry-agt-smoke-venv /tmp/foundry-agt-verify.log
python3 -m venv /tmp/foundry-agt-smoke-venv
. /tmp/foundry-agt-smoke-venv/bin/activate
python -m pip install --quiet \
  "agent-governance-toolkit[full]~=4.1.0" \
  "agent-framework~=1.10.0"
agt --version
agt doctor
agt verify | tee /tmp/foundry-agt-verify.log
grep -F "OWASP ASI 2026" /tmp/foundry-agt-verify.log
```

This block is a hard gate. A non-zero exit from installation, any AGT command,
or the OWASP output check is a smoke failure.

---

## Step 2 — Execute the pinned AGT runtime and export safe audit events

Run this exact Bash/Python block. It checks the six public signatures,
middleware construction, default-policy allow/deny behavior, the shared
AuditLog hash chain, and CloudEvents export. It then writes only sanitized
event metadata for the canonical runtime-evidence producer.

```bash
set -euo pipefail
cd "$GITHUB_WORKSPACE"
. /tmp/foundry-agt-smoke-venv/bin/activate
python3 - <<'PY'
# AGT_RUNTIME_SMOKE
from __future__ import annotations

import inspect
import json
from pathlib import Path

from agent_framework import Agent
from agent_os.integrations.maf_adapter import create_governance_middleware
from agent_os.policies import PolicyEvaluator
from agentmesh.governance import AuditLog

policy_dir = Path("skills/foundry-agt/references/policies")
assert policy_dir.is_dir(), f"missing policy directory: {policy_dir}"

symbols = (
    create_governance_middleware,
    PolicyEvaluator.evaluate,
    PolicyEvaluator.load_policies,
    AuditLog.log,
    AuditLog.export_cloudevents,
    Agent.__init__,
)
for symbol in symbols:
    print(f"SIGNATURE {symbol.__module__}.{symbol.__qualname__}{inspect.signature(symbol)}")
assert "middleware" in inspect.signature(Agent.__init__).parameters

audit_log = AuditLog()
middleware = create_governance_middleware(
    policy_directory=policy_dir,
    allowed_tools=[],
    denied_tools=[],
    agent_id="ci-smoke-agt",
    enable_rogue_detection=False,
    audit_log=audit_log,
)
assert isinstance(middleware, list)
assert len(middleware) >= 2
print(f"MIDDLEWARE count={len(middleware)}")

evaluator = PolicyEvaluator()
evaluator.load_policies(policy_dir)
deny_decision = evaluator.evaluate({"message": "DROP TABLE users"})
allow_decision = evaluator.evaluate({"message": "hello"})
assert str(getattr(deny_decision, "action", "")).lower() == "deny"
assert str(getattr(allow_decision, "action", "")).lower() != "deny"
print(
    "POLICY "
    f"deny={getattr(deny_decision, 'action', None)} "
    f"allow={getattr(allow_decision, 'action', None)}"
)

audit_log.log(
    "tool_call",
    "agt://ci-smoke-agent",
    "read_record",
    resource="record://example",
    data={"session_id": "session-allow"},
    outcome="success",
    policy_decision="allow",
    trace_id="trace-allow",
    policy_version="2026.07",
)
audit_log.log(
    "tool_call",
    "agt://ci-smoke-agent",
    "delete_record",
    resource="record://example",
    data={"session_id": "session-deny"},
    outcome="denied",
    policy_decision="deny",
    trace_id="trace-deny",
    policy_version="2026.07",
)

integrity_result = audit_log.verify_integrity()
integrity_verified = (
    bool(integrity_result[0])
    if isinstance(integrity_result, tuple)
    else bool(integrity_result)
)
assert integrity_verified, f"AuditLog integrity failed: {integrity_result!r}"

cloud_events = list(audit_log.export_cloudevents())
assert len(cloud_events) == 2
reasons = {
    "read_record": str(getattr(allow_decision, "reason", "allowed")),
    "delete_record": str(getattr(deny_decision, "reason", "blocked")),
}
safe_events = []
for cloud_event in cloud_events:
    data = dict(cloud_event["data"])
    action = str(data["action"])
    safe_events.append(
        {
            "event_id": str(cloud_event["id"]),
            "timestamp": str(cloud_event["time"]),
            "event_type": str(cloud_event["type"]),
            "agent_id": str(cloud_event["source"]),
            "session_id": str(data["session_id"]),
            "policy_name": "foundry-agt-default",
            "tool_name": action,
            "decision": str(data["policy_decision"]),
            "reason": reasons[action],
            "evaluation_ms": 0.0,
        }
    )

raw_safe_events = json.dumps(safe_events, indent=2, sort_keys=True)
for sentinel in ("DROP TABLE", "Bearer ", "api_key="):
    assert sentinel not in raw_safe_events
Path("/tmp/foundry-agt-safe-events.json").write_text(
    raw_safe_events + "\n",
    encoding="utf-8",
)
Path("/tmp/foundry-agt-integrity-ok").write_text("true\n", encoding="utf-8")
print("AGT_RUNTIME_SMOKE=PASS")
PY
```

This block is a hard gate. The safe-events and integrity files must be
created by this runtime execution; do not synthesize or hand-edit them.

---

## Step 3 — Invoke the canonical runtime-evidence producer

Run this exact Bash/Python block. It imports the producer from
`references/python/runtime_evidence.py`; it does not redefine the producer.

```bash
set -euo pipefail
cd "$GITHUB_WORKSPACE"
export AGT_SAFE_EVENTS_PATH="/tmp/foundry-agt-safe-events.json"
export AGT_INTEGRITY_PATH="/tmp/foundry-agt-integrity-ok"
export AGT_EVIDENCE_PATH="specs/agt-runtime-evidence.json"
python3 - <<'PY'
# RUNTIME_EVIDENCE_PRODUCER_SMOKE
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

workspace = Path(os.environ["GITHUB_WORKSPACE"])
sys.path.insert(
    0,
    str(workspace / "skills" / "foundry-agt" / "references" / "python"),
)
from runtime_evidence import build_evidence, write_evidence

safe_events = json.loads(
    Path(os.environ["AGT_SAFE_EVENTS_PATH"]).read_text(encoding="utf-8")
)
integrity_verified = (
    Path(os.environ["AGT_INTEGRITY_PATH"]).read_text(encoding="utf-8").strip()
    == "true"
)
assert integrity_verified, "AGT runtime did not verify AuditLog integrity"

redaction_policy = "skills/foundry-agt/references/policies/pii-deny.yaml"
retention_policy = "skills/foundry-agt/references/runtime-audit-export.md"
assert (workspace / redaction_policy).is_file()
assert (workspace / retention_policy).is_file()

evidence = build_evidence(
    safe_events,
    policy_version="foundry-agt-default@1.0",
    redaction_policy=redaction_policy,
    retention_policy=retention_policy,
    integrity_verified=integrity_verified,
    captured_at=datetime.now(timezone.utc).isoformat(),
)
write_evidence(os.environ["AGT_EVIDENCE_PATH"], evidence)

evidence_path = Path(os.environ["AGT_EVIDENCE_PATH"])
raw_evidence = evidence_path.read_text(encoding="utf-8")
written = json.loads(raw_evidence)
assert written["schema"] == "foundry-agt-runtime-evidence/v1"
assert written["events_observed"]["allow"] >= 1
assert written["events_observed"]["deny"] >= 1
assert written["integrity_verified"] is True
for sentinel in ("DROP TABLE", "Bearer ", "api_key="):
    assert sentinel not in raw_evidence
print(f"RUNTIME_EVIDENCE_SMOKE=PASS path={evidence_path}")
PY
```

This block is a hard gate. Success requires the actual
`specs/agt-runtime-evidence.json` artifact and all assertions above.

---

## Step 4 — Write the authoritative result marker

Your FINAL action must be one Bash tool call containing exactly one of the
following commands. Do not emit assistant prose before or after this action.

After Steps 0-3 all exit successfully:

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-agt-smoke-result
```

If any prior step fails:

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-agt-smoke-result
```

Do not print either marker token to stdout. Do not put a marker token in a
summary or fenced prose response. CI reads only the literal bytes at
`/tmp/foundry-agt-smoke-result`; the marker Bash write must be your final
action.
