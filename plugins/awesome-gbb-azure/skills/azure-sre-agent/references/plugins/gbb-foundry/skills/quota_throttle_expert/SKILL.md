---
name: quota_throttle_expert
description: Diagnose AOAI deployment TPM exhaustion behind Foundry hosted agents — pull capacity vs utilization, identify burst patterns, recommend scale-up or PTU migration.
---

# quota_throttle_expert

## When to use

- A user reports 429s from a Foundry hosted agent's underlying model
- App Insights shows `Quota exceeded` / `OperationLimitExceeded` for a deployment
- A scheduled task flags TPM utilization > 80% for a deployment

## Investigation flow

1. **Identify the deployment**:
   ```bash
   az cognitiveservices account deployment show \
     --name <foundry-account> --resource-group <rg> \
     --deployment-name <deployment-id> -o json
   ```
   Capture `sku.capacity` (TPM in thousands), `sku.name` (e.g. `Standard`, `GlobalStandard`, `ProvisionedManaged`).

2. **Pull TPM utilization** for the deployment over the failing window
   from App Insights (assumes `foundry-observability` is wired):
   ```kql
   customMetrics
   | where timestamp > ago(2h)
   | where name == "gen_ai.client.token.usage"
   | where customDimensions["gen_ai.system"] == "az.ai.openai"
   | where customDimensions["gen_ai.response.model"] == "<deployment-id>"
   | summarize sum(valueSum) by bin(timestamp, 1m)
   | order by timestamp asc
   ```

3. **Compare against the deployment's capacity**:
   - `sku.capacity` of 100 → 100k TPM
   - Multiply by 60 → 6M tokens/minute capacity
   - Identify peak minutes vs limit

4. **Classify the throttle**:

   | Pattern | Cause | Recommendation |
   |---|---|---|
   | Sustained peak > 80% capacity | Workload outgrew baseline | Increase `sku.capacity` |
   | Spiky peaks 200%+ for 1-2 min, calm baseline | Burst pattern | Consider PTU (Provisioned Managed) for predictable burst headroom |
   | One client dominates | Single noisy neighbor | Add per-spoke rate-limit at Citadel APIM gateway (hand off to `apim_throttle_expert`) |
   | Region cap hit (Standard SKU) | Regional quota | Request quota increase via portal or migrate to `GlobalStandard` |

5. **Cross-check** with Azure Monitor's `TokenTransaction` metric (if the
   user has the `Microsoft.CognitiveServices/accounts` resource in the
   monitored RG).

6. **Output**: peak TPM, capacity, % utilization, classification, ONE recommended action with the exact CLI command (do NOT execute — review mode).

## Tools

- `RunAzCliReadCommands`
- `QueryAppInsightsByAppId`

## Safety

- Never modify the deployment SKU — `sku.capacity` changes are reviewed by the human (cost impact)
- Never read AOAI account keys
