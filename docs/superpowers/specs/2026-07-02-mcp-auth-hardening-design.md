# Design — Hardened authentication for MCP servers on ACA (`foundry-mcp-aca`)

- **Date:** 2026-07-02
- **Status:** Approved (design phase)
- **Target skill:** `skills/foundry-mcp-aca/` (extend in place; v1.1.0 → v1.2.0)
- **Inspiration:** Microsoft blog "Only 8.5% of MCP Servers Use OAuth — Here's
  How to Host One Securely on App Service" (App Service framing) — re-grounded
  on the **official ACA** guidance so the skill stays App-Service-free.

---

## 1 · Context & motivation

`foundry-mcp-aca` is the catalog's PRODUCER-side skill for hosting MCP servers
on Azure Container Apps. Its current Authentication section (SKILL.md ~552–574)
is a thin three-row table (no-auth / API-key / managed-identity) with no threat
model, no spec-compliant OAuth story, and no hardening guidance. Meanwhile the
industry baseline is dismal — an external survey cited by the blog found only
**8.5% of MCP servers use OAuth**. A remotely-hosted MCP server with no identity
perimeter is an unauthenticated remote-code-execution surface.

The blog's remedy is a 5-layer defense architecture, but it is written for
**Azure App Service** — a service this catalog deliberately avoids. This design
ports that architecture to **ACA built-in authentication ("Easy Auth for
Container Apps")**, which delivers the same Entra-validated perimeter and works
with the skill's existing ACA deployment model.

Two facts (verified against Microsoft Learn) shape the design and make it more
accurate than a straight port of the blog:

1. **There is an official ACA-specific doc** —
   [`learn.microsoft.com/azure/container-apps/mcp-authentication`](https://learn.microsoft.com/azure/container-apps/mcp-authentication)
   ("Secure MCP servers on Azure Container Apps"). It documents the exact
   `az containerapp auth` flow and the 401-without-token / 200-with-bearer
   contract. The skill cites first-party ACA docs, not the App Service blog.
2. **PRM (Protected Resource Metadata) is the server's job on ACA.** App
   Service has a *preview* platform feature
   (`WEBSITE_AUTH_PRM_DEFAULT_WITH_SCOPES`) that auto-publishes
   `/.well-known/oauth-protected-resource`. **ACA has no equivalent.** For
   full interactive-OAuth discovery on ACA, the MCP server itself must serve
   PRM (RFC 9728). This is the headline ACA-vs-App-Service distinction the
   skill must state correctly.

## 2 · Goals / non-goals

**Goals**

- Replace the thin auth table with a `## Securing your MCP server` section that
  gives a threat model, the 5 adapted defense layers, and both consumer models.
- Make **ACA built-in auth + `Return401`** the standard/recommended perimeter.
- Cover **both** consumer models: server-to-server (Foundry agent / MI bearer)
  and interactive OAuth clients (VS Code / Claude / Copilot).
- Reconcile the existing "external ingress for Foundry agents" gotcha with the
  new "put auth in front of it" guidance.
- Push all non-trivial code to `references/` (SSOT per AGENTS.md §7).
- Extend the CI fixture to prove the 401/200 contract live on Azure (§2.9).

**Non-goals (YAGNI / scope guards)**

- **No Azure App Service.** Explicitly avoided per user direction.
- **No deep network build-out.** Private endpoints + APIM are a *light* pointer
  cross-referencing `foundry-vnet-deploy`, not a build.
- **No interactive browser sign-in in CI.** The fixture proves the
  server-to-server 401/200 contract only; interactive-OAuth-discovery (PRM) is
  documented but not fixture-tested (CI cannot drive a user browser login).
- **No new skill.** Extend `foundry-mcp-aca` in place.

## 3 · Locked design decisions

| Decision | Choice |
|---|---|
| Where it lands | Extend `foundry-mcp-aca` (not a new skill) |
| Standard auth mechanism | ACA built-in auth (Easy Auth) — **App Service avoided** |
| Consumer models | Both server-to-server AND interactive OAuth |
| Network depth | Light — Easy Auth perimeter + tool defenses + monitoring; APIM/PE as advanced pointer |
| Testing | Fullest — extend CI fixture to prove 401 (no token) / 200 (valid token) live |
| Doc structure | Approach C — threat→defense mapping table + reference-backed layers |

## 4 · Document structure (Approach C)

The thin Authentication table is replaced by one new section placed before the
Gotchas table:

```
## Securing your MCP server
  (intro: the 8.5% hook; "the perimeter is yours"; ACA built-in auth is the
   standard mechanism; App Service explicitly NOT used)
  ### Threat model → defense mapping          ← centerpiece table
  ### Layer 1 — Identity perimeter: ACA built-in auth + Return401
  ### Layer 2 — Managed identity; never forward the caller's token
  ### Layer 3 — Secret hygiene & tool-input defense
  ### Layer 4 — Network hardening (light; advanced pointer → foundry-vnet-deploy)
  ### Layer 5 — Audit & monitoring (→ foundry-observability)
  ### Connecting clients
        - server-to-server (Foundry agent / MI bearer)
        - interactive OAuth clients (VS Code/Claude/Copilot)
```

**Ripple edits:**

- The old no-auth / API-key / managed-identity table folds into Layer 1 as
  "options," with the hardened default (built-in auth) called out.
- The Gotchas ingress row (SKILL.md line 591) is rewritten to reconcile
  external ingress with Easy Auth (see §6).
- Failure Modes gains 401-related rows (missing/invalid token, wrong audience).

Estimated SKILL.md growth: ~150–180 lines. Heavy code lives in references.

## 5 · Threat → defense mapping (centerpiece table)

| Threat | Mitigating layer | Where the code lives |
|---|---|---|
| Unauthenticated tool invocation | L1 ACA built-in auth + `Return401` | `mcp-aca-auth.bicep` / `az containerapp auth` |
| Confused-deputy / token forwarding | L2 MI + OBO; never forward caller token | `secure_server.py` |
| Over-broad permissions → lateral movement | L2 least-privilege single role assignment | `mcp-aca-auth.bicep` |
| Credential exfiltration via tools | L3 return secret *metadata*, not values; KV refs | `secure_server.py` |
| Path traversal / injection in tool args | L3 input allow-listing (reject `..` `/` `\` `;` `\|` `$(` backtick) | `secure_server.py` (`safe_lookup`) |
| Undetected abuse (invocation spikes) | L5 OTel audit events + scheduled-query alert | `secure_server.py` + `foundry-observability` |

## 6 · The five layers (content, scaled to scope)

**Layer 1 — Identity perimeter (fullest).** The exact official flow: register
an Entra app exposing `api://<appId>` → `az containerapp auth microsoft update`
(clientId + tenant + issuer `https://login.microsoftonline.com/<tenant>/v2.0`)
→ `az containerapp auth update --unauthenticated-client-action Return401`. ACA
validates the JWT **before** it reaches the app and injects the
`X-MS-CLIENT-PRINCIPAL` header (clients cannot forge identity). IaC via a Bicep
`authConfig` child resource. Caveat: Entra has **no Dynamic Client
Registration** — clients must be pre-authorized (ship a known client id).

**Layer 2 — Managed identity (fullest).** `DefaultAzureCredential` resolves
`az login` locally and MI in-cloud. One least-privilege role assignment
(example: `Key Vault Secrets User`). **The rule:** the caller's token authorizes
access to **your** server only — never forward it downstream. Use MI or the
On-Behalf-Of (OBO) flow for the next hop.

**Layer 3 — Secret & input hygiene (medium).** Tools return secret **metadata**
(name/version), never values; secrets flow via Key Vault references
(`@Microsoft.KeyVault(SecretUri=...)`). Tool inputs are allow-listed;
`safe_lookup` rejects traversal/injection characters.

**Layer 4 — Network hardening (light — pointer only).** One paragraph: private
endpoints + APIM front door (`validate-jwt`, `rate-limit-by-key`) are
defense-in-depth → cross-ref `foundry-vnet-deploy`. Includes the ingress
reconciliation below.

**Layer 5 — Audit & monitoring (medium).** Azure Monitor OpenTelemetry
auto-instruments FastAPI; emit an `audit_event` custom event per tool call; a
scheduled-query alert fires on tool-invocation spikes → cross-ref
`foundry-observability`.

**Ingress reconciliation (rewrites the Gotchas row at line 591).** Foundry
hosted agents run in Foundry's infrastructure (not your VNET), so they require
`--ingress external`. **External ingress ≠ unauthenticated** — Easy Auth +
`Return401` makes external ingress safe because every call needs a valid token.
For true network isolation, VNET-inject via `foundry-vnet-deploy`.

## 7 · Consumer models

| Client model | How it authenticates | Status on ACA |
|---|---|---|
| **Server-to-server** (Foundry agent / any service) | Presents an Entra bearer token for `api://<appId>` via its MI | Platform-native; **fixture proves this** |
| **Interactive — manual bearer** (VS Code/Claude/Copilot) | Token retrieved into `.vscode/mcp.json` (`az account get-access-token --resource api://<appId>`) | Official ACA doc path; simplest |
| **Interactive — full OAuth discovery** (advanced) | Server publishes PRM (RFC 9728) at `/.well-known/oauth-protected-resource`; client follows `WWW-Authenticate` → user sign-in | **Server's responsibility on ACA** (no platform PRM); ref FastMCP auth provider + MCP authorization spec |

The interactive-discovery path is documented as "advanced" and points at
FastMCP's auth provider + the MCP authorization spec
(`modelcontextprotocol.io/specification/.../basic/authorization`). It is not
fixture-tested (requires browser user sign-in).

## 8 · Reference files (SSOT per AGENTS.md §7)

| File | Status | Contents |
|---|---|---|
| `references/python/secure_server.py` | **NEW** | Complete hardened FastMCP server: `whoami` (reads `X-MS-CLIENT-PRINCIPAL`), `safe_lookup` (traversal/injection rejection), secret-*metadata* tool (DefaultAzureCredential + Key Vault), `audit_event` OTel emission. Kept separate so the minimal `server.py` stays minimal. Header cites its SKILL.md section (validator-enforced). Respects the `_helper()` pattern (no tool calls another tool). |
| `references/bicep/mcp-aca-auth.bicep` | **NEW** | `authConfig` child resource (Entra provider, `allowedAudiences: [api://<clientId>]`, `unauthenticatedClientAction: Return401`) + least-privilege role assignment. Documented as an add-on to canonical `mcp-aca.bicep`. |
| `references/mcp.json` | **NEW** | Interactive-client config snippet (manual-bearer + discovery variants). |
| `references/upstream-pin.md` | **EDIT** | Add bounded pins for any new pip deps introduced by `secure_server.py` (`azure-monitor-opentelemetry`, `azure-keyvault-secrets`, `azure-identity`); bump `last_validated`. |

## 9 · CI fixture — live 401/200 proof

**Fixture extension** (after the existing Step 5 unauthenticated roundtrip):

1. Enable ACA built-in auth on the deployed app (via `mcp-aca-auth.bicep` or
   `az containerapp auth` post-provision) with `--unauthenticated-client-action
   Return401` and `allowedAudiences: [api://<clientId>]`.
2. Unauthenticated call to `/mcp/` → **assert HTTP 401**.
3. `az account get-access-token --resource api://<clientId>` → authenticated
   call with `Authorization: Bearer <token>` → **assert HTTP 200** + a
   conformant MCP body.
4. Preserve all fixture patterns: Pattern 12 (deterministic marker file
   `/tmp/foundry-mcp-aca-smoke-result`), Pattern 25 (marker-first,
   best-effort teardown ≤5 min), Pattern 11 (env inventory), Pattern 17
   (show-don't-assert on az state), Pattern 27 (never invoke `copilot`
   recursively).

**Infra dependency (must be surfaced as a blocking maintainer task).**
`az ad app create` requires Microsoft Graph app-registration rights that the CI
identity (§9.7) does **not** have today. **Recommended: a standing CI Entra app
registration.**

- A maintainer creates **one** app registration once, exposing
  `api://<clientId>` (App ID URI + a `user_impersonation` scope), and stores
  `MCP_AUTH_APP_CLIENT_ID` as a GitHub secret (tenant id is already available
  as `AZURE_TENANT_ID`). If the ACA provider config requires a client secret
  for the validation flow, also store `MCP_AUTH_APP_CLIENT_SECRET` (note the
  rotation caveat); prefer a validation-only provider config that avoids the
  secret if it yields clean 401/200.
- The fixture references the standing app — **no per-run `az ad app create`**,
  no directory-object teardown, deterministic audience.
- **Fallback if the secret is absent:** the 401 half runs unconditionally
  (deploy auth + `Return401` + unauth call → 401); the 200 half is gated on the
  client-id secret being present. Because §2.9 requires the live 200 proof, the
  standing app registration is a **hard prerequisite** the plan calls out
  explicitly (a maintainer task, blocking full fixture pass).

Whether the provider config needs a client secret (full-login) vs. bearer
**validation only** is an implementation detail to resolve while building the
fixture — pick the simplest config that produces a clean 401/200.

## 10 · Versioning, cross-refs, pin, commit hygiene

- **Version:** `foundry-mcp-aca` v1.1.0 → **v1.2.0** (MINOR — new capability).
- **Cross-refs:** outbound links only *from* `foundry-mcp-aca` →
  `foundry-vnet-deploy` (network), `foundry-observability` (audit/alerts),
  `foundry-hosted-agents` (agent→MCP auth). No edits to those skills, so **no
  `[multi-skill]` tag** — keeps the change contained.
- **upstream-pin.md:** bounded specifiers per AGENTS.md §9.5 for any new pip
  deps; update `last_validated`.
- **Commit tag:** `[skill-rewrite]` (new SKILL.md body).
- **Docs:** rebuild `python3 scripts/build-site.py --out docs/` and commit.
- **Testing tiers:** T0 lint + T1/T2 pin (if deps added) + T3 fixture (the live
  401/200 proof). §2.9 evidence in the PR body.

## 11 · Risks & open questions

| Risk / question | Disposition |
|---|---|
| CI identity lacks Graph app-registration rights | Standing CI app registration (maintainer task); documented as blocking prerequisite (§9). |
| ACA provider config may need a client secret (rotation burden) | Resolve during fixture build; prefer validation-only config; store secret only if required. |
| Interactive-OAuth-discovery (PRM) not CI-testable | Documented, not fixture-tested (needs browser login); explicitly a non-goal for CI. |
| FastMCP version's auth-provider surface for server-side PRM | Verify during implementation; the advanced path is doc-only, so no hard dependency on a specific FastMCP auth API. |
| New pip deps expand the pinned surface | Bounded pins in upstream-pin.md; re-validate imports (T2). |

## 12 · Primary references

- ACA: [Secure MCP servers on Azure Container Apps](https://learn.microsoft.com/azure/container-apps/mcp-authentication)
- ACA: [Troubleshoot MCP servers on Azure Container Apps](https://learn.microsoft.com/azure/container-apps/mcp-troubleshooting)
- ACA: [Authentication and authorization in Azure Container Apps](https://learn.microsoft.com/azure/container-apps/authentication)
- MCP: [Authorization specification](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization)
- RFC 9728 (Protected Resource Metadata), RFC 8414 (Authorization Server Metadata)
- Contrast only: App Service [Configure built-in MCP server authorization (Preview)](https://learn.microsoft.com/azure/app-service/configure-authentication-mcp)
  — cited to explain the platform-PRM difference, NOT used for deployment.
