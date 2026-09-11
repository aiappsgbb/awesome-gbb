---
name: foundry-mcp-auth
description: >
  Use when a custom Foundry MCP server needs delegated user authentication,
  OAuth identity passthrough, audience-correct access tokens, per-user scope
  authorization, or connection-consent troubleshooting. USE FOR: custom Entra
  OAuth MCP, Prompt Agent MCP connection, Hosted FoundryToolbox caller context,
  oauth_consent_request, CONSENT_REQUIRED, delegated versus app-only identity,
  MCP protected resource metadata, OAuth versus literal Entra OBO.
  DO NOT USE FOR: generic Toolbox management (use foundry-toolbox), hosted
  runtime deployment (use foundry-hosted-agents), durable MCP tasks or jobs
  (use foundry-mcp-aca-jobs), web frontend sign-in, or general network provisioning.
metadata:
  version: "1.0.0"
---

# Foundry MCP delegated authentication

**UNRELEASED CANDIDATE - THREE LIVE DELEGATED PATHS VERIFIED.** The initial
cycle was LOCAL ONLY. On 2026-09-11, **Prompt -> direct MCP** and
**Hosted -> Toolbox**, and **Prompt -> Toolbox -> MCP** executed the read-only tools over private networking
as the real consenting user, with server-side `demo.read` and identity receipts.
This is not four-path compatibility, multi-user isolation certification, or a
literal OBO exchange. All four paths below remain final acceptance criteria.
Do not publish, deploy, register apps, write connections, or grant consent
without **Gate B**, the operator's separate cloud-change approval.

## Identity boundaries

| Boundary | Identity and credential |
|---|---|
| User -> Foundry | Existing tenant-isolated Azure CLI user credential for backend tests, or user sign-in to Playground; same tenant as the project. Neither implies MCP consent. |
| Hosted agent -> Toolbox | Agent runtime credential, with audience `https://ai.azure.com`; upstream wrapper forwards the trusted request-scoped `x-agent-foundry-call-id`. |
| Foundry/Toolbox -> custom MCP | Credentials from the user's custom OAuth connection, minted for the MCP API's own audience and delegated permission. |
| MCP -> another API, if separately required | Explicit Entra OBO exchange for the second audience, not replay of the inbound access token. Not implemented in this candidate. |

OAuth identity passthrough is **not proof of Entra OBO**. It is native
connection-managed authorization/refresh. `UserEntraToken` is a different
mechanism for supported services, not a universal custom-server substitute.
Never send Microsoft-audience tokens to a custom MCP, copy a personal token
into an agent definition, or fall back to managed identity when user context
is missing. Do not decode, fabricate, persist, or send the platform call ID
to the custom MCP.

## Released support and remaining acceptance

| Required path | Current contract | Remaining status |
|---|---|---|
| Prompt -> direct MCP | `MCPTool.project_connection_id` references custom OAuth; Foundry emits consent output. | LIVE PASS for one user via API on 2026-09-11; Playground UX still NOT DEMONSTRATED. |
| Hosted -> Toolbox -> MCP | Upstream `FoundryToolbox` carries platform auth and request context; inner `MCPToolboxTool` references OAuth. | LIVE PASS for one user via API on 2026-09-11; late consent/revocation and second-user isolation NOT DEMONSTRATED. |
| Prompt -> Toolbox -> MCP | Native `UserEntraToken` connection targets first-party Toolbox; its inner MCP connection stays custom OAuth2. | LIVE PASS for one user; no static bearer or custom token broker. |
| Hosted -> direct MCP | Native `FoundryChatClient.get_mcp_tool(project_connection_id=...)` was deployed separately, without custom caller headers. | NOT DEMONSTRATED: returned completed/empty output with no tool evidence in the tested stack. The working Hosted/Toolbox agent is preserved separately. |

The pinned hosting release converts Toolbox consent during initialization,
not arbitrary late `CONSENT_REQUIRED` tool errors. Newer hosting
`1.0.0b260903` adds OAuth Content output, but does not establish conversion of
late Toolbox exceptions. No speculative adapter is shipped. A user's initial
consent after another user initialized the shared host, expiry, and revocation
must remain explicit gates, not silently successful retries.

Use two independent users for final isolation acceptance. Local signed-token
concurrency tests are not a substitute for two actual Entra users.

## Canonical artifacts

Copy/import these implementations rather than repeating their bodies:

| File | Owned contract |
|---|---|
| [authorization.py](references/python/authorization.py) | Resource-server authorization: signature, issuer, audience, lifetime, delegated scope, pseudonymous receipts and synthetic ownership. |
| [delegated_server.py](references/python/delegated_server.py) | Resource-server authorization: HTTP MCP, PRM, request-local identity and deny logging. |
| [connection.yaml](references/yaml/connection.yaml) | Connection setup: secret-free definition using environment references, not secret command-line arguments. |
| [connection-contract.md](references/connection-contract.md) | Connection setup: resource/client separation, scopes, callback, create/read and consent lifecycle. |
| [provision_connection.py](references/python/provision_connection.py) | Connection setup: live-proven GA ARM builder and opt-in create/update with safe readback. |
| [configure_foundry.py](references/python/configure_foundry.py) | Agent integration: pure SDK builders and explicit Gate-B-only create function. |
| [invoke_agent.py](references/python/invoke_agent.py) | Agent integration: distinct Prompt/Hosted endpoints, consent continuation and failure-status handling. |
| [hosted_agent.py](references/python/hosted_agent.py) | Agent integration: minimal composition using the upstream Toolbox/Responses wrappers. |
| [stage_hosted.py](references/python/stage_hosted.py) | Local recipe: stage canonical build inputs inside a standalone Hosted project, never through `..` service paths. |
| [templates/](templates/) | Local recipe: separate server, management and hosted dependency environments; brownfield `azd` composition. |
| [playground.md](test-fixture/playground.md) | Live acceptance: operator-driven Playground protocol, including all unresolved cases. |
| [demo-runbook.md](references/demo-runbook.md) | Reproducing and operating the retained two-path demo without resource expiry or automatic cleanup. |

## Resource-server authorization

Use a tenant-specific Entra v2 issuer/JWKS and the API application ID as JWT
audience. Pin RS256; require expiry, issued-at and identity claims; validate
not-before when present. Read signed `scp`, not `scope`, `roles`, a model
argument or a claimed user header. `azp` identifies the OAuth client, not
the user. Invalid credentials return 401; a valid app-only or insufficiently
scoped token returns 403. JWKS transport failures surface as errors, never
as successful or anonymous tool calls.

Three identifiers are deliberately different: MCP resource URL
`https://<host>/mcp`, JWT audience `<api-application-id>`, and OAuth requested
scope `api://<api-application-id>/demo.read`. The JWT permission is `demo.read`.
The verifier maps that validated permission to the full scope advertised by
PRM; `offline_access` is not a business permission required in the access token.
The MCP is a resource server only: no token broker, OAuth proxy, DCR or callback
service. Entra clients must be pre-registered.

Keep `include_fastmcp_meta=False`: the Hosted Toolbox consumer rejected the
private `_fastmcp` metadata key. This disables only vendor-specific metadata,
not authentication or authorization. After changing an already-published tool
schema, create a fresh Toolbox version and bind the Hosted agent to that
version; stale metadata persisted in the initial Hosted composition until this
version refresh.

`who_am_i()` and `list_my_demo_items()` take no identity arguments. Each call
uses its authenticated request context. Receipts never contain JWTs, raw
subject/tenant IDs, emails or secrets. Pseudonyms use a random process-local
HMAC key; they change on restart. The demo uses one replica. Cross-restart
identity reconciliation is not a feature of this mock.

For redacted live identity evidence, the operator may configure
`MCP_SUBJECT_LABELS_JSON`: a map from explicitly approved Entra object IDs to
distinct generic labels such as `user-a` and `user-b`. The server adds
`subject_label` only by looking up the **signature-validated** `oid`; neither a
prompt nor a tool argument controls it. IDs and names never appear in receipts.
Unconfigured subjects return `unmapped`, which must not count as proof of an
expected user. Labels do not grant permission or replace the normal JWT/scope
checks. Keep actual mappings in private deployment configuration, not this repo.

## Connection setup

**Historical creation blocker, resolved in this environment on 2026-09-11:**
with connection CLI `1.0.0-beta.6` and ARM
`2025-04-01-preview`, the native custom OAuth PUT returned
`ConnectorNamespaceCustomConnectorDirectInvokeRequiresApiDefinitionV3` (HTTP
400): ConnectorGateway's DirectInvoke mode requires a version 3.0 API
definition. The same owned connection also failed through the standard ARM
SDK using GA `2026-05-01` and preview `2026-05-15-preview`, with the same
service error. This is a connection-creation failure, not a consent, JWT or
private-MCP handshake result. The inspected CLI/schema exposes no documented
per-connection API-definition switch. Do not change a shared namespace to
ProxyInvoke, expose the MCP publicly, or invent metadata knobs. A newer
registered ARM API is not a proven fix merely because it exists. Repeating the
same GA `2026-05-01` request on September 11 succeeded without a namespace
change. This is evidence of recovery in the tested account, not a universal
rollout announcement. Use the live-proven
[GA ARM helper](references/python/provision_connection.py); CLI-only recovery
was not separately replayed after the platform fix.
Do not keep replaying an unchanged failure or rotate credentials as if that
corrected a generated API definition. Escalate with sanitized request shape,
versions, service codes and correlation IDs when supported paths agree.

Follow [the connection contract](references/connection-contract.md) before
executing any cloud command. Use custom OAuth with a dedicated resource API
and a separate OAuth client, minimal delegated permissions and exact platform
redirect URI. Preserve other redirect URIs if editing an existing registration.
The connection belongs to a Foundry project; reuse it across agents only
where supported. Consent is per user, project and connection, not globally
per portal login.

`oauth_consent_request` / MCP `CONSENT_REQUIRED` is distinct from
`mcp_approval_request`. Read-only tool approval may be `never`; this **never**
auto-approves OAuth or admin consent. Denial must not become empty data.

## Agent integration

For Prompt/Toolbox, use `build_toolbox_bridge_properties` with the **first-party
Foundry project endpoint** and versioned Toolbox, then
`build_prompt_toolbox_definition` with that bridge connection ID. Its
`UserEntraToken` audience is `https://ai.azure.com`, which is used only at the
Microsoft Toolbox boundary. The existing inner custom MCP OAuth connection
still requests the custom API audience/scope. Never point this first-party
bridge directly at the custom MCP. This native composition passed live;
the older static-bearer SDK example is not the canonical delegated recipe.

The pure builder returns a Prompt definition and an inner Toolbox MCP tool,
both referencing the same connection ID. It never puts `authorization` or
user headers into the tool configuration. `create_bindings` is a **cloud
write**, not a local test: only call it after Gate B and verify the connection
auth type separately. It reads without credentials and rejects target mismatch.

For Hosted, deploy the Responses 2.0.0 runtime and set a versioned
`TOOLBOX_ENDPOINT`. Use `FoundryToolbox` itself; do not copy its private auth
transport. The runtime credential grants platform access only, while the
platform resolves the downstream user using the trusted call context.
Constructing the wrapper locally or supplying a fabricated header is not
proof of that platform chain.

Invoke a Prompt Agent through project Responses with `agent_reference`.
Invoke Hosted through `project.get_openai_client(agent_name=hosted_name)`:
the project-level `agent_reference` route is rejected for Hosted. Pass the
normal user credential and, where needed, a supported private proxy transport;
never copy portal tokens or add invented caller headers. The API can return
HTTP success with `response.status == "failed"`: inspect `response.error` and
tool outputs, not just the HTTP status or assistant prose.
The canonical helper takes an `http_client_factory`, not a shared HTTP
client: the OpenAI client owns and closes its transport after each call.
The factory supplies a new private transport for subsequent turns/consent
continuation. Use `agent_version` to select the Prompt direct or Toolbox
version; Hosted uses its deployed endpoint routing.

Use the canonical Hosted Dockerfile's default container identity. A fixed
`USER 65532` could not create `/home/session/.sessions` on the platform mount
and caused `session_not_ready`. The independent ACA server keeps its
non-root identity. Do not replace session storage with an auth bypass.

Ownership remains: `foundry-toolbox` owns the upstream consumer and Toolbox
management; `foundry-hosted-agents` owns runtime hosting; `foundry-prompt-agents`
owns Prompt lifecycle; `foundry-mcp-aca` / `azd-patterns` own ACA and shared IaC.
This recipe owns only their delegated-auth composition.

## Local recipe

From the repository root, choose distinct paths for the three venvs. Install
each dependency set separately; never add the management SDK to Hosted:

```bash
python3 -m venv .scratch/mcp-auth-server
.scratch/mcp-auth-server/bin/pip install ./skills/foundry-mcp-auth/templates
python3 -m venv .scratch/mcp-auth-management
.scratch/mcp-auth-management/bin/pip install ./skills/foundry-mcp-auth/templates/management
python3 -m venv .scratch/mcp-auth-hosted
.scratch/mcp-auth-hosted/bin/pip install ./skills/foundry-mcp-auth/templates/hosted
```

Server: FastMCP 2.14 / MCP 1.29 / PyJWT 2.10. Management: Projects SDK 2.6.
The server azd template uses `language: docker` and native `docker.remoteBuild`
so the approved registry builds the image without a local Docker daemon.
Image builds are cloud operations and still require Gate B.
Hosted uses core 1.16 / OpenAI provider 1.14 with the catalog's hosting
`1.0.0b260730`, Foundry provider 1.10.4 and Projects SDK 2.3, respecting its
`<2.4` requirement. OpenAI provider 1.10 lacks the `_feature_usage` import
required by the Foundry provider despite satisfying its declared lower bound.
The inspected newer cohort has the same SDK upper-bound issue; upgrading
everything is not a fix. Keep jobs' FastMCP 4 / MCP 2 environment unchanged.

Run local tests with no Azure credentials or endpoints:

```bash
.scratch/mcp-auth-server/bin/python -m unittest scripts.tests.test_foundry_mcp_auth_policy scripts.tests.test_foundry_mcp_auth_contract
PYTHONPATH=skills/foundry-mcp-auth .scratch/mcp-auth-server/bin/python -m unittest discover -s skills/foundry-mcp-auth/test-fixture -p 'test_server.py'
PYTHONPATH=skills/foundry-mcp-auth .scratch/mcp-auth-management/bin/python -m unittest discover -s skills/foundry-mcp-auth/test-fixture -p 'test_management.py'
PYTHONPATH=skills/foundry-mcp-auth .scratch/mcp-auth-hosted/bin/python -m unittest discover -s skills/foundry-mcp-auth/test-fixture -p 'test_hosted.py'
```

Create the deployable Hosted project with the canonical staging helper:

```bash
python3 skills/foundry-mcp-auth/references/python/stage_hosted.py .scratch/delegated-hosted
```

Run Hosted `azd` commands from that new directory. The extension rejects
parent-directory service paths even when ordinary Container Apps accepts
them. Staging copies only the canonical Dockerfile, dependency manifest and
entrypoint; no credentials or caches. The live run used azd 1.33.0 with
`azure.ai.agents` 1.0.0-beta.14.

For manual local serving, set `MCP_TENANT_ID`, `MCP_API_CLIENT_ID` and
`MCP_BASE_URL` (HTTPS origin; loopback HTTP only for local work), then run
`python -m references.python.delegated_server` from this skill directory.
Production serving uses real Entra JWTs; test signing keys exist only in tests.
There is no auth-disable flag.

## Gate B and private deployment

Before **every** Azure shell/subprocess export both isolated CLI config dirs
from the operator's tenant index; explicitly select the approved subscription,
not its index default. Assert tenant/subscription immediately before writes
using `azure-tenant-isolation`. Never force login when the isolated session
works. No environment IDs belong in this public recipe.

Gate B must approve the resource allow-list, Entra/RBAC changes, credentials,
cost and cleanup. Check real runtime routes and DNS before deploying:
Prompt/Toolbox/Hosted -> MCP, browser -> Playground/consent, and permitted
Entra token/JWKS egress. No hidden public fallback. APIM is optional, not a
portal integration prerequisite.

The server template uses an **existing internal VNet-connected ACA
environment**, registry and pull identity in the approved resource group.
It reuses `azd-patterns/references/bicep/aca-app.bicep`; pre-grant AcrPull
and verify registry reachability. It does not create a VNet or patch the hub.
App-level external ingress on an internal ACA environment permits VNet
callers; it does not alone determine internet exposure.

After Gate B, run the server `azd up` from `templates/` and the Hosted
brownfield workflow from the directory created by `stage_hosted.py`, following
the existing hosted skill's environment contract. Keep the server template
under the skill so shared Bicep modules resolve. The placeholder image is
not the authenticated server: do not expose/advertise the app or create its
connection until `azd deploy` has replaced it and auth probes pass.
Use a short unique azd environment name (at most 20 characters).

In the live setup, account network injection and account capability host alone
did not initially yield working private tool calls. The approved addition of
the Basic **project** capability host (no BYO datastore connections), followed
by propagation, preceded successful private Prompt and Toolbox calls. See
`azd-patterns`' `foundry-project-capability-host.bicep`. Check actual project
state and obtain approval for this project-wide change; do not blindly
recreate existing hosts. The first immediate retry still failed DNS; the
subsequent no-credential control reached the MCP and was correctly rejected
with 401, then the delegated request succeeded. Use a bounded readiness
window and classify that wrapped downstream 401 as successful network
reachability, never as delegated success.

For a retained demo, no default cleanup schedule, shutdown date or resource
`expiresAt` tag is part of this recipe. Client credentials and OAuth tokens
still have technical lifetimes: use an operator-approved, tenant-accepted
long-lived client credential, managed rotation, and platform token refresh.
Do not equate retaining infrastructure with a non-expiring OAuth token.
Keep exact resource IDs, image digests, versions, consent status and safe
identity evidence in a private runbook, separate from public skill docs.

## Live acceptance and publication

The [unattended fixture](test-fixture/consumer_prompt.md) is deliberately
separate from the [interactive protocol](test-fixture/playground.md).
A workload identity passing a fixture is not delegated E2E. Missing prerequisites
or unsupported paths are explicit failures/blocks, never skipped-to-PASS.
No personal refresh tokens, copied portal tokens, browser storage scraping,
automatic browser consent, Graph data or extra web application.

Before release: complete all four original paths, first and later consent,
denial, refresh/revocation, two-user concurrency and private reachability.
Record sanitized evidence against the exact candidate SHA. Do not call this
candidate production-ready merely because local tests or pin imports pass.
Literal OBO additionally requires an explicitly approved audience-distinct
mock API and a real A->B exchange. Wave 2 web sign-in remains separate:
authorization code/PKCE, audience-correct backend tokens, supported MSAL OBO,
session/consent handling; never reuse tokens obtained from the portal.

## Sources

- [MCP authentication](https://learn.microsoft.com/azure/foundry/agents/how-to/mcp-authentication)
- [Toolbox identity boundaries](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/tool-authentication)
- [FoundryToolbox integration](https://learn.microsoft.com/agent-framework/integrations/by-component/tools/foundry-toolbox)
- [Private networking](https://learn.microsoft.com/azure/foundry/agents/how-to/virtual-networks)
- [Entra OBO](https://learn.microsoft.com/entra/identity-platform/v2-oauth2-on-behalf-of-flow)
- [Pinned source and known limitations](references/upstream-pin.md)
