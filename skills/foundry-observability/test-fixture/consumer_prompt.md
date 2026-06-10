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
to `/tmp/foundry-observability-smoke-result` (Step 3). If you find
yourself reading `skill-deps.yml`, `upstream-pin.md`, or anything under
`docs/`, you are off-script — stop and execute Step 0.

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
workflow bug, not a skill bug. Write the FAIL marker (Step 3) with
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

python - <<'PY'
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
  COUNT=$(echo "$RESULT" | python -c "import sys, json; d = json.load(sys.stdin); print(len(d) if isinstance(d, list) else 0)" 2>/dev/null || echo "0")
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

This step is a SOFT gate per Pattern 13. The marker file in Step 3
remains `SMOKE_RESULT=PASS` regardless of `LAW_HIT` — the NOTE above
captures the lag observation for the audit trail without false-FAILing
on physics we don't control. Do NOT write `SMOKE_RESULT=FAIL` because
of an empty KQL result; only write FAIL if Step 0 or Step 1 failed.

---

## Step 3 — Marker contract (deterministic, MANDATORY)

No teardown — the probe span is ephemeral telemetry and there are no
Azure resources to delete (Pattern 25 N/A for this fixture).

Your FINAL action is to invoke the Bash tool to write the marker file.
The file's literal byte content is what CI grades; your assistant-text
reply is NOT graded.

On success (Step 0 auth context complete AND Step 1 `configure_azure_monitor`
+ span emission succeeded — Step 2 outcome does NOT affect the marker):

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-observability-smoke-result
```

On Step 0 or Step 1 failure ONLY:

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-observability-smoke-result
```

The marker file is single-source-of-truth. Do not print the marker token
anywhere else in your reply — no echoes, no summaries, no fenced code
blocks containing the literal string. The Bash tool write is the only
legitimate emission path.
