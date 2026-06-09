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

Print the auth context for the run log. Do NOT gate flow on any of
these checks — `azure/login@v2` already validated the credentials
upstream.

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
echo "LAW_WORKSPACE_ID=${LAW_WORKSPACE_ID:+set}"
az account show --output table || echo "(az cache not inherited — relying on subsequent SDK / az calls)"
```

If `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, or
`LAW_WORKSPACE_ID` prints empty, the workflow's `env:` block is broken
(AGENTS.md § 9.7 Pattern 11). That is a workflow bug, not a skill bug.
Write the FAIL marker (Step 4) with reason
`auth context missing: <var-name>` and stop.

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
read works):

```bash
az monitor log-analytics workspace show \
  --workspace-name law-awesome-gbb-ci \
  -g rg-awesome-gbb-ci \
  --query "{name:name, retentionInDays:retentionInDays, sku:sku.name}" \
  -o table
```

The CI resource group already contains `law-awesome-gbb-ci`. If this
fails with `ResourceNotFound`, that's a CI-infra regression — write
the FAIL marker with reason
`law-awesome-gbb-ci workspace not found in rg-awesome-gbb-ci` and stop.
Do NOT try to create the workspace.

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

## Step 3 — Run ONE representative Kusto query

Run a query via `az` CLI against the `law-awesome-gbb-ci` workspace.
This proves the KQL execution surface that § 6 of the runbook relies
on actually works in CI.

```bash
WORKSPACE_ID=$(az monitor log-analytics workspace show \
  --workspace-name law-awesome-gbb-ci \
  -g rg-awesome-gbb-ci \
  --query customerId -o tsv)

az monitor log-analytics query \
  --workspace "$WORKSPACE_ID" \
  --analytics-query "AzureActivity | where TimeGenerated > ago(1h) | take 5" \
  --output json
```

Empty result table is acceptable (low-activity workspace). Non-zero
exit code is NOT acceptable. A KQL syntax error from `az` is NOT
acceptable — that means the runbook's KQL is malformed.

---

## Step 4 — Marker contract (deterministic, MANDATORY)

Your FINAL action — after Steps 0-3 — is to invoke the Bash tool to
write the marker file. The file's literal byte content is what CI
grades; your assistant-text reply is NOT graded.

On success (all of: Step 2a, 2b, 2c, and Step 3 exited 0):

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-network-runbook-smoke-result
```

On ANY failure (auth context missing, workspace not found, RBAC empty,
KQL error, any az command non-zero exit):

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-network-runbook-smoke-result
```

The marker file is single-source-of-truth. Do not print the marker
token anywhere else in your reply — no echoes, no summaries, no fenced
code blocks containing the literal string. The Bash tool write is the
only legitimate emission path.
