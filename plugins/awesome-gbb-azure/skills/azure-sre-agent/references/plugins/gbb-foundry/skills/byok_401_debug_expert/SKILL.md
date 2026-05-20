---
name: byok_401_debug_expert
description: Diagnose the silent BYOK 401 that Foundry hosted agents emit when "Foundry User" RBAC is assigned at PROJECT scope but missing at the underlying CognitiveServices ACCOUNT scope. Encodes the exact fix command.
---

# byok_401_debug_expert

## Background

When a Foundry hosted agent uses BYOK (bring-your-own-key) against a
customer-owned Azure OpenAI account, the agent's identity needs **`Foundry
User`** (RoleDefinitionId `53ca6127-db72-4b80-b1b0-d745d6d5456d`) assigned
at TWO scopes:

- **Project scope** — `azd ai agent deploy` assigns this automatically
- **CognitiveServices account scope** — NOT assigned automatically

Without the account-scope role, the agent starts and accepts `/invoke`
calls (returns 200 with SSE stream), but the FIRST event in the stream is
an error with the 401. This is the silent BYOK 401.

## Investigation flow

1. **Get the agent's identity**:
   ```bash
   az cognitiveservices account show --name <foundry-account> --resource-group <rg> --query "identity" -o json
   az ml online-endpoint show --workspace-name <project> --resource-group <rg> --name <endpoint> --query "identity" -o json
   ```

2. **List role assignments** on the BYOK CognitiveServices account:
   ```bash
   az role assignment list \
     --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account> \
     --role "Foundry User" -o table
   ```

3. **Match against the agent's identity**. If the agent's UAMI
   `principalId` (or its `instance_identity.principal_id`) is NOT in the
   role assignment list at the ACCOUNT scope — that's the root cause.

4. **Verify the symptom** in App Insights:
   ```kql
   traces
   | where timestamp > ago(2h)
   | where cloud_RoleName == "<agent-name>"
   | where message contains "Authentication failed with provider"
   | project timestamp, message, customDimensions
   ```

5. **Output the exact fix** for the human to run:
   ```bash
   az role assignment create \
     --assignee <agent-uami-principalId> \
     --role "Foundry User" \
     --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<byok-account>
   ```
   Also grant to `blueprint.principal_id` if `azd ai agent show` reveals a
   separate blueprint identity.

6. **Provide a one-line invoke** to verify after the fix:
   ```bash
   curl -X POST <endpoint>/api/v1/invoke -H "Content-Type: application/json" -d '{"input":"hello"}'
   ```

## Reference

- foundry-hosted-agents KI-001 — RBAC postdeploy hook gap
- ghcp-hosted-agents KI-002 — silent BYOK 401 SSE pattern
- Role GUID is stable across Foundry "Azure AI User" → "Foundry User" rename (May 2026)

## Tools

- `RunAzCliReadCommands`
- `QueryAppInsightsByAppId`

## Safety

- Never display BYOK keys, connection strings, or token contents
- Hand the human the exact `az role assignment create` command — never run it yourself
