# `foundry-mcp-aca` — deep audit trail

| Field | Value |
|-------|-------|
| **Auditor** | Phase 4 PR 6/6 (`unsafecode/foundry-mcp-aca-audit`) |
| **Date** | 2026-05-30 |
| **Bug-class scan** | C1-C21 per Appendix A of `docs/superpowers/specs/2026-05-30-deep-audit-and-testing-rethink-design.md` (L381-422) |
| **Skill version under audit** | `1.1.0` (HEAD of `main` at `d9d5541`, post-PR #204 merge) |
| **Audit surface** | `skills/foundry-mcp-aca/SKILL.md` (880 lines) + `references/python/server.py` + `references/bicep/mcp-aca.bicep` + `references/postdeploy_cosmos_firewall_egress.py` + `references/upstream-pin.md` |
| **Companion fixture** | `skills/foundry-mcp-aca/test-fixture/consumer_prompt.md` (new — Phase 4 PR 6/6 artifact) |
| **Precedent format** | `docs/audit/foundry-observability-audit-trail.md` (PR #204 — shorter audit-only precedent) |
| **PR #204 deferral precedent applied** | YES — all fix-in-PR-candidate HITs deferred to focused follow-up PRs; audit-only commit, no `metadata.version` bump |

---

## Executive summary

The `foundry-mcp-aca` skill teaches **producer-side** deployment of Model Context Protocol servers on Azure Container Apps (Cosmos DB MCPToolKit, Azure Functions, or custom Python FastMCP). It is one of the more substantial skills in the catalog (880 lines of SKILL.md, four canonical reference files spanning Python, Bicep, and an idempotent post-deploy script).

The C1-C21 walk produced **two HITs**, both classified as **HIGH-severity C15 (Reference ↔ SKILL.md drift)**, and both **deferred** from this PR per the PR #204 precedent (audit-only scope, narrow brief):

1. **HIT-1 — Canonical reference composition is broken.** `references/bicep/mcp-aca.bicep` configures **liveness + startup probes targeting `/health`** on port 8080 (L86, L92). `references/python/server.py` is the documented canonical server body (SKILL.md L387 cross-link) and **does not expose a `/health` route** — FastMCP's `streamable-http` transport mounts only `/mcp/`. A consumer who copies both files verbatim deploys a container that the startup probe will mark unhealthy until `failureThreshold: 30` × `periodSeconds: 3` = 90 s elapses, then crash-loops indefinitely. The Bicep header comment (L13) and SKILL.md L86 + L387 both promise the `/health` endpoint as a contract, so the defect is in the canonical Python reference, not the Bicep.

2. **HIT-2 — Upstream pin contradicts its own KI-001 and SKILL.md guidance.** `references/upstream-pin.md` YAML front-matter installs `fastmcp~=3.3.1` (L75) under `validation.script`, while:
   - the **same pin file's `known_issues[0]`** (L59-64) declares `KI-001 open — Keep FastMCP pinned below 3.0.0 until the streamable-http mount-path change is explicitly revalidated`
   - **SKILL.md L135, L142, L159, L163, L218, L481** all mandate `fastmcp>=2.0.0,<3.0.0` with an explicit "🛑 DO NOT bump fastmcp major version without re-running the demo scenarios" callout
   - the pin file's README table (L105) records `fastmcp 2.14.7` as the human-facing pinned version

   A freshness-loop refresh PR appears to have bumped the YAML validation cap to `~=3.3.1` without closing KI-001 or reconciling SKILL.md prose. Either KI-001 needs closing (and SKILL.md mass-rewriting to allow 3.x) or the pin script needs reverting to `~=2.14.7`. Same root cause as HIT-1 (reference drift), different file pair.

Beyond those two HITs the catalog walk surfaced **zero new defects**. C1-C8 (the credential / endpoint / SDK / API / RBAC / env-var / GUID / deprecation cluster that catches most wrapper-skill regressions) are all clean. C16 / C18 / C19 / C20 / C21 are non-applicable. C9-C14 are clean modulo the noted drifts.

**Decision:** ZERO fix-in-PR HITs in this PR per the coordinator brief's narrow two-artifact scope (audit + new fixture only). The two HITs above are logged under § "Open items (deferred)" with reproduction steps and recommended PR shape for follow-up. No `skills/foundry-mcp-aca/SKILL.md` `metadata.version` bump. No `[skill-rewrite]` tag in commit messages. Pure audit-only + new-fixture commit, mirroring PR #204's deferral of C15 LOW.

---

## Findings (C1-C21)

> **Scoring convention** (matches `foundry-observability-audit-trail.md` § "Findings"):
> - **HIT** — defect present; severity {LOW, MEDIUM, HIGH}; classify as fix-in-PR or deferred.
> - **none observed** — bug class is applicable to the skill surface but no defect was found.
> - **N/A** — bug class is not applicable (e.g., skill doesn't expose the relevant surface).

### 1. C1 — Credential type bugs (sync cred in async client; MID-I class)

**Status: none observed.**

The skill's Python references use `azure.identity` (sync `DefaultAzureCredential`) only in the `postdeploy_cosmos_firewall_egress.py` script, which is a sync-only `subprocess`-driven helper — no async context. The canonical `server.py` does not instantiate any Azure credential (it only declares the FastMCP server skeleton; tool implementations call backend APIs left to the consumer). SKILL.md L424-453 demonstrates async Cosmos client usage in the Cosmos MCP example with `azure.identity.aio.DefaultAzureCredential` paired with `azure.cosmos.aio.CosmosClient` — the async/async pair is correct. No MID-I instance.

### 2. C2 — Endpoint URL bugs (project vs account; MID-G class)

**Status: N/A.**

The skill does not invoke the Foundry control plane. It targets ACA management (Bicep + `az containerapp` + `azd up`) and the deployed MCP server's HTTPS endpoint (which is `https://<aca-name>.<env-fqdn>` and entirely consumer-side). There is no AI Services account/project endpoint surface in scope.

### 3. C3 — Wrong model names

**Status: N/A.**

The skill does not deploy or reference Azure OpenAI models. The MCP server is the deployment target; the agent that calls the MCP is out of scope (covered by `foundry-hosted-agents` and `foundry-toolbox`).

### 4. C4 — Wrong RBAC role names

**Status: none observed.**

SKILL.md L259-274 specifies `AcrPull` as the role required on the UAMI for image pulls — correct GA role name. L324-336 specifies `Cosmos DB Built-in Data Contributor` for the Cosmos MCP variant — correct role name (it is the built-in data-plane RBAC role, distinct from the legacy `Cosmos DB Account Reader`). The canonical Bicep does not embed role assignments (consumer responsibility); SKILL.md cross-links to `azd-patterns` for the canonical RBAC module shape, which is correct cross-skill delegation.

### 5. C5 — Wrong API scopes

**Status: N/A.**

The skill does not document an OBO / on-behalf-of flow, JWT validation, or API-scope assignment. The MCP wire protocol uses HTTP transport headers (`Authorization: Bearer …`) at the consumer's discretion; the skill correctly defers JWT/OBO concerns to `citadel-spoke-onboarding` (SKILL.md L831).

### 6. C6 — Wrong env-var names

**Status: none observed.**

Documented env vars are stable Azure surface:
- `PORT` (ACA injects; correctly read by `server.py` L13/L62)
- `AZURE_RESOURCE_GROUP`, `AZURE_SUBSCRIPTION_ID`, `AZURE_COSMOS_ACCOUNT_NAME` (`azd env` standard) — correctly consumed by `postdeploy_cosmos_firewall_egress.py` L166-168
- `COSMOS_MCP_ACA_NAME` (script-local override, documented L35-37)

No name drift against current `azd` env or Azure CLI defaults.

### 7. C7 — Hardcoded GUIDs

**Status: none observed.**

Grep against `skills/foundry-mcp-aca/**` for `^[0-9a-f]{8}-[0-9a-f]{4}-` returns zero hits. All resource identifiers are parameterized via Bicep `param` declarations or env-var lookups.

### 8. C8 — Deprecated SDK calls

**Status: none observed.**

The skill correctly flags two deprecation traps:
- Bicep `ingress.transport: 'auto'` is **deprecated** (SKILL.md L387 + Bicep L57-60 inline comment); canonical Bicep uses explicit `'http'` — correct.
- FastMCP 1.x `MCP.run()` bare form (stdio default) is **deprecated** for cloud use (SKILL.md L580-593 critical-gotchas + server.py L57-62 inline comment); canonical Python uses `transport="streamable-http"` — correct.

Both deprecations are documented as anti-patterns AND the canonical references demonstrate the correct alternative.

### 9. C9 — Bicep module drift

**Status: none observed for in-skill drift.**

The canonical `references/bicep/mcp-aca.bicep` uses `Microsoft.App/containerApps@2024-03-01`, which is the current GA API version. UAMI wiring shape matches `azd-patterns` library (`UserAssigned` + `userAssignedIdentities` dict). External ingress, registry block with identity reference, container resource limits, and probes are all conformant with the `azd-patterns` SSOT.

> **Cross-skill drift note (NOT a HIT):** SKILL.md L387 says "the canonical ACA module with external ingress on `:8080`, UAMI for ACR pull (A2), `transport: 'http'` (not deprecated `'auto'`), and liveness + startup probes on `/health`" — the prose accurately summarizes the Bicep. The drift introduced by HIT-1 below is on the **Python reference side**, not the Bicep side.

### 10. C10 — Bicep param mismatches

**Status: none observed.**

Bicep parameters (`name`, `location`, `containerAppEnvironmentId`, `image`, `env`, `userAssignedIdentityId`, `acrName`) are all referenced in the body and all six are documented in SKILL.md L387's prose summary or via the `azd-patterns` cross-link. No orphan params, no undeclared references.

### 11. C11 — Cross-skill contradictions

**Status: none observed within the foundry-mcp-aca skill body.**

The skill correctly delegates:
- Hosted agent runtime → `foundry-hosted-agents` (SKILL.md L46-50)
- VNet integration → `foundry-vnet-deploy` (Bicep L18-20)
- RBAC patterns → `azd-patterns` (referenced throughout the deployment chapters)
- JWT / Citadel governance → `citadel-spoke-onboarding` (L831)
- Tool composition in the agent → `foundry-toolbox` (L46-50)

The `consumer scope` boundary (SKILL.md L23-50) is the cleanest demarcation in the catalog — no overlapping claims with `foundry-hosted-agents § MCP Tools`.

### 12. C12 — Container probe misconfigurations

**Status: HIT — see HIT-1 in § Open items.**

The canonical Bicep liveness + startup probes target `/health` on port 8080. SKILL.md L86 documents `/health` as a contract ("Health endpoint at `/health` (separate from MCP protocol)"). The canonical Python `references/python/server.py` does **not** implement a `/health` route — FastMCP's `streamable-http` transport binds only `/mcp/`. A verbatim copy → unhealthy container, crash-loop after `failureThreshold: 30` × `periodSeconds: 3` = 90 s.

This is the **same root defect** as HIT-1 under C15 below — the Bicep + Python reference pair do not compose to a deployable artifact. Logged in detail in § Open items.

### 13. C13 — Wrong region defaults

**Status: N/A.**

The skill does not encode a default region — Bicep `location` param defaults to `resourceGroup().location` (correct passthrough). No hardcoded `Sweden Central` or other region literal in the skill body or references. The only region-specific guidance is the AGENTS.md § 9.7 Pattern 21 note about embedding deployments in Sweden Central requiring `GlobalStandard` SKU, which is consumer-side (model deployment, not MCP).

### 14. C14 — JSON/YAML escaping in agent prompts

**Status: N/A.**

The skill does not author agent prompts — it documents server deployment. The "validate-or-reject" pattern at SKILL.md L760-820 is server-side tool input shape design (Pydantic models) and does not touch prompt-escaping concerns.

### 15. C15 — Reference ↔ SKILL.md drift

**Status: HIT (HIGH × 2) — see HIT-1 + HIT-2 in § Open items.**

Two drift instances surfaced; both deferred per PR #204 precedent.

- **HIT-1 — Bicep ↔ Python composition gap.** Covered by C12 above; full reproduction in § Open items.
- **HIT-2 — Upstream-pin contradicts SKILL.md + own KI-001.** Pin YAML installs `fastmcp~=3.3.1` while SKILL.md mandates `<3.0.0` six times and the pin's own `KI-001` (status `open`) says "Keep FastMCP pinned below 3.0.0". Additional internal drift: pin README table L105 records `fastmcp 2.14.7`, and L108-110 list `azure-identity 1.19.0` / `aiohttp 3.9.0` while the YAML installs `1.25.3` / `3.13.5`.

Full reproduction + recommended fix shape in § Open items.

### 16. C16 — Missing `dependsOn` (RBAC race)

**Status: N/A within this skill's references.**

The canonical `references/bicep/mcp-aca.bicep` is a **single-resource module** (one Container App). RBAC role assignments live in `azd-patterns`'s canonical library (per SKILL.md L259-274 cross-link). There is no in-module `dependsOn` race because there are no sibling resources in this Bicep file. The race lives at the consumer's `main.bicep` level (which composes this module + the RBAC module) — and `azd-patterns` already documents the `dependsOn: [rbac]` pattern as Pattern 7 carry from foundry-hosted-agents.

### 17. C17 — Tool wrapper type mismatches (dict vs Pydantic)

**Status: none observed.**

SKILL.md L760-820 documents the "validate-or-reject" Pydantic-model-driven pattern for commit-style tools. The pattern correctly uses `model_dump()` for serialization, returns structured error dicts (`HTTP 200` with `INSUFFICIENT_EVIDENCE` payload), and never raises. L621-655 demonstrates the `FunctionTool not callable` pitfall (decorated `@mcp.tool` cannot be invoked from Python) with the correct mitigation (extract a plain `_helper()`). The canonical `server.py` L37-54 implements that pattern.

### 18. C18 — Bot/webhook signature bugs

**Status: N/A.**

The skill is not a bot/webhook skill — it produces MCP servers. There is no Slack/Teams/Twilio webhook signature surface in scope.

### 19. C19 — Logging exposure (secrets, PII)

**Status: none observed.**

The canonical `server.py` does not log secrets. The `postdeploy_cosmos_firewall_egress.py` script logs the discovered egress IP at L99 + L133, which is intentional (the IP is needed for the firewall patch and is not a secret — Azure public ACA egress IPs are observable from any peer endpoint). No env-var dumps, no header logging, no PII surface.

### 20. C20 — Async/sync mismatches beyond credentials

**Status: none observed.**

The async surfaces in the skill are consistent:
- `azure.cosmos.aio.CosmosClient` paired with `azure.identity.aio.DefaultAzureCredential` paired with `aiohttp.ClientSession` (SKILL.md L424-453) — all async.
- `fastmcp.FastMCP` with `@mcp.tool() async def …` (server.py L44-54) — async tools throughout.
- `postdeploy_cosmos_firewall_egress.py` uses sync `subprocess.run` + sync polling — internally consistent sync flow.

No `await` on a sync object, no event-loop pitfalls.

### 21. C21 — Outdated package pins (beyond freshness loop)

**Status: HIT (HIGH) — covered by HIT-2 in § Open items.**

The freshness loop refreshed `references/upstream-pin.md` to `fastmcp~=3.3.1` on 2026-05-29 (validated by `copilot-bot` per L92-93), but the human-readable prose / KI / SKILL.md guidance did not follow. This is the freshness loop working as designed for the YAML contract, and **simultaneously** demonstrating the gap the loop cannot close on its own: KI closure + SKILL.md prose updates require human + a focused `[skill-rewrite]` PR. Logged once under HIT-2 in § Open items.

---

## Fixture

A new Copilot CLI test fixture lives at `skills/foundry-mcp-aca/test-fixture/consumer_prompt.md` and is wired into `.github/workflows/skill-test.yml`'s `copilot-cli-matrix` job via the existing change-gated matrix builder (`scripts/build-test-matrix.py`). The `.github/skill-deps.yml` entry was already in place at L61-63 (`foundry-mcp-aca: { depends_on: [foundry-hosted-agents] }`) from an earlier Phase 3 housekeeping commit; **no edit needed and none was made** per the coordinator brief's narrow scope.

**Smoke contract** (Pattern 25 ACA-deploy shape, mirroring the `foundry-hosted-agents` precedent that proved out the soft-PASS teardown):

1. **Step 0 — env + auth inventory** (Pattern 11 + Pattern 17). Prints `…=set` for `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `ACR_LOGIN_SERVER`. Runs `az account show --output table || echo "(az cache not inherited)"` (show-don't-assert per Pattern 17). Forbids `command -v`, `find /`, and `curl -fsSL` install patterns per Pattern 15 (the workflow's `azure/setup-azd` step pre-provisions `azd` to `/usr/local/bin/azd`; the fixture documents this as a pre-granted capability).

2. **Step 1 — explicit `azd auth login`** (Pattern 6). Runs `azd auth login --federated-credential-provider github --client-id "$AZURE_CLIENT_ID" --tenant-id "$AZURE_TENANT_ID"` to make the OIDC exchange visible up-front rather than buried inside `azd up`'s ACR push step.

3. **Step 2 — build the deploy artifact tree.** The agent writes a self-contained `azd` project under a temp directory: `azure.yaml`, `infra/main.bicep` (Container App + ACR repository tag, referencing pre-provisioned `cae-awesome-gbb-ci` + `acrawesomegbbci` + the CI UAMI via `existing`), `src/Dockerfile`, `src/server.py` (a tiny FastMCP server with **explicit `/health` route** — see § Open items HIT-1; the fixture cannot use the canonical `references/python/server.py` verbatim because of the documented composition gap), and `src/requirements.txt`. Service name is suffixed with a short UUID per Pattern 3.

4. **Step 3 — `azd up`.** Hard gate. Bicep deploys the new Container App into the pre-existing CAE, ACR remote build produces the image, the agent waits for the new revision to reach `Running` state. Total budget ~12-18 min under typical conditions.

5. **Step 4 — MCP HTTP roundtrip.** Hard gate. Resolves the deployed ACA FQDN via `az containerapp show -o tsv --query properties.configuration.ingress.fqdn`. Issues **two** JSON-RPC calls over `POST https://<fqdn>/mcp/`:

   ```http
   POST /mcp/ HTTP/1.1
   Content-Type: application/json
   Accept: application/json, text/event-stream

   { "jsonrpc": "2.0", "method": "initialize", "id": 1,
     "params": { "protocolVersion": "2025-06-18",
                 "capabilities": {},
                 "clientInfo": { "name": "ci-smoke", "version": "1.0" } } }
   ```

   Asserts HTTP 200 + JSON-RPC `result.serverInfo.name` present. Then `tools/list`:

   ```http
   POST /mcp/ HTTP/1.1
   …same headers…

   { "jsonrpc": "2.0", "method": "tools/list", "id": 2 }
   ```

   Asserts HTTP 200 + at least one tool in `result.tools[]`. The trailing slash on `/mcp/` is FastMCP 3.x's documented mount path (SKILL.md L580-593 critical-gotchas + L603); the dual `Accept` header is required by the MCP streamable-HTTP spec to allow the server to choose single-response vs streaming.

6. **Step 5 — Marker IMMEDIATELY on hard-gate success** (Pattern 12 + Pattern 25). Before any teardown attempt, the agent invokes the Bash tool to run `printf 'SMOKE_RESULT=PASS\n' > /tmp/foundry-mcp-aca-smoke-result`. This is the load-bearing inversion that Pattern 25 introduced: **the smoke is the contract; cleanup is hygiene**. The hosted-agents fixture chained marker emission after cleanup and false-FAIL'd on OIDC TTL expiry mid-cleanup; the Phase 4 PR for hosted-agents fixed that race by writing the marker before `azd down`. This fixture inherits the same shape.

7. **Step 6 — Teardown best-effort** (Pattern 25). Attempts `azd down --purge --force` with a **5-minute budget**. On success, the run leaves zero orphans. On timeout or error, the agent emits a single `NOTE: teardown stalled at <step>` line to stdout (transcript-only) and returns. The `rg-awesome-gbb-ci` janitor (AGENTS.md § 9.7 P25) sweeps `ci-smoke-mcp-*` ACR repositories and Container Apps older than 7 days. The marker stays `SMOKE_RESULT=PASS`; cleanup failure does NOT downgrade the smoke verdict.

**Marker path:** `/tmp/foundry-mcp-aca-smoke-result`. Workflow evaluator (`.github/workflows/skill-test.yml` L321-330 — the canonical Pattern 12 grader) reads the file and `cmp -s` against `printf 'SMOKE_RESULT=PASS\n'` for byte-exact match.

**Why this fixture protects the catalog:**

- Honest end-to-end test of the deployment + wire-protocol contract: `azd up` succeeds + MCP HTTP `initialize` + `tools/list` both return 200 with conformant JSON-RPC bodies. The MCP HTTP roundtrip is the value contract this skill exists to enable; everything else is plumbing.
- Tests against pre-provisioned `cae-awesome-gbb-ci` + `acrawesomegbbci` (pre-granted `AcrPush` on the CI UAMI; Pattern 7) — no RBAC propagation race in the critical path.
- Pattern 25 marker-first / cleanup-second shape inherits the hosted-agents fixture's hard-won OIDC TTL resilience.
- Self-contained goal prompt (Pattern 20) — no `Use the foundry-mcp-aca skill` directive; the agent does the work from general training + the SKILL.md content the workflow's audit step pastes into the prompt.
- Inline FastMCP server in the fixture (with explicit `/health` route) documents the HIT-1 workaround in-place for future readers, so the fixture survives until HIT-1's canonical-reference fix lands.

---

## CI matrix runs (stability)

Per AGENTS.md § 9.7 Pattern 1 (≥ 45 s spacing between empty-commit stability runs). All three runs must be GREEN before reporting back to the coordinator (project session `256a94b2-ddae-4bf2-8dfd-5c3865781662`); `auto-merge-copilot.yml` does NOT auto-merge human-authored PRs, so the coordinator runs the admin squash-merge once 3-of-3 are green.

| Run | SHA | Trigger | Status | Notes |
|-----|-----|---------|--------|-------|
| #1 | (first push after PR open) | `pull_request synchronize` | TBD | Initial run — establishes per-leg wall-clock baseline (ACA deploy is heaviest in catalog at ~15-25 min) |
| #2 | `git commit --allow-empty -m "stability run #2 for foundry-mcp-aca"` | `pull_request synchronize` | TBD | Pattern 1 spacing ≥ 45 s after #1 transitions to in-progress |
| #3 | `git commit --allow-empty -m "stability run #3 for foundry-mcp-aca"` | `pull_request synchronize` | TBD | Pattern 1 spacing ≥ 45 s after #2 |

This section will be filled in via PR-description amendments after each run resolves. If any leg flaps, the audit's "Open items" section gets an additional entry capturing the failure mode + root cause + fix.

---

## Open items (deferred)

> **Decision protocol** (from PR #204 + the coordinator brief): HITs are **fix-in-PR** only when they (a) involve a single skill, (b) are PATCH-scope, AND (c) fall within the PR's explicit scope as set by the coordinator brief. The Phase 4 PR 6/6 brief defines scope as **two new files only** (this audit + the fixture); reference-file edits, KI closures, and SKILL.md prose rewrites are out-of-scope. HITs that meet (a) + (b) but not (c) are deferred to focused follow-up PRs with explicit reviewer attention.

### HIT-1 — Canonical Bicep ↔ Python reference composition gap (HIGH; deferred)

**Bug class:** C12 (container probe misconfiguration) + C15 (reference ↔ SKILL.md drift).
**Severity:** HIGH — every consumer who copies both canonical references verbatim deploys an unhealthy container that crash-loops after 90 s.
**Surface:** `skills/foundry-mcp-aca/references/python/server.py` vs `skills/foundry-mcp-aca/references/bicep/mcp-aca.bicep`.

**Reproduction.**

1. Follow SKILL.md L380-410 verbatim: copy `references/bicep/mcp-aca.bicep` into your `infra/`.
2. Follow SKILL.md L455-510 verbatim: copy `references/python/server.py` into your `src/`.
3. `azd up`. The Container App provisions, the image pulls, the container starts on port 8080, `MCP.run(transport="streamable-http")` binds `/mcp/` correctly.
4. The startup probe `httpGet { path: '/health', port: 8080 }` returns HTTP 404 (FastMCP `streamable-http` mount has no `/health` route — only `/mcp/`).
5. With `failureThreshold: 30` + `periodSeconds: 3`, the startup probe fails for 90 s, then ACA marks the revision Unhealthy and starts replacing it. The new replica fails the same probe. Crash-loop forever; revision never reaches `Running` state.

**Evidence.**
- `skills/foundry-mcp-aca/references/bicep/mcp-aca.bicep` L86: `httpGet: { path: '/health', port: 8080 }` (liveness).
- `skills/foundry-mcp-aca/references/bicep/mcp-aca.bicep` L92: `httpGet: { path: '/health', port: 8080 }` (startup).
- `skills/foundry-mcp-aca/references/bicep/mcp-aca.bicep` L13-14 inline comment: "Liveness + startup probes on /health — without these, cold-start tool calls 502 until the first scrape" — **the Bicep header asserts `/health` as a contract.**
- `skills/foundry-mcp-aca/SKILL.md` L86: "Health endpoint at `/health` (separate from MCP protocol)" — **SKILL.md asserts `/health` as a contract.**
- `skills/foundry-mcp-aca/SKILL.md` L387: "liveness + startup probes on `/health` (without them, cold-start tool calls 502 until the first scrape)" — **second SKILL.md assertion.**
- `skills/foundry-mcp-aca/references/python/server.py` L29-62: full file body, **no `/health` route registered**, no `app.get("/health", …)` or equivalent. FastMCP's `streamable-http` transport mounts only the MCP protocol endpoint.

**Recommended fix shape (follow-up PR).**

Add a `/health` route to `references/python/server.py`. FastMCP 2.x exposes the underlying Starlette app via `mcp.streamable_http_app()` or `mcp.app` (the exact accessor changed between minor versions — needs revalidation against `fastmcp 2.14.7` and `3.3.1`). The simplest portable shape:

```python
# After `mcp = FastMCP("my-tools")`:

from starlette.responses import PlainTextResponse
from starlette.routing import Route

async def health(request):
    return PlainTextResponse("ok", status_code=200)

# FastMCP 2.x:
mcp.custom_route("/health", methods=["GET"])(health)
# or, fallback:
# mcp.streamable_http_app().routes.append(Route("/health", health, methods=["GET"]))
```

The shape needs validation against the actual FastMCP version SKILL.md mandates (`<3.0.0`, currently 2.14.7) before landing. PR shape: single commit touching only `references/python/server.py` + a SKILL.md PATCH bump (`1.1.0` → `1.1.1`) + a one-paragraph SKILL.md callout next to L86 explaining "the canonical `server.py` registers `/health` via `mcp.custom_route(...)`."

**Why deferred from this PR.** The coordinator brief explicitly limits scope to two new files (audit + fixture). Editing `references/python/server.py` and bumping `metadata.version` would expand scope beyond the brief, and the PR #204 precedent (audit-only commit, no SKILL.md edit, deferred C15 LOW HIT) governs Phase 4's discipline. The fix is small but deserves explicit reviewer attention — both `fastmcp 2.14.7` and `fastmcp 3.3.1` need spot-validation that `mcp.custom_route` is the right hook (it changed in the 2.x → 3.x transition that drove KI-001).

**Risk of deferral.** Every consumer following SKILL.md verbatim until the follow-up PR merges hits this defect. Mitigation: the new fixture in this PR uses an inline FastMCP server with `/health` registered explicitly — so the smoke proves the deployment path works once the route exists, and future readers can see the workaround in the fixture body. The fixture's inline server doubles as a working example for affected consumers.

### HIT-2 — Upstream pin contradicts SKILL.md + own KI-001 (HIGH; deferred)

**Bug class:** C15 (reference ↔ SKILL.md drift) + C21 (outdated package pins beyond what freshness loop catches).
**Severity:** HIGH — the pin's validation.script installs a fastmcp version that SKILL.md and the pin's own KI explicitly forbid.
**Surface:** `skills/foundry-mcp-aca/references/upstream-pin.md` vs `skills/foundry-mcp-aca/SKILL.md`.

**Reproduction.**

1. Run the pin's `validation.script` (front-matter L66-90): `pip install "fastmcp~=3.3.1"` succeeds, prints `ok foundry-mcp-aca imports`. Pin is satisfied per the freshness loop.
2. Read `skills/foundry-mcp-aca/references/upstream-pin.md` L59-64: `KI-001 status: open — Keep FastMCP pinned below 3.0.0 until the streamable-http mount-path change is explicitly revalidated`.
3. Read `skills/foundry-mcp-aca/SKILL.md` L135, L142, L159, L163, L218, L481: six independent mandates of `fastmcp>=2.0.0,<3.0.0` with a 🛑 callout at L163 saying "DO NOT bump fastmcp major version without re-running the demo scenarios".
4. Notice the pin's own README table at L105 records `fastmcp 2.14.7` as the human-facing pinned version — the YAML and the README table disagree.
5. Additional drift in the same pin file: README L108-110 lists `azure-identity 1.19.0` and `aiohttp 3.9.0`, while YAML L37-47 installs `azure-identity~=1.25.3` and `aiohttp~=3.13.5`. The README table is stale.

**Evidence.**
- `skills/foundry-mcp-aca/references/upstream-pin.md` L13-17: YAML installs `fastmcp~=3.3.1`.
- `skills/foundry-mcp-aca/references/upstream-pin.md` L59-64: open `KI-001` says <3.0.0.
- `skills/foundry-mcp-aca/references/upstream-pin.md` L105: README says `fastmcp 2.14.7`.
- `skills/foundry-mcp-aca/SKILL.md` L135: `fastmcp>=2.0.0,<3.0.0  # MUST upper-bound`.
- `skills/foundry-mcp-aca/SKILL.md` L163: "🛑 DO NOT bump fastmcp major version without re-running the demo scenarios".

**Recommended fix shape (follow-up PR).** Pick ONE of two paths:

**Path A — Close KI-001, validate 3.x, mass-update SKILL.md.** If 3.3.1 has been validated against the streamable-http mount path:
- Mark `KI-001 status: closed_upstream_fixed` with a citation to the validation run.
- Mass-update SKILL.md to `fastmcp>=3.0.0,<4.0.0` across all six mandate sites.
- Update the README table at L105 to `fastmcp 3.3.1`.
- Update README table L108-110 to `azure-identity 1.25.3` / `aiohttp 3.13.5`.
- Bump SKILL.md `metadata.version` MINOR (3.x is a breaking change for any consumer reading the pin guidance).
- Tag the commit `[skill-rewrite]` per AGENTS.md § 4 mass-edit invariants.

**Path B — Revert the pin script to 2.x, leave KI-001 open.** If 3.3.1 has NOT been validated:
- Revert the validation.script `pip install` to `fastmcp~=2.14.7`.
- Reconcile the README table at L105 (it already says 2.14.7 — no change needed).
- Reconcile README L108-110 to match YAML (azure-identity / aiohttp drift is independent).
- Bump SKILL.md `metadata.version` PATCH if any SKILL.md prose is touched, otherwise no bump.

The path choice is a freshness-loop / customer-validation question that requires running the SKILL.md demo scenarios against 3.3.1 — the audit can flag the drift but cannot resolve it without that validation work.

**Why deferred from this PR.** Same reasoning as HIT-1 — coordinator brief restricts scope to the two new audit + fixture files. A pin rewrite either way is a focused single-purpose PR that benefits from explicit reviewer attention on the version semantics.

**Risk of deferral.** The freshness loop classifies the pin as satisfied (validation.script passes), so no automated nag will surface the contradiction. A consumer who reads `references/upstream-pin.md` L13-17 instead of SKILL.md L135 will pin `fastmcp~=3.3.1` and hit the streamable-http mount-path break KI-001 warns about. Mitigation: the audit captures the contradiction with full reproduction so the follow-up PR has a complete diff target.

---

## Sign-off

| Phase | Outcome |
|-------|---------|
| C1-C21 walk | Complete |
| Fix-in-PR HITs | **0** — both HITs deferred per PR #204 precedent and the coordinator brief's narrow two-artifact scope |
| `skills/foundry-mcp-aca/SKILL.md` `metadata.version` bump | **None** — audit-only + new-fixture commit, no SKILL.md edit |
| `[skill-rewrite]` commit tag | **Not used** — required only for SKILL.md body rewrites; none in this PR |
| Open items deferred | 2 (both HIGH-severity, both single-skill PATCH-scope, both warrant focused follow-up PRs) |
| Fixture wired into `skill-test.yml` matrix | Yes — via existing `.github/skill-deps.yml` L61-63 + `scripts/build-test-matrix.py` change-gating |
| Stability runs | TBD (3 required, ≥ 45 s apart, all GREEN before reporting to coordinator) |
| Coordinator handoff target | project session `256a94b2-ddae-4bf2-8dfd-5c3865781662` |
