---
name: hosted_agent_deploy_expert
description: Investigate failed Microsoft Foundry hosted-agent deployments — MAF SDK breaking changes, ACR push, ACA rollout, BYOK provisioning, and the azd ai agent extension's known envelope and RBAC quirks.
---

# hosted_agent_deploy_expert

## When to use

- A user reports a failed `azd up`, `azd ai agent deploy`, or `azd deploy` for a Foundry hosted agent
- A scheduled task flags failed deployments in the monitored Foundry project
- A hosted agent starts but the first `/invoke` returns errors

## Investigation flow

1. **Identify the failed deploy** — agent name, approximate time, which command the user ran.

2. **Check the Foundry project's deployments**:
   ```bash
   az ml online-deployment list \
     --workspace-name <project> --resource-group <rg> \
     --output table
   ```
   Capture `instanceName`, `provisioningState`, `failureReason` for each failed deployment.

3. **Pull container logs from App Insights** for the failure window:
   ```kql
   traces
   | where timestamp > ago(1h)
   | where cloud_RoleName == "<agent-name>"
   | where severityLevel >= 2
   | project timestamp, message, severityLevel, customDimensions
   | top 50 by timestamp desc
   ```

4. **Classify by pattern**:

   | Pattern in logs | Root cause | KI |
   |---|---|---|
   | `Authentication failed with provider ... (HTTP 401)` | Foundry User missing at account scope | foundry-hosted-agents KI-001 |
   | `cannot import name 'AzureOpenAIChatClient' from 'agent_framework.azure'` | MAF SDK 1.4.0 breaking change | foundry-hosted-agents KI-002 (replace with `OpenAIChatClient` from `agent_framework.openai`) |
   | `SkillsProvider object has no attribute 'skill_paths'` | MAF API change | foundry-hosted-agents KI-003 (use `SkillsProvider.from_paths(...)`) |
   | `Quota exceeded` / `OperationLimitExceeded` | AOAI TPM cap hit | Hand off to `quota_throttle_expert` |
   | `ImagePullBackOff` / `pull access denied` | Pull identity, registry mode/policy or reachability needs verification | Use the selected hosted contract's actual pull identity and mode-appropriate repository permission; do not grant to the agent identity or change registry mode automatically |
   | `403 Forbidden /openai/deployments/...` | Actual caller lacks the required OpenAI data action, or another access boundary rejected it | Verify caller/scope and exact data actions first; account-level OpenAI access uses Cognitive Services OpenAI User, not a broad automatic grant |
   | `Request body must be a JSON object with a non-empty input string` | `azd ai agent invoke` envelope bug | ghcp-hosted-agents KI-001 (use `curl` with `{"input":"..."}`) |
   | Manifest/schema rejected | Consumer/profile mismatch is one candidate | Select the versioned foundry-hosted-agents contract; preserve legacy files and compare actual consumer output before changing them |

5. **For 401 patterns**, hand off to `byok_401_debug_expert`.
6. **For 429/quota**, hand off to `quota_throttle_expert`.

## Tools

- `RunAzCliReadCommands`
- `QueryAppInsightsByAppId`
- `QueryLogAnalyticsByWorkspaceId`

## Safety

- Never display Foundry connection strings, AOAI keys, or ACR passwords
- Read-only investigation — every change suggestion is for the human to approve
