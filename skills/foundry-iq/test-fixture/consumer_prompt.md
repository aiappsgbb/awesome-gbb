# Goal — `foundry-iq` stable GA knowledge-source smoke

Prove the narrow Foundry IQ GA programmatic slice against the standing CI
Azure AI Search service. Create a UUID-suffixed search index, create and read
a `searchIndex` knowledge source through REST API `2026-04-01`, verify the
returned kind, and clean up only the two data-plane objects you created.

The Search service was provisioned separately through the checked-in
`azure.yaml` + Bicep project. This execution fixture must not provision or
delete infrastructure. Never delete or recreate the Search service, its
resource group, locks, identities, policies, or role assignments.

This is an execution smoke, not a catalog inspection. Run every Bash block
in order. Do not inspect repo files, rebuild docs, run validators, or invoke
`copilot` recursively. You are already the running Copilot CLI process; the
outer workflow captures stdout.

---

## Step -1 — Acknowledge the skill contract

Your first action must be a separate Bash tool call containing only this
command. Do not combine it with Step 0 or any later work; the standalone
output is required by the workflow audit.

```bash
echo "skills/foundry-iq/SKILL.md"
```

Wait for that tool call to finish before proceeding.

---

## Step 0 — Show auth context

Run this block as a new Bash tool call after Step -1:

```bash
echo "AZURE_CLIENT_ID=${AZURE_CLIENT_ID:+set}"
echo "AZURE_TENANT_ID=${AZURE_TENANT_ID:+set}"
echo "AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID:+set}"
```

If any variable is empty, write the FAIL marker from Step 3 with reason
`auth context missing: <var-name>` and stop.

---

## Step 1 — Install bounded Python dependencies

```bash
python3 -m pip install --quiet \
  "azure-identity~=1.25.0" \
  "requests~=2.32.0"
```

If installation fails, write the FAIL marker with reason
`dependency install failed` and stop.

---

## Step 2 — Execute the checked-in stable REST smoke

Run this exact command from the repository root. Do not copy, inline, or
rewrite the script; its path is required audit evidence.

```bash
python3 skills/foundry-iq/test-fixture/live_smoke.py
```

The script uses Entra authentication and Resource Graph discovery. It sends
`api-version=2026-04-01` and treats only `searchIndex`, `azureBlob`,
`indexedOneLake`, and `web` as GA. Azure SQL, direct file upload,
indexed/remote SharePoint, Fabric Data Agent, Fabric Ontology, MCP server,
and Work IQ are preview-only.

Success requires exit code 0, output containing
`foundry-iq-ga-searchIndex-ok`, and `/tmp/foundry-iq-smoke-evidence` showing:

- `api_version` is exactly `2026-04-01`
- `exercised_ga_kind` is exactly `searchIndex`
- index PUT and knowledge-source PUT returned `201`
- knowledge-source GET returned `200`
- `knowledge_source_delete_status` is `204` or `404`
- `index_delete_status` is `204` or `404`

If the script fails, write the FAIL marker with the exception class or HTTP
status and stop. A cleanup warning is a transcript NOTE, but do not write the
PASS marker unless both delete-status fields satisfy the evidence contract
above.

---

## Step 3 — Write the deterministic result marker

After Step 2 succeeds, your final action is:

```bash
printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-iq-smoke-result
```

On any earlier failure:

```bash
printf 'SMOKE_RESULT=FAIL <one-line reason>\n' > /tmp/foundry-iq-smoke-result
```

The marker file is authoritative. Do not emit the marker token elsewhere.
