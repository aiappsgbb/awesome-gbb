# Customer goal — `foundry-network-runbook` skill smoke

You are a network on-call operator. A Foundry deployment in
`rg-awesome-gbb-ci` completed successfully a few hours ago. You want to
prove the `foundry-network-runbook` skill's diagnostic command surface
actually executes against your CI environment.

This is a **READ-ONLY** smoke. You will NOT create, modify, or delete
any Azure resource. No tear-down step exists because nothing is
created.

---

## Step 0 — Auth context (show, do not assert)

Print the auth context for the run log. Gate execution only on those
three core Azure identity variables. `LAW_WORKSPACE_ID` and
`az account show` are audit context only; do not gate flow on either
because `azure/login@v2` already validated credentials upstream and LAW
is optional.

```bash
rm -f /tmp/foundry-network-runbook-law-absent
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "LAW_WORKSPACE_ID=${LAW_WORKSPACE_ID:+set}"
az account show --output table || echo "(az cache not inherited — relying on subsequent SDK / az calls)"
```

Only `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, and
`AZURE_SUBSCRIPTION_ID` are mandatory. If any of those three prints
empty, the workflow's `env:` block is broken (AGENTS.md § 9.7 Pattern
11). That is a workflow bug, not a skill bug. Write the FAIL marker
(Step 4) with reason `auth context missing: <var-name>` and stop.

`LAW_WORKSPACE_ID` is optional and is printed for audit context only.
An empty value MUST NOT fail the smoke; Step 2a independently detects
whether the optional LAW workspace exists and takes the documented
soft-skip path when it does not.

---

## Step 1 — Read the skill

Open `skills/foundry-network-runbook/SKILL.md`. Section § 3 (pre-flight
checklist) lists 7 diagnostic commands. Section § 4 is the symptom
matrix. Section § 6 lists Kusto queries. Read § 3, § 4, and § 6 before
running the next two steps.

---

## Step 2 — Run THREE representative diagnostics from § 3

Run these three commands. Each one MUST execute (exit code 0). Empty
result is acceptable — the goal is to prove the diagnostic surface
works end-to-end against real Azure, not to assert specific data
exists.

**a) Log Analytics workspace probe** (proves the LAW management-plane
read works — BEST-EFFORT, see soft-skip below):

```bash
LAW_PROBE_ERROR="/tmp/foundry-network-runbook-law-probe-error"
rm -f "$LAW_PROBE_ERROR"
trap 'rm -f "$LAW_PROBE_ERROR"' EXIT
if az monitor log-analytics workspace show \
  --workspace-name law-awesome-gbb-ci \
  -g rg-awesome-gbb-ci \
  --query "{name:name, retentionInDays:retentionInDays, sku:sku.name}" \
  -o table 2>"$LAW_PROBE_ERROR"; then
  rm -f /tmp/foundry-network-runbook-law-absent
  echo "LAW present — management-plane read OK"
elif grep -Eqi '\((ResourceNotFound|WorkspaceNotFound)\)' "$LAW_PROBE_ERROR"; then
  : > /tmp/foundry-network-runbook-law-absent
  echo "NOTE: law-awesome-gbb-ci absent in rg-awesome-gbb-ci — LAW-dependent probes (2a assertion + Step 3 Kusto) soft-skipped; LAW-independent surfaces (2b private-DNS, 2c RBAC) still asserted."
else
  cat "$LAW_PROBE_ERROR" >&2
  exit 1
fi
```

`law-awesome-gbb-ci` is **not** in the standing CI-infra inventory
(AGENTS.md § 9.7 lists AI Services, ACR, and the Container App
Environment — no standalone LAW workspace). When it is absent, this is
NOT a CI-infra regression and MUST NOT FAIL the smoke: persist the
absence marker at `/tmp/foundry-network-runbook-law-absent`, emit the
NOTE above, and carry on. The file persists the decision across separate
Bash tool calls; a shell variable would not. The LAW-independent
diagnostic surfaces (2b, 2c) still prove the runbook's read paths work.
Only a confirmed `ResourceNotFound` / `WorkspaceNotFound` response takes
this soft-skip. Authentication, authorization, CLI, and transient
management-plane errors are real failures; write the FAIL marker with
the reported error and stop. Do NOT try to create the workspace.

**b) Private DNS zone enumeration** (proves the private-DNS read
surface works):

```bash
az network private-dns zone list -g rg-awesome-gbb-ci -o table || true
```

Empty result is acceptable. Non-zero exit code is NOT acceptable.

**c) RBAC introspection on the CI UAMI** (proves the role-assignment
read surface works AND that the UAMI has the pre-granted roles per
AGENTS.md § 9.7):

```bash
az role assignment list \
  --assignee "$AZURE_CLIENT_ID" \
  --all \
  --query "[].{role:roleDefinitionName, scope:scope}" \
  -o table
```

MUST return **at least one row** (the pre-granted Contributor /
AcrPush / Cognitive Services OpenAI User / Foundry User assignments).
If empty, the UAMI identity context is broken — that is a
workflow/identity bug, not a skill bug. Write the FAIL marker with
reason `UAMI has no role assignments` and stop.

---

## Step 3 — Run ONE representative Kusto query (BEST-EFFORT)

Run a query via `az` CLI against the `law-awesome-gbb-ci` workspace.
This proves the KQL execution surface that § 6 of the runbook relies
on actually works in CI.

**Skip this step entirely if the persisted absence marker from Step 2a
exists** — the workspace isn't provisioned in CI, so there's nothing to
query. Emit `NOTE: Step 3 Kusto query soft-skipped (LAW absent)` and
proceed to Step 4. This is a soft-skip, NOT a FAIL.

```bash
if [ ! -f /tmp/foundry-network-runbook-law-absent ]; then
  WORKSPACE_ID=$(az monitor log-analytics workspace show \
    --workspace-name law-awesome-gbb-ci \
    -g rg-awesome-gbb-ci \
    --query customerId -o tsv)

  az monitor log-analytics query \
    --workspace "$WORKSPACE_ID" \
    --analytics-query "AzureActivity | where TimeGenerated > ago(1h) | take 5" \
    --output json
else
  echo "NOTE: Step 3 Kusto query soft-skipped (LAW absent)"
fi
```

When LAW is present: empty result table is acceptable (low-activity
workspace). Non-zero exit code is NOT acceptable. A KQL syntax error
from `az` is NOT acceptable — that means the runbook's KQL is malformed.

---

## Step 4 — Marker contract (deterministic, MANDATORY)

Your FINAL action — after Steps 0-3 — is to invoke the Bash tool to
write the marker file. The file's literal byte content is what CI
grades; your assistant-text reply is NOT graded.

On success — all LAW-**independent** surfaces passed (Step 2b
private-DNS exit 0, Step 2c RBAC returned ≥1 row) AND either LAW was
present and its probes (2a + Step 3) exited 0, OR LAW was absent and
those two were soft-skipped per the persisted absence marker:

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-network-runbook-smoke-result
```

A soft-skipped LAW (workspace absent) is still a PASS — the marker file
MUST remain byte-exact `SMOKE_RESULT=PASS\n`; the LAW-absent NOTE goes
only to your stdout transcript, never into the marker.

On a real failure (auth context missing, RBAC empty, private-DNS
non-zero exit, a non-not-found error from Step 2a, OR — when LAW was
PRESENT — a non-zero exit / KQL error from Step 3):

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-network-runbook-smoke-result
```

Note: `law-awesome-gbb-ci workspace not found` is NO LONGER a failure
reason — it is the soft-skip path above.

The marker file is single-source-of-truth. Do not print the marker
token anywhere else in your reply — no echoes, no summaries, no fenced
code blocks containing the literal string. The Bash tool write is the
only legitimate emission path.
