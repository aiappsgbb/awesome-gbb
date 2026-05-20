# citadel-routed

Azure SRE Agent with `defaultModelProvider: Azure OpenAI` routed through an
**AI Citadel APIM gateway**. The agent's outbound LLM traffic is keyless
(Foundry MI token validated by APIM) and observable end-to-end through the
Citadel hub. Designed for GBB engagements that already operate (or are
deploying) a Citadel governance hub.

## Prerequisites

- An Azure subscription with `Microsoft.App` RP registered (`./bin/install-prerequisites.sh && bash scripts/preflight.sh`)
- An **AI Citadel hub** deployed (use [`citadel-hub-deploy`](https://github.com/aiappsgbb/awesome-gbb/tree/main/skills/citadel-hub-deploy))
- A **Foundry project spoke** onboarded to the hub via [`citadel-spoke-onboarding`](https://github.com/aiappsgbb/awesome-gbb/tree/main/skills/citadel-spoke-onboarding) with `llm:read` access contract
- Resource group(s) the SRE Agent should monitor (typically the Citadel hub RG + your workload RGs)

## Quick Start

```bash
# from a clone of microsoft/sre-agent, with this recipe copied into recipes/
cd sre-agent/sreagent-templates

./bin/new-agent.sh --recipe citadel-routed --non-interactive \
  --set agentName=sre-citadel-pilot \
  --set resourceGroup=rg-sre-pilot \
  --set location=swedencentral \
  --set targetRGs=rg-citadel-hub,rg-pilot-prod \
  --set citadelGatewayUrl=https://apim-citadel.contoso.net \
  --set citadelProductKey=<sub-key-or-empty-for-JWT> \
  -o sre-citadel-pilot/

./bin/deploy.sh sre-citadel-pilot/
```

After deploy, the agent has:

- 1 connector to Application Insights (the Citadel hub's AppIn)
- 1 connector to Log Analytics (the Citadel hub's LAW)
- 1 skill: `citadel-gateway-debug` — investigates 4xx/5xx responses from the gateway
- 1 subagent: `apim-403-investigator` — invoked via `/agent` for JWT/audience/scope issues
- 1 common prompt: `citadel-safety-rules` — forbids reading APIM subscription keys and forbids modifying named-values

## Parameters

| Param | Required | Example |
|---|---|---|
| `agentName` | yes | `sre-citadel-pilot` |
| `resourceGroup` | yes | `rg-sre-pilot` |
| `location` | yes | `swedencentral` |
| `targetRGs` | yes | `rg-citadel-hub,rg-pilot-prod` |
| `citadelGatewayUrl` | yes | `https://apim-citadel.contoso.net` |
| `citadelProductKey` | no | `<sub-key>` (leave empty when using JWT-only via Access Contract) |
| `existingAgentAppInsightsId` | no | Set if the Citadel hub's AppIn should be reused for SRE Agent telemetry |

## Post-deploy

1. The agent prints a `webhookBridgeTriggerUrl` — save to Citadel KV as `sre-incident-webhook` for use by other skills.
2. Verify the gateway routing: ask the agent "Test the LLM connection." It should call the gateway and confirm a 200.
3. If the first turn returns 401, the Foundry MI lacks the `llm:read` Access Contract — re-run `citadel-spoke-onboarding`.

## Verify

```bash
./bin/verify-agent.sh "$SUBSCRIPTION_ID" rg-sre-pilot sre-citadel-pilot \
  --expected sre-citadel-pilot/
```

Should report all 22 checks pass against `expected-config.json`.

## Cross-skill notes

- This recipe **does not** install GBB plugins. Pair with `gbb-citadel` and `gbb-foundry` from `references/plugins/` for richer expert subagents.
- For the `defaultModel.provider: MicrosoftFoundry` (Anthropic on Foundry) path, change `defaultModelProvider` in `agent.json` to `Anthropic` and update the Foundry connection accordingly.
