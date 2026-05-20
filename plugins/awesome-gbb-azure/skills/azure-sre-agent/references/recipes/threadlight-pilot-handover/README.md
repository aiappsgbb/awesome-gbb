# threadlight-pilot-handover

Azure SRE Agent pre-wired for the **Threadlight pilot handover** moment —
when a customer just took delivery of a Threadlight ACA-hosted pipeline (a
themed process designed by [`threadlight-design`](https://github.com/aiappsgbb/awesome-gbb/tree/main/skills/threadlight-design), deployed by [`threadlight-deploy`](https://github.com/aiappsgbb/awesome-gbb/tree/main/skills/threadlight-deploy)) and needs an
operator agent watching it from day one.

This recipe wires the SRE Agent's HTTP-trigger webhook into the Threadlight
ACA event bridge, so any unhandled exception in the pilot's AI-step or
human-step automatically posts an incident to the SRE Agent.

## Prerequisites

- Azure subscription with `Microsoft.App` RP registered (`bash scripts/preflight.sh`)
- A Threadlight pilot deployed (use [`threadlight-deploy`](https://github.com/aiappsgbb/awesome-gbb/tree/main/skills/threadlight-deploy))
- The pilot's resource group name + the ACA environment name
- The pilot's App Insights resource ID (created automatically by `foundry-observability`)

## Quick Start

```bash
cd sre-agent/sreagent-templates

./bin/new-agent.sh --recipe threadlight-pilot-handover --non-interactive \
  --set agentName=sre-threadlight-pilot \
  --set resourceGroup=rg-sre-threadlight-pilot \
  --set location=swedencentral \
  --set targetRGs=rg-threadlight-pilot-prod \
  --set threadlightAppInsightsId=/subscriptions/<sub>/resourceGroups/rg-threadlight-pilot-prod/providers/microsoft.insights/components/appin-threadlight \
  --set threadlightAcaEnvName=cae-threadlight-pilot \
  -o sre-threadlight-pilot/

./bin/deploy.sh sre-threadlight-pilot/
```

After deploy, the agent has:

- 2 connectors: App Insights + Log Analytics (the pilot's existing telemetry)
- 1 skill: `threadlight-incident-triage` — investigates pilot-step exceptions
- 1 subagent: `threadlight-runtime-investigator` — deep-dive on ACA revision and replica health
- 1 scheduled task: `daily-pipeline-health` — runs at 06:00 UTC daily

## Step 2 — wire the HTTP trigger into Threadlight

After `deploy.sh` finishes, it prints a `webhookBridgeTriggerUrl` like:

```
https://sre-threadlight-pilot--abc1234.def56789.swedencentral.azuresre.ai/api/v1/triggers/<uuid>
```

Then from the Threadlight pilot's deploy output, set the env var on every
ACA app:

```bash
az containerapp update \
  --name <pilot-app> \
  --resource-group rg-threadlight-pilot-prod \
  --set-env-vars SRE_AGENT_WEBHOOK_URL=<webhookBridgeTriggerUrl>
```

The Threadlight runtime checks this env var in its global exception handler
and POSTs a JSON incident payload when any step raises an unhandled
exception. The SRE Agent receives the trigger, kicks off
`threadlight-incident-triage`, and the operator gets a Markdown summary
within ~30s.

## Parameters

| Param | Required | Example |
|---|---|---|
| `agentName` | yes | `sre-threadlight-pilot` |
| `resourceGroup` | yes | `rg-sre-threadlight-pilot` |
| `location` | yes | `swedencentral` |
| `targetRGs` | yes | `rg-threadlight-pilot-prod` |
| `threadlightAppInsightsId` | yes | ARM ID of the pilot's App Insights |
| `threadlightAcaEnvName` | yes | The ACA environment name (used in default queries) |
| `threadlightLawId` | no | ARM ID of the pilot's LAW (defaults to the AppIn's workspace) |

## Verify

```bash
./bin/verify-agent.sh "$SUBSCRIPTION_ID" rg-sre-threadlight-pilot sre-threadlight-pilot \
  --expected sre-threadlight-pilot/
```

Manually fire a trigger to verify wiring:

```bash
curl -X POST <webhookBridgeTriggerUrl> \
  -H "Content-Type: application/json" \
  -d '{"pilot_id":"smoke-test","step":"manual","error":"smoke test from operator"}'
```

The agent should respond within 30s with a markdown investigation summary.

## Cross-skill notes

- Pair with the `gbb-foundry` plugin for richer hosted-agent subagents if the pilot includes hosted agents.
- This recipe is designed for the **handover moment**. After 4-6 weeks of operation, customers should consider migrating to a customer-owned SRE Agent (transfer ownership via Bicep re-apply with a new UAMI).
