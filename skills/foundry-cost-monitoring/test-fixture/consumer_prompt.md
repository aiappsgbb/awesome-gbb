# Customer goal — `foundry-cost-monitoring` skill smoke

You are a FinOps engineer on a customer team. You just installed the
`awesome-gbb` Copilot CLI plugin and you want to prove that the
`foundry-cost-monitoring` skill works end-to-end against your CI Azure
subscription, Application Insights workspace, and the public Azure
Retail Prices API.

**This is an EXECUTION smoke, not a catalog inspection.** You MUST run
every Bash code block below in order. Do NOT inspect repo files, do NOT
run `validate-skills.py`, do NOT rebuild docs, do NOT `git status` —
those are catalog-author concerns, not consumer-smoke concerns. Your only
acceptable terminal state is a Bash tool call that writes a marker file
to `/tmp/foundry-cost-monitoring-smoke-result` (Step 5). If you find
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
`/tmp/foundry-cost-monitoring-transcript.log`, defeating the workflow's
retry classifier (AGENTS.md § 9.7 Pattern 19 addendum). The workflow
ALREADY captures your output via the outer `tee` — your job is to
EXECUTE Steps 0-5 directly in Bash tool calls, not to "run the smoke".

Do whatever the skill tells you to do. Do NOT improvise from
training-data knowledge of Cost Management or KQL — read the skill's
`SKILL.md` first, and follow its documented contract.

This fixture is **read-only**: it does NOT create any Azure resources,
does NOT deploy any infrastructure, and does NOT invoke any models.

---

## Step 0 — Auth context (show, do not assert)

Print the auth context for the run log. Do NOT gate flow on the `az`
cache check — `azure/login@v2` already validated the credentials
upstream and Copilot CLI subprocesses don't always inherit `~/.azure/`
(AGENTS.md § 9.7 Pattern 17).

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "LAW_WORKSPACE_ID=${LAW_WORKSPACE_ID:+set}"
az account show --output table || echo "(az cache not inherited — relying on workflow OIDC)"
```

If `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, or
`LAW_WORKSPACE_ID` prints empty, the workflow's `env:` block is broken
(Pattern 11). That is a workflow bug, not a skill bug. Write the FAIL
marker (Step 5) with reason `auth context missing: <var-name>` and stop.

Do NOT run `command -v`, `find /`, or `curl -fsSL` to hunt for tooling
(Pattern 15). The CI runner already has `az` CLI 2.74+, `python3`, and
`curl` — assume them.

- **Log `az` into the subshell** so Steps 1-4 have a working token (Pattern 11
  v2 fix — `azure/login@v2` authenticates the runner's CLI cache, but copilot
  CLI spawns each tool call in a fresh subshell that cannot read that cache.
  `AZURE_FEDERATED_TOKEN_FILE` does NOT inherit either — it's set inside
  azure/login's own process, not via `core.exportVariable`. The runner-level
  `ACTIONS_ID_TOKEN_REQUEST_URL` + `ACTIONS_ID_TOKEN_REQUEST_TOKEN` vars DO
  inherit because GHA sets them on the parent process when `id-token: write`
  is in job permissions). Run this verbatim:

  ```bash
  if [ -n "${ACTIONS_ID_TOKEN_REQUEST_URL:-}" ] && [ -n "${ACTIONS_ID_TOKEN_REQUEST_TOKEN:-}" ]; then
    OIDC_TOKEN=$(curl -sS \
      -H "Authorization: bearer $ACTIONS_ID_TOKEN_REQUEST_TOKEN" \
      "${ACTIONS_ID_TOKEN_REQUEST_URL}&audience=api://AzureADTokenExchange" \
      | jq -r .value)
    if [ -n "$OIDC_TOKEN" ] && [ "$OIDC_TOKEN" != "null" ]; then
      az login --service-principal \
        --username "$AZURE_CLIENT_ID" \
        --tenant "$AZURE_TENANT_ID" \
        --federated-token "$OIDC_TOKEN" \
        --output none
      echo "subshell-az-login: ok"
    else
      echo "subshell-az-login: skipped (OIDC token fetch returned empty)"
    fi
  else
    echo "subshell-az-login: skipped (ACTIONS_ID_TOKEN_REQUEST_* missing — id-token: write not set?)"
  fi
  ```

  The `echo` line MUST land in the transcript so we have evidence the login
  path ran. `ok` is the success state; `skipped` outcomes classify downstream
  curl behaviour in Step 4.

---

## Step 1 — Retail Prices API probe (HARD GATE)

The skill (`SKILL.md` § 2) documents the anonymous public Azure Retail
Prices REST endpoint. Hit it with `urllib.request` (no SDK install, no
auth headers) for a single page of Foundry-model meters in Sweden
Central, then assert the response is well-formed.

```bash
python3 - <<'PY'
import json, sys, urllib.parse, urllib.request

base = "https://prices.azure.com/api/retail/prices"
flt = "serviceName eq 'Foundry Models' and armRegionName eq 'swedencentral' and contains(meterName, 'Tokens')"
url = f"{base}?$top=5&$filter={urllib.parse.quote(flt)}"
print(f"GET {url}")

try:
    with urllib.request.urlopen(url, timeout=20) as resp:
        if resp.status != 200:
            print(f"FAIL: HTTP {resp.status}")
            sys.exit(2)
        body = json.loads(resp.read())
except Exception as exc:
    print(f"FAIL: Retail Prices probe raised {type(exc).__name__}: {exc}")
    sys.exit(2)

items = body.get("Items") or []
if not items:
    print(f"FAIL: Retail Prices returned 200 but Items[] is empty")
    sys.exit(2)

sample = items[0]
required = ["retailPrice", "meterName", "unitOfMeasure", "armRegionName", "currencyCode"]
missing = [k for k in required if k not in sample]
if missing:
    print(f"FAIL: missing fields in sample row: {missing}")
    sys.exit(2)

# Persist sample row for Step 3 — Copilot CLI Bash invocations are
# separate shells; file is how state survives across blocks.
with open("/tmp/foundry-cost-monitoring-sample-row.json", "w") as f:
    json.dump(sample, f)

# Persist HTTP status for the Step 5 smoke-summary line.
with open("/tmp/foundry-cost-monitoring-retail-http", "w") as f:
    f.write("200")

print(f"OK: Retail Prices returned {len(items)} rows")
print(f"  sample.meterName       = {sample['meterName']}")
print(f"  sample.retailPrice     = {sample['retailPrice']}")
print(f"  sample.unitOfMeasure   = {sample['unitOfMeasure']}")
print(f"  sample.currencyCode    = {sample['currencyCode']}")
print(f"  sample.armRegionName   = {sample['armRegionName']}")
PY
```

This step is a **HARD GATE**. The Retail Prices API is anonymous,
public, and has multi-region redundancy — a failure here means the
public endpoint is genuinely down (rare) or DNS / network is broken on
the runner. Write the FAIL marker with reason `retail prices probe
failed` and stop.

---

## Step 2 — LAW gen_ai.usage probe (SOFT GATE per Pattern 13)

The skill (`SKILL.md` § 4) documents KQL projections over App Insights
`customDimensions['gen_ai.usage.*']` spans emitted by
`foundry-observability`-instrumented agents. CI runs `foundry-observability`
matrix legs that emit probe spans, so there MAY be `gen_ai.usage.*`
rows in the workspace — but there's no guarantee they fall inside this
fixture's 30-day window. Probe, then SOFT-PASS on empty.

```bash
test -n "${LAW_WORKSPACE_ID:-}" || { echo "LAW_WORKSPACE_ID not set; cannot run KQL probe"; exit 2; }

cat > /tmp/cost-mon-kql.txt <<'KQL'
union dependencies, traces, requests
| where timestamp > ago(30d)
| where isnotempty(customDimensions["gen_ai.usage.input_tokens"])
| summarize
    rows = count(),
    input_tokens  = sum(toint(customDimensions["gen_ai.usage.input_tokens"])),
    output_tokens = sum(toint(customDimensions["gen_ai.usage.output_tokens"]))
KQL

QUERY="$(cat /tmp/cost-mon-kql.txt)"

set +e
KQL_OUT=$(timeout 60s az monitor log-analytics query \
  -w "$LAW_WORKSPACE_ID" \
  --analytics-query "$QUERY" \
  -o json 2>&1)
KQL_STATUS=$?
set -e
echo "kql-rc: $KQL_STATUS (0=ok, 124=timeout, other=error)"
echo "$KQL_STATUS" > /tmp/foundry-cost-monitoring-kql-rc

echo "--- KQL output ---"
echo "$KQL_OUT" | head -40
echo "--- end KQL output ---"

if [ "$KQL_STATUS" -ne 0 ]; then
  # `az monitor log-analytics query` non-zero is most often a permissions
  # or workspace-not-found error. Print + soft-PASS — the skill itself is
  # read-only and the gen_ai data path is the responsibility of the
  # foundry-observability fixture (which gates on it). Don't double-fail.
  echo "NOTE: az monitor log-analytics query exit $KQL_STATUS; soft-PASS per Pattern 13."
  echo "0" > /tmp/foundry-cost-monitoring-law-rows
else
  ROW_COUNT=$(echo "$KQL_OUT" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d) if isinstance(d,list) else 0)')
  echo "LAW returned $ROW_COUNT row(s) with non-empty gen_ai.usage.input_tokens"
  echo "$ROW_COUNT" > /tmp/foundry-cost-monitoring-law-rows
  if [ "$ROW_COUNT" -eq 0 ]; then
    echo "NOTE: LAW empty for gen_ai.usage.input_tokens in last 30d window. Expected — fixture is read-only and CI gen_ai spans may not fall in window. Soft-PASS per Pattern 13."
  fi
fi
```

SOFT gate per Pattern 13. The marker file in Step 5 remains
`SMOKE_RESULT=PASS` whether the KQL returns 0 rows, an error, or
real data — the NOTE above captures the observation for the audit
trail. Do NOT write `SMOKE_RESULT=FAIL` for an empty KQL result or
a 403 on the LAW workspace.

---

## Step 3 — Compute projected cost (HARD GATE, no value assertion)

Prove the SKILL.md § 4 join works: pick a row from the rate card cached
in Step 1, apply it to a small synthetic token count, and print the
projected cost. Real customer code would join LAW rows × rate card; we
short-circuit that here because Step 2 is soft. NO assertion on the
computed value — rates change; we only assert the join executes without
error.

```bash
python3 - <<'PY'
import json, sys

try:
    with open("/tmp/foundry-cost-monitoring-sample-row.json") as f:
        rate = json.load(f)
except FileNotFoundError:
    print("FAIL: sample row from Step 1 missing — Step 1 did not persist /tmp/foundry-cost-monitoring-sample-row.json")
    sys.exit(2)

# Skill § 10 pitfall: unit-of-measure is a mix of '1K' and '1M'.
# Normalize to per-1K-tokens so the multiply is consistent.
uom = rate.get("unitOfMeasure", "")
price = float(rate["retailPrice"])
if uom.startswith("1K"):
    price_per_1k = price
elif uom.startswith("1M"):
    price_per_1k = price / 1000.0
else:
    print(f"FAIL: unrecognised unitOfMeasure {uom!r} — cannot normalize")
    sys.exit(2)

# Synthetic tokens — a typical small chat turn
input_tokens = 1284
output_tokens = 342
total_tokens = input_tokens + output_tokens

# Apply uniformly (real code would look up input/output meters separately
# from the rate-card cache; we exercise the multiply path only)
projected = (total_tokens / 1000.0) * price_per_1k

print(f"meter           = {rate['meterName']}")
print(f"retailPrice     = {price} per {uom}  →  ${price_per_1k:.6f} per 1K tokens (normalized)")
print(f"input_tokens    = {input_tokens}")
print(f"output_tokens   = {output_tokens}")
print(f"projected_cost  = ${projected:.6f} {rate.get('currencyCode','USD')}")
print("OK: rate-card × token-count join executed end-to-end")
PY
```

Hard gate on the JOIN EXECUTING (no `FileNotFoundError`, no unit-mix
crash, no exception). The computed cost value is NOT asserted.

---

## Step 4 — Cost Management REST query (SOFT-PASS on 403 per Pattern 25)

The skill (`SKILL.md` § 11) documents that Cost Management Reader is
required on the subscription scope to read actual cost data. The CI
UAMI may or may not have that grant yet; if it doesn't, this step
soft-passes with a NOTE containing the exact role-grant snippet for the
coordinator to apply.

```bash
test -n "${AZURE_SUBSCRIPTION_ID:-}" || { echo "AZURE_SUBSCRIPTION_ID not set"; exit 2; }
test -n "${AZURE_CLIENT_ID:-}"        || { echo "AZURE_CLIENT_ID not set"; exit 2; }

# Acquire ARM token from the env-var-driven managed identity / OIDC chain
TOKEN=$(az account get-access-token --resource https://management.azure.com --query accessToken -o tsv 2>/dev/null || true)
if [ -z "$TOKEN" ]; then
  echo "NOTE: could not acquire ARM token (az not authenticated in this subshell); skipping Cost Mgmt probe — soft-PASS per Pattern 25."
  echo "skipped" > /tmp/foundry-cost-monitoring-costmgmt-status
else
  SCOPE="/subscriptions/$AZURE_SUBSCRIPTION_ID"
  URL="https://management.azure.com${SCOPE}/providers/Microsoft.CostManagement/query?api-version=2025-03-01"
  BODY='{
    "type": "ActualCost",
    "timeframe": "MonthToDate",
    "dataset": {
      "granularity": "Daily",
      "aggregation": {
        "totalCost": {"name": "Cost", "function": "Sum"}
      }
    }
  }'

  set +e
  HTTP_RESPONSE=$(curl -sS -w "\n%{http_code}" -X POST "$URL" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "$BODY")
  CURL_STATUS=$?
  set -e

  HTTP_CODE=$(printf '%s' "$HTTP_RESPONSE" | tail -n 1)
  BODY_OUT=$(printf '%s' "$HTTP_RESPONSE" | sed '$d')

  echo "Cost Mgmt POST → HTTP $HTTP_CODE"
  printf '%s\n' "$BODY_OUT" | head -20

  if [ "$HTTP_CODE" = "200" ]; then
    ROWS=$(printf '%s' "$BODY_OUT" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len((d.get("properties") or {}).get("rows") or []))' 2>/dev/null || echo "0")
    echo "Cost Mgmt returned $ROWS aggregated row(s) for MonthToDate."
    echo "200" > /tmp/foundry-cost-monitoring-costmgmt-status
  elif [ "$HTTP_CODE" = "403" ] || [ "$HTTP_CODE" = "401" ]; then
    echo "NOTE: Cost Management returned HTTP $HTTP_CODE — Cost Management Reader role grant pending for CI UAMI."
    echo "      Documented in SKILL.md § 11. To grant (run as subscription owner):"
    echo ""
    echo "          UAMI_OBJECT_ID=\$(az ad sp show --id \"\$AZURE_CLIENT_ID\" --query id -o tsv)"
    echo "          az role assignment create \\"
    echo "              --assignee-object-id \"\$UAMI_OBJECT_ID\" \\"
    echo "              --assignee-principal-type ServicePrincipal \\"
    echo "              --role 'Cost Management Reader' \\"
    echo "              --scope \"/subscriptions/\$AZURE_SUBSCRIPTION_ID\""
    echo ""
    echo "      Soft-PASS per Pattern 25 — pending RBAC does NOT block catalog ship."
    echo "$HTTP_CODE" > /tmp/foundry-cost-monitoring-costmgmt-status
  else
    echo "NOTE: Cost Mgmt returned unexpected HTTP $HTTP_CODE — printing body for audit; soft-PASS per Pattern 25."
    echo "$HTTP_CODE" > /tmp/foundry-cost-monitoring-costmgmt-status
  fi
fi
echo "cost-mgmt-http: $(cat /tmp/foundry-cost-monitoring-costmgmt-status 2>/dev/null || echo unknown)"
```

SOFT gate per Pattern 25. Marker remains `SMOKE_RESULT=PASS` regardless
of Cost Mgmt outcome. The 403 path is the documented expected state
until the role grant lands; the NOTE block surfaces the exact remediation
command so the coordinator can apply it out-of-band.

---

## Step 5 — Marker contract (deterministic, MANDATORY)

No teardown — this fixture is read-only and created zero Azure
resources (Pattern 25 N/A for cleanup; only for the Step 4 soft-pass
classification).

Your FINAL action is to invoke the Bash tool to write the marker file.
The file's literal byte content is what CI grades; your assistant-text
reply is NOT graded.

On success (Step 0 auth context complete AND Step 1 Retail Prices probe
returned 200 + non-empty Items AND Step 3 cost computation join
executed without exception — Step 2 KQL and Step 4 Cost Mgmt outcomes
do NOT affect the marker):

Just BEFORE writing the marker, emit one summary line so the workflow
transcript artifact has all three Azure-surface outcomes on a single
grep-able line:

```bash
echo "smoke-summary: retail=$(cat /tmp/foundry-cost-monitoring-retail-http 2>/dev/null || echo n/a) kql=$(cat /tmp/foundry-cost-monitoring-kql-rc 2>/dev/null || echo n/a) costmgmt=$(cat /tmp/foundry-cost-monitoring-costmgmt-status 2>/dev/null || echo n/a)"
```

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-cost-monitoring-smoke-result
```

On Step 0 / Step 1 / Step 3 failure ONLY:

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-cost-monitoring-smoke-result
```

The marker file is single-source-of-truth (Pattern 12). Do not print
the marker token anywhere else in your reply — no echoes, no summaries,
no fenced code blocks containing the literal string. The Bash tool
write is the only legitimate emission path.

Target wall-clock: 3-5 min.
