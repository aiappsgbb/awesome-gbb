# MCP Auth Hardening (foundry-mcp-aca) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing `foundry-mcp-aca` skill (v1.1.0 → v1.2.0) with a defense-in-depth "Securing your MCP server" section, two canonical reference files (hardened server + Easy Auth Bicep), a bounded new pin, and a CI fixture that proves the live 401→200 Entra-auth contract.

**Architecture:** All security guidance is anchored on **ACA built-in auth ("Easy Auth for Container Apps")** — the platform validates the caller's Entra JWT before the request reaches the container (`Return401` for anonymous), injects a trusted `X-MS-CLIENT-PRINCIPAL` header, and the server uses its **own managed identity** (never the caller's token) for downstream Azure. Non-trivial code lives in `references/` (SSOT per AGENTS.md §7); SKILL.md carries the threat model, a threat→defense table, five layers, and one-line cross-links.

**Tech Stack:** FastMCP (`streamable-http`), Azure Container Apps + `authConfigs@2025-01-01`, `DefaultAzureCredential`, `azure-keyvault-secrets`, Bicep, `az containerapp auth`, Copilot-CLI CI fixture.

---

## Deviations from the approved spec (plan-time refinements)

Recorded here so the executor understands why the plan differs from `docs/superpowers/specs/2026-07-02-mcp-auth-hardening-design.md`:

1. **`references/mcp.json` is DROPPED.** The interactive-client config is a small `.vscode/mcp.json` fragment (≤12 lines) shown in context — AGENTS.md §7 keeps such fragments inline. This also sidesteps the "JSON can't carry a `§` header" question. The client config now lives inline in the `### Connecting clients` subsection.
2. **Audit layer stays on stdlib `logging`** (structured JSON → stdout → ACA → Log Analytics), cross-linking `foundry-observability` for the OTel upgrade. This avoids pulling in the heavy `azure-monitor-opentelemetry` dependency tree. **The only new pin is `azure-keyvault-secrets`.**
3. **Workflow env passthrough added** (`.github/workflows/skill-test.yml`) so the CI auth proof activates the moment a maintainer creates the `MCP_AUTH_APP_CLIENT_ID` secret — inert (empty → graceful skip) until then.

## Files touched

| File | Action | Responsibility |
|------|--------|----------------|
| `skills/foundry-mcp-aca/SKILL.md` | Modify | Frontmatter version+triggers; replace `## Authentication` with `## Securing your MCP server`; reconcile one Gotchas row; add 401 Failure-Mode rows |
| `skills/foundry-mcp-aca/references/python/secure_server.py` | Create | Canonical hardened FastMCP server (L1 principal, L2 MI, L3 secret-metadata + input allow-list, L5 audit) |
| `skills/foundry-mcp-aca/references/bicep/mcp-aca-auth.bicep` | Create | Canonical `authConfigs@2025-01-01` Easy Auth add-on + least-privilege role assignment |
| `skills/foundry-mcp-aca/references/upstream-pin.md` | Modify | Add `azure-keyvault-secrets ~=4.11.0` in 4 places; bump `last_validated` |
| `skills/foundry-mcp-aca/test-fixture/consumer_prompt.md` | Modify | Insert gated 401/200 auth proof after Step 5; add optional env var to Step 0 inventory |
| `.github/workflows/skill-test.yml` | Modify | Pass `MCP_AUTH_APP_CLIENT_ID` secret into both fixture env blocks |
| `docs/**` | Regenerate | `scripts/build-site.py` static output |

**Ordering constraint:** Task 2 (SKILL.md sections) MUST precede Tasks 3–4, because the reference files' `§ <heading>` header anchors are validated against real SKILL.md headings by `scripts/validate-skills.py`.

---

### Task 1: SKILL.md frontmatter — version bump + discovery triggers

**Files:**
- Modify: `skills/foundry-mcp-aca/SKILL.md:1-14`

- [ ] **Step 1: Read the current frontmatter**

Run: `sed -n '1,14p' skills/foundry-mcp-aca/SKILL.md`
Expected: `metadata.version` shows `"1.1.0"`; `description:` mentions "authentication patterns".

- [ ] **Step 2: Bump the version**

Replace:
```yaml
  version: "1.1.0"
```
with:
```yaml
  version: "1.2.0"
```

- [ ] **Step 3: Add auth-hardening trigger phrases to the description**

In the `description:` folded block, replace the sentence fragment:
```
ACA configuration, and authentication patterns.
```
with:
```
ACA configuration, and authentication + hardening (ACA built-in auth / Easy Auth, OAuth, managed identity).
```
and in the `USE FOR:` list, replace:
```
remote MCP endpoint, MCP for hosted agent, connect hosted agent to MCP.
```
with:
```
remote MCP endpoint, MCP for hosted agent, connect hosted agent to MCP, secure MCP server, harden MCP server, MCP authentication, MCP OAuth, ACA Easy Auth for MCP.
```

- [ ] **Step 4: Verify YAML parses and description ≤ 1024 chars**

Run:
```bash
python3 -c "
import yaml, pathlib
fm = pathlib.Path('skills/foundry-mcp-aca/SKILL.md').read_text().split('---')[1]
d = yaml.safe_load(fm)
assert d['metadata']['version'] == '1.2.0', d['metadata']
n = len(d['description'])
print('desc chars:', n)
assert n <= 1024, f'TOO LONG: {n}'
print('OK')
"
```
Expected: prints `desc chars: <N under 1024>` then `OK`.

- [ ] **Step 5: Commit**

```bash
git add skills/foundry-mcp-aca/SKILL.md
git commit -m "foundry-mcp-aca: bump to v1.2.0 and add auth-hardening triggers [skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: SKILL.md body — replace `## Authentication` with `## Securing your MCP server`

**Files:**
- Modify: `skills/foundry-mcp-aca/SKILL.md:552-574` (the `## Authentication` block, bounded by `---` at 550 and 576)
- Modify: `skills/foundry-mcp-aca/SKILL.md:591` (Gotchas external-ingress row)
- Modify: `skills/foundry-mcp-aca/SKILL.md:599-603` (Failure Modes table — append rows)

- [ ] **Step 1: Confirm the exact current Authentication block boundaries**

Run: `sed -n '550,576p' skills/foundry-mcp-aca/SKILL.md`
Expected: line 550 `---`, line 552 `## Authentication`, a 3-row table, a json block, line 576 `---`. Note the exact text between the two `---` fences — that entire inner block is what Step 2 replaces.

- [ ] **Step 2: Replace the entire `## Authentication` section (everything between the `---` on line 550 and the `---` on line 576) with the new section**

New content (replaces the old heading, table, and json example — keep the surrounding `---` fences intact):

````markdown
## Securing your MCP server

> **The perimeter is yours to build.** A public survey found only **8.5% of
> reachable MCP servers require OAuth** — the rest are unauthenticated remote
> tool-execution endpoints, i.e. open RCE. A remote MCP server with no identity
> check is not "internal-only by obscurity"; it is exploitable. This section
> hardens the ACA deployment above with Entra-validated auth **in front of** the
> container, managed identity for the hops behind it, and audit + input
> defenses on the tools themselves.
>
> **This skill uses ACA built-in authentication ("Easy Auth for Container
> Apps") — not Azure App Service.** The platform validates the caller's token
> before a request reaches your code. Reference:
> [Authentication and authorization in Azure Container Apps](https://learn.microsoft.com/azure/container-apps/authentication).

### Threat model → defense mapping

| Threat | Mitigating layer | Where it lives |
|--------|------------------|----------------|
| Unauthenticated tool invocation (open RCE) | **L1** ACA built-in auth + `Return401` | `references/bicep/mcp-aca-auth.bicep` / `az containerapp auth` |
| Confused deputy — server replays the caller's token downstream | **L2** managed identity; never forward the inbound token | `references/python/secure_server.py` |
| Over-broad RBAC → lateral movement | **L2** one least-privilege role assignment | `references/bicep/mcp-aca-auth.bicep` |
| Secret exfiltration through a tool result | **L3** return secret *metadata*, never values; Key Vault refs | `references/python/secure_server.py` |
| Path traversal / command injection in tool args | **L3** allow-list inputs; reject `..` `/` `\` `;` `\|` `` ` `` `$(` | `references/python/secure_server.py` |
| Undetected abuse (invocation floods, probing) | **L5** one audit event per call → scheduled-query alert | `references/python/secure_server.py` + `foundry-observability` |

Defense-in-depth: skipping **L1** makes everything else moot; **L2–L5** keep a
breach from spreading.

### Layer 1 — Identity perimeter: ACA built-in auth

Put Entra in front of the container. ACA validates the JWT **before** it reaches
your app and injects a trusted `X-MS-CLIENT-PRINCIPAL` header (base64 JSON the
client cannot forge). Anonymous calls get `401` — they never touch your tools.

**One-time app registration** (defines the audience clients request a token for):

```bash
TENANT_ID=$(az account show --query tenantId -o tsv)
APP_ID=$(az ad app create --display-name "mcp-server-auth" \
  --sign-in-audience AzureADMyOrg --query appId -o tsv)
az ad sp create --id "$APP_ID"
# Expose api://<appId> as the resource callers request a token for:
az ad app update --id "$APP_ID" --identifier-uris "api://$APP_ID"
```

**Enable built-in auth + reject anonymous callers:**

```bash
az containerapp auth microsoft update -n <app> -g <rg> \
  --client-id "$APP_ID" \
  --issuer "https://login.microsoftonline.com/$TENANT_ID/v2.0" \
  --allowed-token-audiences "api://$APP_ID" --yes
az containerapp auth update -n <app> -g <rg> \
  --unauthenticated-client-action Return401
```

`Return401` is the API-server posture (reject), versus `RedirectToLoginPage`
(browser apps) or `AllowAnonymous` (pass everything through — never for a remote
MCP). The IaC-native equivalent — a `Microsoft.App/containerApps/authConfigs`
child resource, validation-only so it needs **no client secret** — is
[`references/bicep/mcp-aca-auth.bicep`](references/bicep/mcp-aca-auth.bicep).

**Caveat — no Dynamic Client Registration.** Entra does not implement DCR, so
interactive MCP clients must be **pre-registered**; ship a known client id
rather than expecting the client to self-register.

These options replace the old dev-only table:

| Option | When | Posture |
|--------|------|---------|
| Built-in auth + `Return401` (**recommended**) | Any reachable deployment | Entra-validated bearer |
| `AllowAnonymous` + a dev bypass flag | Local inner-loop only | No perimeter — never expose |

### Layer 2 — Managed identity and the confused-deputy rule

The server authenticates to Azure with its **own** managed identity, never the
caller's token. `DefaultAzureCredential` resolves `az login` locally and the
user-assigned MI in ACA — no secrets in code:

> **MUST:** downstream Azure access uses the server's MI. Copy the credential +
> secret-metadata pattern verbatim from
> [`references/python/secure_server.py`](references/python/secure_server.py).

**The confused-deputy rule:** the inbound token authorizes the caller to *your
server only*. Do **not** replay it to Cosmos, Key Vault, or another API. Use the
server's MI, or the On-Behalf-Of flow if you genuinely must act as the user.
Grant that MI exactly one role (e.g. `Key Vault Secrets User`) — the role
assignment is in
[`references/bicep/mcp-aca-auth.bicep`](references/bicep/mcp-aca-auth.bicep).

### Layer 3 — Secret hygiene and tool-input defense

**Never return a secret value from a tool.** Return metadata (name, version,
enabled) so the model can reason about a secret without exfiltrating it; the
value reaches the runtime via a Key Vault reference
(`@Microsoft.KeyVault(SecretUri=...)`), not through the model. The
`secret_status` tool in `secure_server.py` shows the pattern.

**Allow-list tool inputs.** Any argument that becomes a path, key, or shell
fragment is a traversal/injection vector. The `safe_lookup` tool in
`secure_server.py` rejects `..`, `/`, `\`, `;`, `|`, `` ` ``, and `$(` before
use — reject-by-default beats sanitizing.

### Layer 4 — Network hardening

Easy Auth is an **identity** perimeter, not a **network** one. For regulated
workloads add, in order: private endpoints + VNET injection, then an APIM front
door running `validate-jwt` + `rate-limit-by-key`. That topology (and why
Foundry hosted agents still require external ingress) is
[`foundry-vnet-deploy`](../foundry-vnet-deploy/SKILL.md) — out of scope here.

**External ingress is not "unauthenticated."** Foundry hosted agents run in
Foundry's infrastructure, so the MCP needs `--ingress external` (see Gotchas).
With Layer 1 in front, every external call still needs a valid token — external
ingress + Easy Auth is the standard safe posture. Reach for VNET isolation only
when a compliance boundary demands it.

### Layer 5 — Audit and monitoring

Emit one structured audit line per tool call (caller, tool, decision). ACA ships
stdout to Log Analytics automatically, so a
[`foundry-observability`](../foundry-observability/SKILL.md) scheduled-query
alert can fire on invocation spikes or repeated `denied` events. The
`audit_event` helper in `secure_server.py` is the emitter; upgrade to Azure
Monitor OpenTelemetry spans via `foundry-observability` when you want
distributed tracing.

### Connecting clients

| Client | How it authenticates | Notes |
|--------|----------------------|-------|
| **Server-to-server** (Foundry agent, any service) | Its MI requests a token for `api://<appId>`, sends `Authorization: Bearer <token>` | Platform-native; the CI fixture proves this 401→200 contract |
| **Interactive — manual bearer** (VS Code / Claude / Copilot) | Paste a token into the client's MCP config | Simplest interactive path |
| **Interactive — OAuth discovery** (advanced) | Server publishes PRM (RFC 9728); client follows `WWW-Authenticate` → user sign-in | Server's job on ACA — see below |

**Manual bearer** — a VS Code `.vscode/mcp.json` fragment:

```json
{
  "servers": {
    "my-mcp": {
      "type": "http",
      "url": "https://<aca-fqdn>/mcp/",
      "headers": { "Authorization": "Bearer ${input:mcpToken}" }
    }
  }
}
```

Get the token with
`az account get-access-token --resource api://<appId> --query accessToken -o tsv`.

**OAuth discovery (advanced).** Unlike Azure App Service (whose preview platform
feature can auto-serve Protected Resource Metadata), **on ACA the MCP server
itself must publish PRM** at `/.well-known/oauth-protected-resource` (RFC 9728)
and emit a `WWW-Authenticate` challenge so a spec-compliant client can discover
the authorization server and run the flow. FastMCP's auth provider implements
this; see the
[MCP authorization spec](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization).
This path requires an interactive browser sign-in, so it is documented but not
CI-tested.
````

- [ ] **Step 3: Reconcile the Gotchas external-ingress row**

Run: `sed -n '588,593p' skills/foundry-mcp-aca/SKILL.md`
Find the row whose Fix cell tells the reader to use `--ingress external` and points to `foundry-vnet-deploy`. Append this sentence to that Fix cell (keep it one table row — no line break inside the cell):
```
External ingress is safe when fronted by ACA built-in auth (see § Securing your MCP server → Layer 1); it is not the same as "unauthenticated."
```

- [ ] **Step 4: Add two 401 rows to the Failure Modes table**

Run: `sed -n '597,604p' skills/foundry-mcp-aca/SKILL.md`
Confirm the column order (Symptom | Root cause | DO NOT | DO instead — match the real header). Append these two rows immediately after the last existing row, using the actual column order you just confirmed:
```
| MCP call returns `401` after enabling built-in auth | Caller sent no token, or a token for the wrong resource | DO NOT switch to `AllowAnonymous` to "make it work" — that deletes the perimeter | Send `Authorization: Bearer $(az account get-access-token --resource api://<appId> --query accessToken -o tsv)`; confirm the token `aud` equals `api://<appId>` |
| `401` even with a token attached | `allowedAudiences` / issuer mismatch, or a Graph token | DO NOT paste a Microsoft Graph token (`--resource https://graph.microsoft.com`) | Request the token for `api://<appId>`; verify `--allowed-token-audiences` includes exactly that value and issuer is `https://login.microsoftonline.com/<tenant>/v2.0` |
```

- [ ] **Step 5: Verify headings exist and the file still parses**

Run:
```bash
grep -nE '^(## Securing your MCP server|### Threat model|### Layer [1-5] |### Connecting clients)' skills/foundry-mcp-aca/SKILL.md
python3 -c "import pathlib; t=pathlib.Path('skills/foundry-mcp-aca/SKILL.md').read_text(); assert t.count('## Authentication')==0, 'old heading still present'; print('old section gone; new headings present')"
```
Expected: the grep lists the `## Securing your MCP server` heading, `### Threat model → defense mapping`, all five `### Layer N —` headings, and `### Connecting clients`; the python check prints the confirmation.

- [ ] **Step 6: Commit**

```bash
git add skills/foundry-mcp-aca/SKILL.md
git commit -m "foundry-mcp-aca: add 'Securing your MCP server' defense-in-depth section [skill-rewrite]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Create `references/python/secure_server.py`

**Files:**
- Create: `skills/foundry-mcp-aca/references/python/secure_server.py`

- [ ] **Step 1: Write the file**

```python
"""Hardened FastMCP server for ACA — Easy Auth perimeter + defense in depth.

Source of truth for the prose example in `../../SKILL.md § Securing your MCP
server`. This is the hardened sibling of `server.py`; keep `server.py` minimal
and copy the hardening patterns from here.

Layers demonstrated (full threat model in SKILL.md):
    L1  whoami() reads the ACA-injected X-MS-CLIENT-PRINCIPAL header. ACA sets
        it only AFTER validating the JWT at the platform edge, so the header
        identity is trustworthy and cannot be forged by the client.
    L2  DefaultAzureCredential uses the container's managed identity for
        downstream Azure — NEVER the caller's inbound token (confused deputy).
    L3  secret_status() returns secret METADATA, never the value.
        safe_lookup() rejects path-traversal / injection characters.
    L5  audit_event() emits one structured line per call; ACA ships stdout to
        Log Analytics for a foundry-observability scheduled-query alert.

NEVER call one @mcp.tool()-decorated function from inside another — @mcp.tool()
wraps it in a FunctionTool that is not plain-callable. Extract shared logic into
a private _helper() (here: _lookup_backend) and call THAT from both tools.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import os

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from fastmcp import FastMCP

mcp = FastMCP("secure-tools")

logging.basicConfig(level=logging.INFO, format="%(message)s")
_audit = logging.getLogger("mcp.audit")

# One credential for the process lifetime — resolves `az login` locally and the
# user-assigned managed identity in ACA. No secrets in code (Layer 2).
_credential = DefaultAzureCredential()

# Characters that must never appear in a tool argument used as a key or path.
_UNSAFE = ("..", "/", "\\", ";", "|", "`", "$(")


def audit_event(caller: str, tool: str, decision: str, detail: str = "") -> None:
    """Emit one structured audit line (Layer 5). ACA -> Log Analytics captures
    stdout; a foundry-observability scheduled query alerts on spikes / denials."""
    _audit.info(
        json.dumps(
            {
                "event": "mcp.tool.call",
                "caller": caller,
                "tool": tool,
                "decision": decision,
                "detail": detail,
            }
        )
    )


def caller_identity(client_principal_b64: str | None) -> str:
    """Decode the ACA-injected X-MS-CLIENT-PRINCIPAL header (base64 JSON).

    ACA populates this header only after it has validated the token, so the
    claims here are trustworthy. Returns a stable caller id for auditing."""
    if not client_principal_b64:
        return "anonymous"
    try:
        raw = base64.b64decode(client_principal_b64)
        claims = json.loads(raw).get("claims", [])
    except (binascii.Error, json.JSONDecodeError, ValueError):
        return "unknown"
    wanted = {"preferred_username", "upn", "appid", "azp", "sub"}
    for claim in claims:
        if claim.get("typ") in wanted and claim.get("val"):
            return str(claim["val"])
    return "unknown"


def _reject_unsafe(value: str) -> None:
    """Layer 3 input allow-list: raise on traversal / injection characters."""
    if any(token in value for token in _UNSAFE):
        raise ValueError(f"rejected unsafe input: {value!r}")


def _lookup_backend(key: str) -> dict:
    """Plain helper — both tools call THIS, never each other (see module docstring)."""
    return {"key": key, "status": "ok"}


@mcp.tool()
async def whoami(client_principal: str | None = None) -> dict:
    """Return the validated caller identity from the Easy Auth header (Layer 1)."""
    who = caller_identity(client_principal)
    audit_event(who, "whoami", "allowed")
    return {"caller": who}


@mcp.tool()
async def safe_lookup(key: str, client_principal: str | None = None) -> dict:
    """Look up a record by key, rejecting traversal / injection first (Layer 3)."""
    who = caller_identity(client_principal)
    try:
        _reject_unsafe(key)
    except ValueError as exc:
        audit_event(who, "safe_lookup", "denied", str(exc))
        raise
    audit_event(who, "safe_lookup", "allowed", key)
    return _lookup_backend(key)


@mcp.tool()
async def secret_status(name: str, client_principal: str | None = None) -> dict:
    """Return secret METADATA (never the value) via the server's MI (Layers 2+3)."""
    who = caller_identity(client_principal)
    _reject_unsafe(name)
    vault_url = os.environ["KEY_VAULT_URL"]
    client = SecretClient(vault_url=vault_url, credential=_credential)
    props = client.get_secret(name).properties
    audit_event(who, "secret_status", "allowed", name)
    return {
        "name": props.name,
        "enabled": props.enabled,
        "version": props.version,
        "not_before": str(props.not_before),
        "expires_on": str(props.expires_on),
        # NOTE: the secret VALUE is deliberately never returned.
    }


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
    )
```

- [ ] **Step 2: Verify it compiles and the anchor resolves**

Run:
```bash
python3 -m py_compile skills/foundry-mcp-aca/references/python/secure_server.py && echo "py_compile OK"
python3 scripts/validate-skills.py 2>&1 | grep -iE "secure_server|anchor|§" || echo "no anchor/ref errors for secure_server"
```
Expected: `py_compile OK`; no anchor error mentioning `secure_server.py` (the `§ Securing your MCP server` anchor resolves to the Task-2 heading).

- [ ] **Step 3: Commit**

```bash
git add skills/foundry-mcp-aca/references/python/secure_server.py
git commit -m "foundry-mcp-aca: add canonical hardened secure_server.py reference

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Create `references/bicep/mcp-aca-auth.bicep`

**Files:**
- Create: `skills/foundry-mcp-aca/references/bicep/mcp-aca-auth.bicep`

- [ ] **Step 1: Write the file**

```bicep
// =============================================================================
// CANONICAL REFERENCE — ACA built-in auth (Easy Auth) for an MCP server
//
// Source of truth for the prose example in `../../SKILL.md § Layer 1 —
// Identity perimeter`.
//
// Add-on to mcp-aca.bicep: fronts the container app with Entra-validated auth
// so unauthenticated callers get 401 (Return401) and never reach your tools.
// Validation-only posture — NO client secret, because we only VALIDATE inbound
// bearer tokens (we do not run the interactive login/redirect flow). Add a
// clientSecretSettingName + an ACA secret only if you also need interactive
// browser sign-in.
//
// Also grants the app's user-assigned MI exactly one least-privilege role
// (Key Vault Secrets User) — Layer 2's confused-deputy defense.
// =============================================================================

@description('Name of the existing MCP container app (from mcp-aca.bicep)')
param containerAppName string

@description('Entra app (client) ID whose api://<clientId> audience callers request')
param authClientId string

@description('Entra tenant ID that issues the tokens')
param tenantId string = subscription().tenantId

@description('Existing Key Vault the MI may read secret metadata from')
param keyVaultName string

@description('Principal (object) ID of the container app user-assigned MI')
param mcpIdentityPrincipalId string

resource app 'Microsoft.App/containerApps@2024-03-01' existing = {
  name: containerAppName
}

// Easy Auth: validate Entra tokens at the platform edge; reject anonymous
// callers with 401 before the request reaches the container.
resource authConfig 'Microsoft.App/containerApps/authConfigs@2025-01-01' = {
  parent: app
  name: 'current'
  properties: {
    platform: {
      enabled: true
    }
    globalValidation: {
      // API-server posture: reject unauthenticated calls outright.
      unauthenticatedClientAction: 'Return401'
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: authClientId
          openIdIssuer: 'https://login.microsoftonline.com/${tenantId}/v2.0'
          // No clientSecretSettingName: validation-only (bearer JWT check).
        }
        validation: {
          // The token's `aud` MUST equal this value or ACA returns 401.
          allowedAudiences: [
            'api://${authClientId}'
          ]
        }
      }
    }
  }
}

// Layer 2 — least privilege: the MI may read secret METADATA, nothing broader.
resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

// Key Vault Secrets User (built-in role).
var keyVaultSecretsUserRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '4633458b-17de-408a-b874-0445c86b69e6'
)

resource secretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(kv.id, mcpIdentityPrincipalId, keyVaultSecretsUserRoleId)
  scope: kv
  properties: {
    roleDefinitionId: keyVaultSecretsUserRoleId
    principalId: mcpIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}
```

- [ ] **Step 2: Verify it compiles and the anchor resolves**

Run:
```bash
az bicep build --file skills/foundry-mcp-aca/references/bicep/mcp-aca-auth.bicep --stdout >/dev/null && echo "bicep build OK"
python3 scripts/validate-skills.py 2>&1 | grep -iE "mcp-aca-auth|anchor|§" || echo "no anchor/ref errors for mcp-aca-auth"
```
Expected: `bicep build OK` (warnings about the role assignment being a broad scope are acceptable — only a non-zero exit fails); no anchor error mentioning `mcp-aca-auth.bicep` (the `§ Layer 1 — Identity perimeter` anchor substring-matches the Task-2 heading).

- [ ] **Step 3: Commit**

```bash
git add skills/foundry-mcp-aca/references/bicep/mcp-aca-auth.bicep
git commit -m "foundry-mcp-aca: add canonical Easy Auth authConfig Bicep reference

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 5: Add `azure-keyvault-secrets` to `references/upstream-pin.md`

**Files:**
- Modify: `skills/foundry-mcp-aca/references/upstream-pin.md` (frontmatter `packages`, `validation.script`, `docs_to_revalidate`, prose table, `last_validated`)

- [ ] **Step 1: Read the current pin structure**

Run: `sed -n '1,120p' skills/foundry-mcp-aca/references/upstream-pin.md`
Note the exact indentation of the `packages:` list entries, the `validation.script:` pip-install line and the import block, the `docs_to_revalidate:` list, the prose table rows, and the `last_validated:` line.

- [ ] **Step 2: Add the package to the frontmatter `packages` list**

After the existing `azure-identity` package entry (match the existing entry's exact field shape — typically `name`, `version`, and any `notes`), add:
```yaml
    - name: azure-keyvault-secrets
      version: "4.11.0"
      notes: "SecretClient — Layer 3 secret-metadata tool in secure_server.py"
```
(Adjust indentation to match the sibling entries exactly.)

- [ ] **Step 3: Add the bounded pip pin + import smoke to `validation.script`**

In the `validation.script` block, add `azure-keyvault-secrets~=4.11.0` to the `pip install` line (space-separated, keep the other pins unchanged), and add this line to the import-smoke section alongside the other `from ... import ...` lines:
```
from azure.keyvault.secrets import SecretClient
```
Ensure the `~=4.11.0` specifier is used verbatim (AGENTS.md §9.5 requires a bounded `~=` cap; the validator's `_PIP_SPEC_RE` rejects bare `==`/`>=`/unpinned).

- [ ] **Step 4: Add the PyPI doc to `docs_to_revalidate`**

Add this list item (match existing indentation):
```yaml
    - https://pypi.org/project/azure-keyvault-secrets/
```

- [ ] **Step 5: Add a prose-table row and bump `last_validated`**

In the human-readable package table, add one row for `azure-keyvault-secrets` at version `4.11.0` (match the table's column shape). Do **NOT** modify any other row (the pre-existing version drift in that table is out of scope — AGENTS.md §4). Then set:
```yaml
last_validated: 2026-07-02
```

- [ ] **Step 6: Verify the pin's validation script runs and imports resolve**

Run:
```bash
python3 -m venv /tmp/pinvenv && . /tmp/pinvenv/bin/activate
pip install -q "azure-keyvault-secrets~=4.11.0" "azure-identity~=1.25.3" && \
python3 -c "from azure.keyvault.secrets import SecretClient; from azure.identity import DefaultAzureCredential; print('imports OK')"
deactivate
```
Expected: `imports OK`. (This is the T1/T2 import smoke the CI `pin-validation.yml` gate re-runs.)

- [ ] **Step 7: Confirm YAML front-matter still parses**

Run:
```bash
python3 -c "
import yaml, pathlib
txt = pathlib.Path('skills/foundry-mcp-aca/references/upstream-pin.md').read_text()
fm = txt.split('---')[1]
d = yaml.safe_load(fm)
names = [p['name'] for p in d['packages']]
assert 'azure-keyvault-secrets' in names, names
print('pin frontmatter OK; packages:', names)
"
```
Expected: prints the package list including `azure-keyvault-secrets`.

- [ ] **Step 8: Commit**

```bash
git add skills/foundry-mcp-aca/references/upstream-pin.md
git commit -m "foundry-mcp-aca: pin azure-keyvault-secrets ~=4.11.0 for secure_server.py

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 6: Extend the CI fixture with a gated 401→200 auth proof

**Files:**
- Modify: `skills/foundry-mcp-aca/test-fixture/consumer_prompt.md` (Step 0 env inventory; insert new auth block after Step 5, before the Step 6 marker)

**Context the executor MUST preserve:** Pattern 11 (show-don't-assert env), Pattern 12 (byte-exact marker file `/tmp/foundry-mcp-aca-smoke-result`), Pattern 17 (show-don't-assert `az`), Pattern 20 (goal prompt, no `Use skill X`), Pattern 25 (teardown best-effort/soft-PASS), Pattern 27 (never invoke `copilot` recursively). The MCP endpoint is `https://<fqdn>/mcp/` (trailing slash) with header `Accept: application/json, text/event-stream`.

- [ ] **Step 1: Read the fixture's Step 0 env inventory and the Step 5 → Step 6 boundary**

Run:
```bash
sed -n '18,48p'  skills/foundry-mcp-aca/test-fixture/consumer_prompt.md   # env-available list
sed -n '68,116p' skills/foundry-mcp-aca/test-fixture/consumer_prompt.md   # Step 0 inventory
sed -n '505,530p' skills/foundry-mcp-aca/test-fixture/consumer_prompt.md  # end of Step 5, start of Step 6
```
Note the exact heading text of Step 5's success paragraph and the exact `## Step 6` (or similar) heading — Step 3 inserts the new block **between** them.

- [ ] **Step 2: Add the optional auth var to the Step 0 env inventory (show-don't-assert)**

In the Step 0 inventory `echo` block, after the existing `AZURE_*` show lines, add:
```bash
echo "MCP_AUTH_APP_CLIENT_ID=${MCP_AUTH_APP_CLIENT_ID:+set}"
```
and add one sentence right below the inventory block:
```
`MCP_AUTH_APP_CLIENT_ID` is OPTIONAL. When set, it is the client id of a standing pre-registered Entra app whose `api://<id>` audience this smoke uses to prove the 401→200 Easy Auth contract. When unset, the auth sub-test (Step 5b) is SKIPPED with a NOTE — that is expected and MUST NOT fail the run.
```

- [ ] **Step 3: Insert the new auth block between Step 5's success paragraph and the Step 6 marker heading**

Insert this entire block (renumber nothing else; it slots in as "Step 5b"):

````markdown
## Step 5b — Easy Auth 401→200 proof (HARD GATE only when `MCP_AUTH_APP_CLIENT_ID` is set)

Layer 1 of the skill's security model is ACA built-in auth: the platform must
return **401** to an unauthenticated caller and **200** to a caller presenting a
valid Entra bearer token for `api://$MCP_AUTH_APP_CLIENT_ID`.

**Gate:** if `MCP_AUTH_APP_CLIENT_ID` is empty, SKIP this entire step — echo
exactly `NOTE: MCP_AUTH_APP_CLIENT_ID unset — skipping Easy Auth 401/200 proof`
and proceed to Step 6. Do NOT write a FAIL marker for an unset client id; the
base smoke (Steps 1–5) already proved the server works.

When `MCP_AUTH_APP_CLIENT_ID` IS set, run all of the following. Any failure here
is a HARD FAIL — write the FAIL marker (see Step 6 format) with a one-line reason
and stop.

1. **Enable built-in auth on the app you deployed** (use the app name and
   resource group from your earlier steps; `$TENANT_ID` from
   `az account show --query tenantId -o tsv`):

   ```bash
   az containerapp auth microsoft update -n "$APP_NAME" -g "$RG" \
     --client-id "$MCP_AUTH_APP_CLIENT_ID" \
     --issuer "https://login.microsoftonline.com/$TENANT_ID/v2.0" \
     --allowed-token-audiences "api://$MCP_AUTH_APP_CLIENT_ID" --yes
   az containerapp auth update -n "$APP_NAME" -g "$RG" \
     --unauthenticated-client-action Return401
   ```

2. **Wait for the auth config to take effect** (Easy Auth propagation is a
   control-plane change; poll up to 6× with a 10 s back-off):

   ```bash
   for i in $(seq 1 6); do
     CODE=$(curl -s -o /dev/null -w '%{http_code}' \
       -H 'Accept: application/json, text/event-stream' \
       "https://$FQDN/mcp/")
     [ "$CODE" = "401" ] && break
     sleep 10
   done
   echo "unauth status: $CODE"
   ```

   **Assert 401.** If `$CODE` is not `401` after the loop, HARD FAIL with
   `auth proof: expected 401 unauth, got $CODE`.

3. **Acquire a token and assert 200.** The CI managed identity requests a token
   for the app's audience, then repeats the MCP `initialize` round-trip WITH the
   bearer header:

   ```bash
   TOKEN=$(az account get-access-token \
     --resource "api://$MCP_AUTH_APP_CLIENT_ID" \
     --query accessToken -o tsv)
   AUTHED_CODE=$(curl -s -o /tmp/mcp-authed.json -w '%{http_code}' \
     -X POST "https://$FQDN/mcp/" \
     -H 'Content-Type: application/json' \
     -H 'Accept: application/json, text/event-stream' \
     -H "Authorization: Bearer $TOKEN" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"ci","version":"1"}}}')
   echo "authed status: $AUTHED_CODE"
   ```

   **Assert the authed call is NOT 401** (a 200 or a valid MCP JSON-RPC/SSE
   response both count as success — the platform let the request through to the
   server). If `$AUTHED_CODE` is `401`, HARD FAIL with
   `auth proof: valid token still rejected ($AUTHED_CODE)`. Common cause: the CI
   MI is not authorized for `api://$MCP_AUTH_APP_CLIENT_ID`; note it and FAIL.

When both assertions hold, echo `auth proof: 401 unauth / authed OK` and proceed
to Step 6.
````

- [ ] **Step 4: Update the Step 6 marker preamble to acknowledge the auth gate**

In the Step 6 intro sentence (the one describing when to write the PASS marker), change the "once both hard gates pass" phrasing so it reads (adjust to match the fixture's actual wording — keep it one edit):
```
Once the Step 4 provision gate, the Step 5 MCP round-trip gate, AND the Step 5b auth gate (or its documented SKIP when MCP_AUTH_APP_CLIENT_ID is unset) have all passed, write the PASS marker IMMEDIATELY.
```

- [ ] **Step 5: Sanity-check the fixture still contains its load-bearing patterns**

Run:
```bash
grep -c 'foundry-mcp-aca-smoke-result' skills/foundry-mcp-aca/test-fixture/consumer_prompt.md
grep -c "never invoke .copilot. recursively" skills/foundry-mcp-aca/test-fixture/consumer_prompt.md
grep -nE 'Step 5b|Return401|expected 401 unauth' skills/foundry-mcp-aca/test-fixture/consumer_prompt.md
```
Expected: the marker path count is ≥1, the recursive-copilot guard count is ≥1, and the grep lists the new Step 5b markers.

- [ ] **Step 6: Commit**

```bash
git add skills/foundry-mcp-aca/test-fixture/consumer_prompt.md
git commit -m "foundry-mcp-aca: fixture proves live 401->200 Easy Auth contract (gated)

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 7: Wire the optional secret into the CI workflow (inert until maintainer creates it)

**Files:**
- Modify: `.github/workflows/skill-test.yml` (the `copilot-cli-matrix` job — both the main run step env and the retry step env)

- [ ] **Step 1: Find the two fixture-run env blocks**

Run:
```bash
grep -nE 'AZURE_CLIENT_ID: \$\{\{ secrets\.AZURE_CLIENT_ID \}\}' .github/workflows/skill-test.yml
```
Expected: two matches (the main "Run consumer prompt" step and the "Retry …" step). Note both line numbers.

- [ ] **Step 2: Add the passthrough to BOTH env blocks (Pattern 11 — byte-identical across run + retry)**

Immediately after the `AZURE_SUBSCRIPTION_ID: ${{ secrets.AZURE_SUBSCRIPTION_ID }}` line in **each** of the two env blocks, add:
```yaml
          MCP_AUTH_APP_CLIENT_ID: ${{ secrets.MCP_AUTH_APP_CLIENT_ID }}
```
(Match the surrounding indentation exactly. When the secret is absent the value is an empty string, so the fixture's Step 5b gate skips gracefully.)

- [ ] **Step 3: Validate the workflow YAML parses**

Run:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/skill-test.yml')); print('workflow YAML OK')"
grep -c 'MCP_AUTH_APP_CLIENT_ID' .github/workflows/skill-test.yml
```
Expected: `workflow YAML OK`; the grep count is `2`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/skill-test.yml
git commit -m "ci: pass optional MCP_AUTH_APP_CLIENT_ID secret into mcp-aca fixture

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 8: Rebuild the docs site

**Files:**
- Regenerate: `docs/**`

- [ ] **Step 1: Rebuild**

Run: `python3 scripts/build-site.py --out docs/`
Expected: completes without error; `git status` shows regenerated files under `docs/` (the `foundry-mcp-aca` page reflects v1.2.0 and the new section).

- [ ] **Step 2: Commit**

```bash
git add docs/
git commit -m "docs: rebuild site for foundry-mcp-aca v1.2.0

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 9: Full local validation gate

**Files:** none (verification only; commit only if a fix is required)

- [ ] **Step 1: Run the skill validator**

Run: `python3 scripts/validate-skills.py`
Expected: exits 0 with no errors for `foundry-mcp-aca` (frontmatter, description length, semver, forbidden strings, reference-file syntax lint, and `§` anchor resolution all pass).

- [ ] **Step 2: Run the plugin structural check**

Run: `python3 scripts/build-plugins.py --check`
Expected: exits 0 (single-plugin structure intact).

- [ ] **Step 3: Belt-and-braces YAML + description guard**

Run:
```bash
python3 -c "
import yaml, pathlib
fm = pathlib.Path('skills/foundry-mcp-aca/SKILL.md').read_text().split('---')[1]
d = yaml.safe_load(fm)
assert d['metadata']['version']=='1.2.0'
assert len(d['description'])<=1024
print('SKILL.md frontmatter OK,', len(d['description']), 'desc chars')
"
```
Expected: prints the confirmation.

- [ ] **Step 4: Forbidden-string smell test on the diff**

Run:
```bash
git --no-pager diff main -- skills/foundry-mcp-aca | grep -nE 'kyc-poc|card-dispute|threadlight-v[123]|subscriptions/[0-9a-f]{8}-' || echo "no forbidden strings"
```
Expected: `no forbidden strings`.

- [ ] **Step 5: If any check failed, fix inline and commit**

Only if Steps 1–4 surfaced an issue:
```bash
git add -A
git commit -m "foundry-mcp-aca: fix validation findings

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 10: Live Azure 401→200 proof (AGENTS.md §2.9 evidence)

**Files:** none (produces evidence for the review hand-off; nothing to commit)

**Goal:** Reproduce the fixture's Layer-1 contract against real Azure using the operator's local `az login`. Capture the raw 401 and authed-200 outputs for the PR body.

**Prerequisite reality check:** creating the Entra app registration needs Microsoft Graph `Application.ReadWrite` on the signed-in identity. If that is denied, fall back per Step 6 and document the standing-app prerequisite instead of forcing it.

- [ ] **Step 1: Confirm the local context**

Run:
```bash
az account show --query '{sub:id, tenant:tenantId, user:user.name}' -o json
az group show -n rg-awesome-gbb-ci -o none 2>/dev/null && echo "CI RG reachable" || echo "CI RG not reachable — will use a scratch RG"
```
Record the subscription/tenant. Choose the CI RG if reachable, else a scratch RG in Sweden Central.

- [ ] **Step 2: Deploy a minimal MCP server to ACA**

Reuse the skill's canonical path (this mirrors the fixture Steps 1–4): build the container from `references/python/server.py` (or a one-file FastMCP `whoami` app), push to ACR, and `azd provision` / `az containerapp create` an external-ingress app on the CAE. Capture `FQDN=$(az containerapp show -n <app> -g <rg> --query properties.configuration.ingress.fqdn -o tsv)`.
Expected: `curl -s -H 'Accept: application/json, text/event-stream' https://$FQDN/mcp/` returns an MCP response (server works pre-auth).

- [ ] **Step 3: Register the Entra app + enable Easy Auth**

Run the Layer-1 commands from SKILL.md:
```bash
TENANT_ID=$(az account show --query tenantId -o tsv)
APP_ID=$(az ad app create --display-name "mcp-server-auth-livetest" \
  --sign-in-audience AzureADMyOrg --query appId -o tsv)
az ad sp create --id "$APP_ID"
az ad app update --id "$APP_ID" --identifier-uris "api://$APP_ID"
az containerapp auth microsoft update -n <app> -g <rg> \
  --client-id "$APP_ID" \
  --issuer "https://login.microsoftonline.com/$TENANT_ID/v2.0" \
  --allowed-token-audiences "api://$APP_ID" --yes
az containerapp auth update -n <app> -g <rg> \
  --unauthenticated-client-action Return401
```
If `az ad app create` is denied by tenant policy, STOP and go to Step 6.

- [ ] **Step 4: Assert 401 (no token)**

Run:
```bash
for i in $(seq 1 6); do
  CODE=$(curl -s -o /dev/null -w '%{http_code}' \
    -H 'Accept: application/json, text/event-stream' "https://$FQDN/mcp/")
  [ "$CODE" = "401" ] && break; sleep 10
done
echo "UNAUTH=$CODE"
```
Expected: `UNAUTH=401`. Save this line as evidence.

- [ ] **Step 5: Assert authed call is not 401**

Run:
```bash
TOKEN=$(az account get-access-token --resource "api://$APP_ID" --query accessToken -o tsv)
AUTHED=$(curl -s -o /tmp/authed.json -w '%{http_code}' -X POST "https://$FQDN/mcp/" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"livetest","version":"1"}}}')
echo "AUTHED=$AUTHED"; head -c 400 /tmp/authed.json
```
Expected: `AUTHED` is `200` (or a valid MCP JSON-RPC/SSE payload) — NOT `401`. Save the two lines (`UNAUTH=401`, `AUTHED=200`) as the §2.9 evidence block.

- [ ] **Step 6: If app registration was blocked — document the standing-app prerequisite**

Record in the review hand-off: the CI UAMI / local identity lacks Microsoft Graph `Application.ReadWrite`, so a **maintainer must create a standing Entra app registration once** and store its client id as the `MCP_AUTH_APP_CLIENT_ID` GitHub secret (Task 7 already wires it). Capture whatever proof you COULD get (e.g. the pre-auth deploy working, or a 401 from a manually-configured authConfig) so the review still has partial live evidence.

- [ ] **Step 7: Tear down the live-test resources (best-effort, Pattern 25)**

Run:
```bash
az ad app delete --id "$APP_ID" 2>/dev/null || echo "app cleanup skipped"
# delete the scratch container app / RG if you created one just for this test
```

---

## Self-review checklist (run after execution, before the review hand-off)

- [ ] **Spec coverage:** every spec section maps to a task — threat→defense table (Task 2), 5 layers (Task 2 + refs Tasks 3–4), both consumer models (Task 2 `### Connecting clients`), reference SSOT (Tasks 3–4), pin (Task 5), CI 401/200 fixture + infra dependency (Tasks 6–7), versioning/cross-refs/commit tags (Tasks 1–2), live evidence (Task 10). The dropped `mcp.json` is folded into Task 2 inline (see Deviations).
- [ ] **Placeholder scan:** `grep -rInE 'TBD|TODO|FIXME|fill in|<placeholder>' skills/foundry-mcp-aca docs/superpowers/plans/2026-07-02-mcp-auth-hardening.md` → only legitimate `<app>`/`<rg>`/`<appId>`/`<fqdn>`/`<tenant>` doc placeholders remain.
- [ ] **Name consistency:** headings cited by reference headers exactly match — `secure_server.py` → `§ Securing your MCP server`; `mcp-aca-auth.bicep` → `§ Layer 1 — Identity perimeter`. Tool names (`whoami`, `safe_lookup`, `secret_status`) and helper (`_lookup_backend`) match between SKILL.md prose and `secure_server.py`.
- [ ] **Cross-refs are outbound-only** (`foundry-vnet-deploy`, `foundry-observability`) — no `[multi-skill]` tag needed; SKILL.md body edits carry `[skill-rewrite]`.
- [ ] **Azure-tested:** Task 10 evidence (or the documented standing-app blocker) is captured for the §2.9 review gate.

## Execution note

This is an authorized autonomous run ("proceed autonomously till live testing and review"). After the plan self-review, execute Tasks 1–10 inline (superpowers:executing-plans), then **STOP for user review** — do NOT open a PR or merge.
