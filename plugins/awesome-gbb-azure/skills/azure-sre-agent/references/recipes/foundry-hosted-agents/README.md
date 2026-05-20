# foundry-hosted-agents

Azure SRE Agent pre-wired to investigate **Microsoft Foundry hosted-agent**
operations: BYOK 401s, hosted-agent deploy failures, model deployment quota
throttles. Designed for GBB engagements running [`foundry-hosted-agents`](https://github.com/aiappsgbb/awesome-gbb/tree/main/skills/foundry-hosted-agents) or [`ghcp-hosted-agents`](https://github.com/aiappsgbb/awesome-gbb/tree/main/skills/ghcp-hosted-agents) pilots.

## Prerequisites

- Azure subscription with `Microsoft.App` RP registered (`bash scripts/preflight.sh`)
- A Foundry project deployed (use [`microsoft-foundry`](https://github.com/aiappsgbb/awesome-gbb/tree/main/skills/microsoft-foundry) or [`foundry-vnet-deploy`](https://github.com/aiappsgbb/awesome-gbb/tree/main/skills/foundry-vnet-deploy))
- At least one hosted agent deployed in the target Foundry project
- The Foundry project's App Insights resource ID (created automatically by `foundry-observability`)

## Quick Start

```bash
cd sre-agent/sreagent-templates

./bin/new-agent.sh --recipe foundry-hosted-agents --non-interactive \
  --set agentName=sre-foundry-pilot \
  --set resourceGroup=rg-sre-foundry-pilot \
  --set location=swedencentral \
  --set targetRGs=rg-foundry-prod \
  --set foundryAppInsightsId=/subscriptions/<sub>/resourceGroups/rg-foundry-prod/providers/microsoft.insights/components/appin-foundry \
  --set foundryLawId=/subscriptions/<sub>/resourceGroups/rg-foundry-prod/providers/microsoft.operationalinsights/workspaces/law-foundry \
  -o sre-foundry-pilot/

./bin/deploy.sh sre-foundry-pilot/
```

After deploy, the agent has:

- 2 connectors: App Insights + Log Analytics (the Foundry project's existing telemetry)
- 1 skill: `hosted-agent-deploy-triage` — investigates failed hosted-agent deploys
- 1 subagent: `byok-401-investigator` — diagnoses the silent 401 from the BYOK call (Foundry User RBAC scoped to project but not account)
- 1 scheduled task: `daily-hosted-agent-health-check` — runs at 06:00 UTC daily

## Parameters

| Param | Required | Example |
|---|---|---|
| `agentName` | yes | `sre-foundry-pilot` |
| `resourceGroup` | yes | `rg-sre-foundry-pilot` |
| `location` | yes | `swedencentral` |
| `targetRGs` | yes | `rg-foundry-prod` (the Foundry project's RG) |
| `foundryAppInsightsId` | yes | ARM ID of the Foundry App Insights resource |
| `foundryLawId` | yes | ARM ID of the Foundry Log Analytics workspace |
| `existingUamiId` | no | Set to reuse an existing UAMI |

## Verify

```bash
./bin/verify-agent.sh "$SUBSCRIPTION_ID" rg-sre-foundry-pilot sre-foundry-pilot \
  --expected sre-foundry-pilot/
```

## Cross-skill notes

- Pair with the `gbb-foundry` plugin (`references/plugins/gbb-foundry/`) for richer Foundry-specific subagents.
- This recipe assumes `foundry-observability` ran — i.e. App Insights and Log Analytics already collect agent traces and the project has `APPLICATIONINSIGHTS_CONNECTION_STRING` set.
- If the Foundry deployment is BYOK against a customer-owned AOAI account, also grant the SRE Agent's UAMI `Cognitive Services User` on the AOAI account so it can read deployment status.
