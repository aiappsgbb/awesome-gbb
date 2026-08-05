# Design Spec: foundry-mcp-aca refresh 1.2.4

**Status:** Implemented (correction-phase artifact)
**Date:** 2026-08-05
**Base version:** 1.2.3
**Target version:** 1.2.4 (PATCH — pin refresh + wording + deployment corrections)

## Scope

PATCH refresh of `foundry-mcp-aca` covering:

1. Pin bumps: azure-mgmt-appcontainers 4.0→5.0 (MAJOR, API preserved),
   azure-cosmos 4.15→4.16.3, aiohttp 3.13.5→3.14.3, explicit mcp 1.29.0 pin
2. Agnostic prose rewrites (remove engagement-specific phrases per AGENTS.md §2.1)
3. Deployment model coherence: fixture aligned to `azd up` (matching SKILL.md guidance)
4. MCP protocol conformance: session-id capture/replay + tools/call in fixture
5. KI-001 expanded to cover coordinated fastmcp 3.x / mcp 2.0 hold

## Compatibility matrix

| Package | Previous | Current | Hold | Rationale |
|---------|----------|---------|------|-----------|
| fastmcp | 2.14.7 | 2.14.7 | <3.0 | KI-001 — mount-path break |
| mcp | (transitive) | 1.29.0 | <2.0 | KI-001 — incompatible with fastmcp 2.x |
| azure-mgmt-appcontainers | 4.0.0 | 5.0.0 | — | MAJOR but JobsOperations.get/begin_create_or_update preserved |
| azure-cosmos | 4.15.0 | 4.16.3 | — | MINOR; async query_items signature unchanged |
| azure-identity | 1.25.3 | 1.25.3 | — | unchanged |
| azure-keyvault-secrets | 4.11.0 | 4.11.0 | — | unchanged |
| aiohttp | 3.13.5 | 3.14.3 | — | MINOR |

## SSOT boundaries

- SKILL.md links to `references/` code; does not duplicate
- `pilotPosture` Bicep param name is canonical from azd-patterns — NOT renamed
- Generic archetype tool names (get_customer_profile, search_orders_filtered) preserved
- Reference data files unchanged

## Deployment model

`azd up` is the single documented deployment path (AGENTS.md §2.6):
- Bicep uses placeholder image; `azd deploy` swaps via `azd-service-name` tag
- `azure.yaml` service binding handles image build + push
- Probes are omitted during first provision to avoid port mismatch with the
  placeholder image (serves port 80 vs real server port 8080). Production
  deployments add probes after the first successful `azd deploy`.

## Live Azure success criteria (T3)

- `azd up` completes successfully against `rg-awesome-gbb-ci`
- MCP `initialize` returns 200 with `serverInfo.name`
- `mcp-session-id` header captured and replayed via Bash array
- `notifications/initialized` returns HTTP 2xx (status-gated, not swallowed)
- `tools/list` returns ≥1 tool
- `tools/call` on `echo` with `"ci-probe"` returns exact `"echoed: ci-probe"` payload
- `isError` is not `true` on the tools/call response
- Deterministic marker file written (Pattern 12)
