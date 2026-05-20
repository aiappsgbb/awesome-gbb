---
name: jwt_403_debug_expert
description: Diagnose 401/403 responses at the AI Citadel APIM gateway — decode JWT claims, verify Access Contract scope grants, and validate Foundry managed-identity token audience.
---

# jwt_403_debug_expert

## When to use

The SRE Agent should invoke this skill when:

- A user reports a 401 or 403 from the Citadel gateway
- A hosted agent's BYOK call returns "Authentication failed with provider … (HTTP 401)" but the underlying provider is the Citadel-routed AOAI
- After running `citadel-spoke-onboarding`, the new spoke can't reach the gateway

## Investigation flow

1. **Get the correlation ID** of the failing request from the user or from
   the application's logs.

2. **Pull the request from APIM diagnostics**:
   ```kql
   ApiManagementGatewayLogs
   | where TimeGenerated > ago(2h)
   | where CorrelationId == "<id>"
   | project TimeGenerated, OperationId, ApiId, ProductId, ResponseCode, BackendStatusReason, LastErrorReason, RequestHeaders, ResponseHeaders
   ```

3. **Decode the JWT** if present (claims only — NEVER the signature):
   - `aud` — must match the gateway URL configured in the Access Contract
   - `iss` — must be `https://login.microsoftonline.com/<tenant>/v2.0`
   - `oid` — the calling principal's object ID
   - `scp` / `roles` — must include the operation scope (e.g. `llm:read`)
   - `exp` — must not be in the past

4. **Match against the Access Contract**:

   | Symptom | Root cause | Fix |
   |---|---|---|
   | `aud` mismatch | Token issued for wrong audience | Re-issue token with correct audience |
   | Missing scope claim | Access Contract didn't grant this scope | Re-run citadel-spoke-onboarding with the needed scope in `gbb_access_contracts` |
   | `exp` in past | Token expired (default ~1h for MI) | Refresh; check caller's token-cache TTL |
   | No `Authorization` header | Caller using product-key path but no key | Set `Ocp-Apim-Subscription-Key` or switch to JWT |
   | 403 with valid JWT | Per-product policy denies | Check `rate-limit-by-key` and product subscription state |

5. **Output**: classification, root cause hypothesis, ONE recommended fix
   and ONE verification step.

## Tools

This skill uses:
- `RunAzCliReadCommands`
- `QueryLogAnalyticsByWorkspaceId`

## Safety

- NEVER display the JWT signature, named-value contents, or any signing material
- Refer to credentials by resource name only (e.g. "Foundry MI on project `aifp-pilot`")
- Read-only investigation; any RBAC change requires human action
