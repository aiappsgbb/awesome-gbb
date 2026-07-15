# Customer goal — `foundry-observability` skill smoke

You are a developer on a customer team. You just installed the `awesome-gbb`
Copilot CLI plugin and you want to prove that the `foundry-observability`
skill works end-to-end against your CI Application Insights + Log Analytics
Workspace.

**This is an EXECUTION smoke, not a catalog inspection.** You MUST run
every Bash code block below in order. Do NOT inspect repo files, do NOT
run `validate-skills.py`, do NOT rebuild docs, do NOT `git status` —
those are catalog-author concerns, not consumer-smoke concerns. Your only
acceptable terminal state is a Bash tool call that writes a marker file
to `/tmp/foundry-observability-smoke-result` (Step 6). If you find
yourself reading `skill-deps.yml`, `upstream-pin.md`, or anything under
`docs/`, you are off-script — stop and execute Step 0.

**CRITICAL — never invoke `copilot` recursively from a Bash tool.** You
ARE the running Copilot CLI process. Do NOT run `copilot -p ...`,
`copilot --version`, `npm install -g @github/copilot`, or any other
`copilot ...` invocation from inside a Bash tool call. Doing so spawns
a nested CLI process WITHOUT GitHub auth (the workflow only sets
`COPILOT_PROVIDER_BEARER_TOKEN` for our Foundry routing, NOT
`COPILOT_GITHUB_TOKEN`), which will (a) crash with "No authentication
information found" and (b) overwrite this run's transcript at
`/tmp/foundry-observability-transcript.log`, defeating the workflow's
retry classifier (AGENTS.md § 9.7 Pattern 19 addendum). The workflow
ALREADY captures your output via the outer `tee` — your job is to
EXECUTE Steps 0-6 directly in Bash tool calls, not to "run the smoke".

Do whatever the skill's `SKILL.md` tells you to do, but do NOT improvise
from training-data knowledge of OpenTelemetry or Azure Monitor — read
`skills/foundry-observability/SKILL.md` first, then follow the documented
contract.

---

## Step 0 — Auth context (show, do not assert)

Print the auth context for the run log. Do NOT gate flow on the `az`
cache check — `azure/login@v2` already validated the credentials upstream
and Copilot CLI subprocesses don't always inherit `~/.azure/` (AGENTS.md
§ 9.7 Pattern 17).

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "APPLICATIONINSIGHTS_CONNECTION_STRING=${APPLICATIONINSIGHTS_CONNECTION_STRING:+set}"
echo "LAW_WORKSPACE_ID=${LAW_WORKSPACE_ID:+set}"
az account show --output table || echo "(az cache not inherited — relying on SDK DefaultAzureCredential)"
```

If `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`,
`APPLICATIONINSIGHTS_CONNECTION_STRING`, or `LAW_WORKSPACE_ID` prints
empty, the workflow's `env:` block is broken (Pattern 11). That is a
workflow bug, not a skill bug. Write the FAIL marker (Step 6) with
reason `auth context missing: <var-name>` and stop.

Do NOT run `command -v`, `find /`, or `curl -fsSL` to hunt for tooling
(Pattern 15). The CI runner already has `az` CLI 2.74+; `pip install`
for Python packages is allowed inline in Step 1.

---

## Step 1 — Configure OTel + emit probe span (HARD GATE)

Read `skills/foundry-observability/SKILL.md` for the canonical wiring
contract. The skill documents `azure-monitor-opentelemetry` as the
single-call SDK that wires the OTel SDK to App Insights via the
connection string.

Generate a unique probe ID so this run's span is distinguishable from
every other matrix-leg or previous-run probe in the LAW table. **Write
it to a file** so the value survives across Bash tool calls — each
Copilot CLI Bash invocation is a fresh shell, so `export` alone does
NOT persist between separate code blocks (AGENTS.md § 9.7 Pattern 12
file-persistence rationale; same shape as the marker file).

```bash
probe_id="ci-obs-$(uuidgen | cut -c1-8)"
printf '%s' "$probe_id" > /tmp/foundry-observability-probe-id
echo "PROBE_ID=$probe_id (written to /tmp/foundry-observability-probe-id)"
```

Then install the documented dependencies and run a single Python script
that (a) reads the probe ID from the file, (b) calls
`configure_azure_monitor()` against the connection string in env,
(c) emits one probe span carrying `probe_id` as an attribute, and
(d) flushes before exit so the span actually leaves the process:

```bash
export PROBE_ID="$(cat /tmp/foundry-observability-probe-id)"
test -n "$PROBE_ID" || { echo "PROBE_ID file empty"; exit 2; }

pip install --quiet azure-monitor-opentelemetry~=1.8.8 azure-identity opentelemetry-api

python3 - <<'PY'
import os, sys
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace

try:
    configure_azure_monitor(
        connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"],
    )
except Exception as exc:
    print(f"configure_azure_monitor raised: {type(exc).__name__}: {exc}", file=sys.stderr)
    sys.exit(2)

tracer = trace.get_tracer("ci-obs")
with tracer.start_as_current_span("ci_obs_probe") as span:
    span.set_attribute("probe_id", os.environ["PROBE_ID"])
    span.set_attribute("source", "awesome-gbb-foundry-observability-fixture")

flushed = trace.get_tracer_provider().force_flush(timeout_millis=5000)
print(f"force_flush returned: {flushed}")
PY
```

This is the HARD GATE: if `configure_azure_monitor()` raises, or if the
Python script exits non-zero for any reason, the skill's documented
wiring contract is broken. Write the FAIL marker with reason
`configure_azure_monitor raised: <exc>` or `probe span emission failed:
exit <code>` and stop.

The script's success means the SDK wiring layer works. It does NOT
prove the span actually landed in LAW — that's Step 2.

---

## Step 2 — KQL probe against Log Analytics Workspace (SOFT GATE — Pattern 13)

App Insights → LAW ingestion is asynchronous with documented variable
latency (p50 ~2 min, p95 ~5 min, p99 ~10 min). The skill's
`references/queries/first-trace-probe.kql` documents the canonical
4-table probe shape because OTel spans land across `traces`, `requests`,
`dependencies`, and `exceptions` depending on span kind.

Poll the LAW workspace for your probe row, with a generous budget per
Pattern 13. Use a 360-second budget (12 iterations × 30s sleep, well
above the ≥300s floor):

```bash
PROBE_ID="$(cat /tmp/foundry-observability-probe-id)"
test -n "$PROBE_ID" || { echo "PROBE_ID file empty — Step 1 never ran"; exit 2; }

KQL=$(cat <<KQL_END
union traces, requests, dependencies, exceptions
| where timestamp > ago(30m)
| where customDimensions["probe_id"] == "$PROBE_ID"
| project timestamp, itemType, customDimensions
| take 1
KQL_END
)

LAW_HIT="false"
for i in $(seq 1 12); do
  RESULT=$(az monitor log-analytics query \
    -w "$LAW_WORKSPACE_ID" \
    --analytics-query "$KQL" \
    -o json 2>&1 || echo "[]")
  COUNT=$(echo "$RESULT" | python3 -c "import sys, json; d = json.load(sys.stdin); print(len(d) if isinstance(d, list) else 0)" 2>/dev/null || echo "0")
  if [ "$COUNT" -gt 0 ]; then
    echo "LAW probe HIT on iteration $i (after $((i*30))s)"
    LAW_HIT="true"
    break
  fi
  echo "LAW probe iteration $i: 0 rows (elapsed $((i*30))s, budget 360s)"
  sleep 30
done

if [ "$LAW_HIT" != "true" ]; then
  echo "NOTE: LAW probe empty after 360s budget. AppIns→LAW ingestion lag is documented (p99 ~10 min). Step 1 hard gate already proved SDK wiring; soft-PASS per AGENTS.md § 9.7 Pattern 13."
fi
```

This step is a SOFT gate per Pattern 13. The marker file in Step 6
remains `SMOKE_RESULT=PASS` regardless of `LAW_HIT` — the NOTE above
captures the lag observation for the audit trail without false-FAILing
on physics we don't control. Do NOT write `SMOKE_RESULT=FAIL` because
of an empty KQL result; only write FAIL if Step 0 or Step 1 failed.

---

## Step 3 — Install normaliser dependencies

Install PyYAML so the normaliser can load the YAML operating profile.
`observability_evidence.py` has no CLI flags — do not invent any.

```bash
pip install --quiet pyyaml
```

---

## Step 4 — Emit operating-evidence document

Load `references/observability-profile.yaml` with PyYAML, build evidence
with a timezone-aware UTC `captured_at`, and write
`specs/observability-evidence.json`.  The normaliser library is
`skills/foundry-observability/references/python/observability_evidence.py`
— import `build_evidence` and `write_evidence` directly; there is no CLI.

```bash
python3 - <<'PY'
import sys, json
from datetime import datetime, timezone

sys.path.insert(0, 'skills/foundry-observability/references/python')
from observability_evidence import build_evidence, write_evidence
import yaml

profile = yaml.safe_load(open('skills/foundry-observability/references/observability-profile.yaml'))
captured_at = datetime.now(timezone.utc).isoformat()
evidence = build_evidence(profile, captured_at=captured_at)
write_evidence(evidence, 'specs/observability-evidence.json')
print('Written specs/observability-evidence.json')
print(json.dumps(evidence, indent=2, sort_keys=True))
PY
```

If the script exits non-zero for any reason, write the FAIL marker with
reason `evidence emission failed: <reason>` and stop.

---

## Step 5 — Assert evidence contract (HARD GATE)

Read `specs/observability-evidence.json` and assert all required fields.
Every assertion must pass before the PASS marker is written.

```bash
python3 - <<'PY'
import json, sys

evidence = json.loads(open('specs/observability-evidence.json').read())
failures = []

# --- four alert categories ---
required_alerts = {"failure", "latency", "token_cost", "quality_safety"}
got_alerts = set(evidence.get("alert_categories", []))
if not required_alerts.issubset(got_alerts):
    failures.append(f"alert_categories missing: {required_alerts - got_alerts}")

# --- action group owner and resource_id ---
ag = evidence.get("action_group", {})
if not ag.get("owner", "").strip():
    failures.append("action_group.owner is empty")
if not ag.get("resource_id", "").strip():
    failures.append("action_group.resource_id is empty")

# --- evaluator parity and environments ---
if not evidence.get("evaluator_parity", False):
    failures.append("evaluator_parity is not True")
ev_envs = set(evidence.get("evaluator_definition", {}).get("environments", []))
expected_envs = {"dev", "ci", "production"}
if ev_envs != expected_envs:
    failures.append(f"evaluator environments {ev_envs} != {expected_envs}")

# --- evaluator name and version ---
ev_def = evidence.get("evaluator_definition", {})
if not ev_def.get("name", "").strip():
    failures.append("evaluator_definition.name is empty")
if not ev_def.get("version", "").strip():
    failures.append("evaluator_definition.version is empty")

# --- bounded sampling (both in [0, 1]) ---
sampling = evidence.get("sampling", {})
for key in ("traces", "continuous_evaluation"):
    val = sampling.get(key)
    if val is None:
        failures.append(f"sampling.{key} missing")
    elif not (0.0 <= val <= 1.0):
        failures.append(f"sampling.{key}={val} out of [0, 1]")

# --- trace policy ---
tp = evidence.get("trace_policy", {})
if not isinstance(tp.get("content_recording"), bool):
    failures.append("trace_policy.content_recording is not a bool")
if not tp.get("redaction_policy", "").strip():
    failures.append("trace_policy.redaction_policy is empty")
if not tp.get("readers_group", "").strip():
    failures.append("trace_policy.readers_group is empty")

# --- retention >= 30 ---
ret = evidence.get("retention_days")
if not isinstance(ret, int) or isinstance(ret, bool):
    failures.append(f"retention_days must be a strict int, got {type(ret).__name__}")
elif ret < 30:
    failures.append(f"retention_days={ret} < 30")

# --- positive budget ---
budget = evidence.get("monthly_budget_usd")
if budget is None:
    failures.append("monthly_budget_usd missing")
elif not isinstance(budget, (int, float)) or isinstance(budget, bool):
    failures.append("monthly_budget_usd must be a number")
elif budget <= 0:
    failures.append(f"monthly_budget_usd={budget} must be > 0")

if failures:
    for f in failures:
        print(f"ASSERT FAIL: {f}", file=sys.stderr)
    sys.exit(3)

print("All evidence contract assertions PASSED")
print(f"  alert_categories : {sorted(got_alerts)}")
print(f"  action_group.owner : {ag['owner']}")
print(f"  action_group.resource_id : {ag['resource_id'][:60]}...")
print(f"  evaluator_parity : {evidence['evaluator_parity']}")
print(f"  evaluator_environments : {sorted(ev_envs)}")
print(f"  sampling.traces : {sampling.get('traces')}")
print(f"  sampling.continuous_evaluation : {sampling.get('continuous_evaluation')}")
print(f"  trace_policy.content_recording : {tp.get('content_recording')}")
print(f"  retention_days : {ret}")
print(f"  monthly_budget_usd : {budget}")
PY
```

This is the HARD GATE: if any assertion fails, write the FAIL marker
with reason `evidence assertions failed: <first failure>` and stop.

---

## Step 6 — Marker contract (deterministic, MANDATORY)

No teardown — the probe span is ephemeral telemetry and there are no
Azure resources to delete (Pattern 25 N/A for this fixture).

Your FINAL action is to invoke the Bash tool to write the marker file.
The file's literal byte content is what CI grades; your assistant-text
reply is NOT graded.

On success (Step 0 auth context complete AND Step 1 `configure_azure_monitor`
+ span emission succeeded AND Step 4 evidence emission succeeded AND
Step 5 assertions passed — Step 2 outcome does NOT affect the marker):

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-observability-smoke-result
```

On Step 0, Step 1, Step 4, or Step 5 failure ONLY:

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-observability-smoke-result
```

The marker file is single-source-of-truth. Do not print the marker token
anywhere else in your reply — no echoes, no summaries, no fenced code
blocks containing the literal string. The Bash tool write is the only
legitimate emission path.

