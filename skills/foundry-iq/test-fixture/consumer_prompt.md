# Goal — `foundry-iq` GA knowledge base + Agent Service smoke

Prove the Foundry IQ GA contract against the standing CI Azure AI Search
service. Create a UUID-suffixed index, a `searchIndex` knowledge source and a
`low`-effort knowledge base through REST API `2026-10-01`, run a `low`
retrieve, then create a `RemoteTool` project connection and a prompt agent
that answers through the KB MCP tool `knowledge_base_retrieve`
(`2026-11-01-preview`). Clean up only the objects you created.

The Search service, its managed identity and every role assignment were
provisioned separately through the checked-in `azure.yaml` + Bicep project.
This execution fixture must not provision or delete infrastructure. Never
delete or recreate the Search service, its resource group, locks, identities,
policies, or role assignments, and do not re-grant roles.

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
echo "FOUNDRY_PROJECT_ENDPOINT=${FOUNDRY_PROJECT_ENDPOINT:+set}"
echo "FOUNDRY_MODEL_DEPLOYMENT=${FOUNDRY_MODEL_DEPLOYMENT:-gpt-5.4-mini}"
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

## Step 2 — Execute the checked-in GA REST + agent smoke

Run this exact command from the repository root. Do not copy, inline, or
rewrite the script; its path is required audit evidence.

```bash
python3 skills/foundry-iq/test-fixture/live_smoke.py
```

The script uses Entra authentication and Resource Graph discovery. It
sends `api-version=2026-10-01` for the index, knowledge source, knowledge
base and retrieve, and `2026-11-01-preview` only for the KB MCP endpoint.
It calls `{project}/openai/v1/responses` without an `api-version` query
parameter. It may wait up to five minutes for role propagation; let it run.
Only `searchIndex` is exercised; Azure SQL, file, and indexed SharePoint are
GA on `2026-10-01`, while remote SharePoint, Fabric Data Agent, Fabric
Ontology, MCP server, and Work IQ are preview-only.

Success requires exit code 0, output containing
`foundry-iq-ga-kb-agent-ok`, and `/tmp/foundry-iq-smoke-evidence` showing:

- `search_api_version` is exactly `2026-10-01`
- `retrieve_activity_types` contains `modelQueryPlanning`
- `agent_mcp_tool` is exactly `knowledge_base_retrieve`
- `agent_answer_has_code` is `true`
- `knowledge_source_delete_status`, `knowledge_base_delete_status` and
  `index_delete_status` are `204` or `404`
- `agent_delete_status` and `connection_delete_status` are `200`, `202`,
  `204` or `404`

If the script fails, write the FAIL marker with the exception class or HTTP
status and stop. A cleanup warning is a transcript NOTE, but do not write the
PASS marker unless every delete-status field satisfies the evidence
contract above.

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
