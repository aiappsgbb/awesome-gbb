---
name: apim_throttle_expert
description: Diagnose 429 responses from the AI Citadel APIM gateway — identify which rate-limit policy tripped (per-product quota, per-named-value rate-limit-by-key, or backend pool TPM exhaustion).
---

# apim_throttle_expert

## When to use

The SRE Agent should invoke this skill when:

- A user reports a 429 from the Citadel gateway
- A scheduled task flags a spike in 429 responses
- Backend pool TPM utilization approaches its limit

## Investigation flow

1. **Identify the failing operation** — ask the user for the path
   (`/llm/v1/chat/completions`, `/doc/analyze`, etc.) and the time window.

2. **Pull APIM diagnostics** from Log Analytics:
   ```kql
   ApiManagementGatewayLogs
   | where TimeGenerated > ago(2h)
   | where ResponseCode == 429
   | summarize count() by OperationId, ClientIpAddress, ProductId, bin(TimeGenerated, 5m)
   | order by TimeGenerated desc
   ```

3. **Classify the 429** by inspecting the response headers in the same log:

   | Header present | Cause | Action |
   |---|---|---|
   | `Retry-After: <secs>` + `x-throttling-source: apim-product-quota` | Per-product monthly quota exhausted | Check product config; consider raising or moving caller to a different product |
   | `Retry-After: <secs>` + `x-throttling-source: rate-limit-by-key` | Per-key rate limit (typically per-spoke MI) | Check rate-limit policy + named value |
   | `Retry-After: <secs>` + `x-aoai-throttle: true` | Backend AOAI TPM exhaustion (not APIM) | Scale up AOAI deployment or move to PTU |
   | No `Retry-After` | Bug in policy — escalate | Read the operation's policy XML |

4. **For backend exhaustion**, check the BackendPool config:
   ```bash
   az apim api operation policy list ...
   ```

5. **Output** the classification, the specific policy / quota that triggered, the per-product utilization, and a recommended action.

## Tools

This skill uses:
- `RunAzCliReadCommands`
- `QueryLogAnalyticsByWorkspaceId`

## Safety

- Never modify APIM policy, named values, or product subscriptions
- Never read APIM subscription key contents
- All actions must be reviewed by a human
