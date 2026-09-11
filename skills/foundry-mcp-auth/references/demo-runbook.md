# Reproduce and operate the delegated MCP demo

Operate the Prompt/direct, Prompt/Toolbox and Hosted/Toolbox compositions
using the sequence below. Current evidence and unresolved acceptance gates
belong in the [validation notes](../../../docs/maintenance/foundry-mcp-auth-validation.md).
This is native OAuth passthrough, not a literal Entra OBO A-to-B implementation.

## What to retain

Keep the Foundry project/model, internal MCP service, private DNS/routing,
OAuth registrations/connection, Toolbox and agent versions available. **Do
not add a default environment expiry, cleanup automation or shutdown date.**
Maintain a private inventory of exact resource IDs, versions, image digests,
approved user-label mapping and credential lifecycle. Never put its real
identifiers, secret values, consent links or token caches in public docs.

OAuth access/refresh tokens and client credentials have technical lifetimes.
For a retained demo, use the tenant-permitted long client-credential validity,
one active demo secret, and a documented rotation procedure. A secret
expiration is not an instruction to delete the environment. Check credential
health before demonstrations; do not claim perpetual OAuth credentials.

## Reproduction sequence

1. **Isolate the operator:** resolve the approved alias from the tenant index,
   export both CLI config directories in every shell, explicitly target the
   approved subscription and assert tenant/subscription. Use the existing
   `AzureCliCredential(subscription=...)`; do not pass both subscription and
   tenant to that credential when its CLI rejects the combination. No cache
   copying, forced login or personal bearer-token snippets.
2. **Prepare private infrastructure:** use the `azd-patterns` modules for an
   internal Consumption ACA environment, delegated subnet, NAT, exact DNS
   zone/links, pull identity and least-privilege ACR grants. Reuse the approved
   existing project, model and registry. Validate `internal: true` and private
   resolution from the actual operator/runtime routes, not just a laptop.
   The demo uses one MCP replica. A public authenticated ACR, if required by
   the project's generation, is a separate build-plane boundary, not public MCP.
3. **Check the project network contract:** inspect account network injection
   and the project capability host. Use the canonical Basic project-host
   module (no BYO stores) only if needed
   and approved; preserve existing hosts/stores. Bound readiness checks rather
   than treating the first immediate DNS failure as permanent.
4. **Build the MCP:** use the canonical server files and Dockerfile with
   `language: docker` / `docker.remoteBuild: true` in azd. Set the tenant,
   resource API ID and MCP base URL; optionally map an approved user's object
   ID to a non-identifying `user-a` label. Keep `include_fastmcp_meta=False`.
   Publish an immutable uniquely tagged image and record its digest.
5. **Configure real OAuth:** separate resource API and confidential client;
   resource access-token version 2; delegated `demo.read`; custom scope
   `api://<api-id>/demo.read` plus `offline_access`. Use
   `build_oauth_properties` and `provision_connection` from the canonical
   GA ARM helper. Supply the secret only through approved process-memory
   custody. Register the exact returned redirect URL on the client, preserving
   other redirect entries. If `redirectUrl` is absent, read it in the portal.
6. **Create Prompt and Toolbox:** read the connection without credentials,
   verify OAuth2 and matching target, and use `configure_foundry.py`.
   Do not mix an agent `MCPTool` with `MCPToolboxTool`. Keep both tool names
   explicitly allowed. Tool approval `never` does not grant OAuth consent.
   For the Prompt/Toolbox variant, create the native first-party
   `UserEntraToken` bridge with audience `https://ai.azure.com`, targeting
   the versioned Toolbox only. Reuse the same inner custom OAuth connection.
   Use the canonical bridge builders, not a static `authorization` bearer.
7. **Stage and deploy Hosted:** run `stage_hosted.py` into a new directory.
   The Hosted service path must remain inside that directory. Use the
   canonical Dockerfile with its default container identity, Responses 2.0.0,
   `FoundryToolbox` and a versioned `TOOLBOX_ENDPOINT`. Management SDK 2.6 and
   Hosted SDK 2.3 live in separate environments. No custom token transport
   or duplicated Toolbox wrapper.
8. **Invoke as the user:** use `invoke_agent.py`. Prompt uses project
   Responses with `agent_reference`; Hosted uses the agent-bound OpenAI
   client. With private endpoints use a supported proxy transport with remote
   DNS, including the OpenAI HTTP client. Supply a fresh client from
   `http_client_factory` on each invocation, including consent continuation:
   OpenAI closes each supplied transport at exit. Prove a disabled proxy fails
   instead of silently falling back. The runtime's own Toolbox credential
   remains an application identity, while validated downstream MCP identity
   must be the consenting user.
9. **Consent interactively:** open each fresh consent link once and let the
   user complete it. Resume with `previous_response_id`. An Entra permission
   grant alone does not prove Foundry completed the callback. If a one-time
   link ends in `Code ... not found`, obtain a fresh request; do not automate
   approval or keep refreshing the failed page.
10. **Assert tool-level evidence:** both tools must execute. Check
    `response.status`, actual tool outputs, `subject_label`, `auth_kind`,
    audience, scopes and item ownership. Match each receipt correlation to
    server audit. Assistant text alone, HTTP 200 alone, health, discovery and
    a consent response are not E2E success.

## Before a demonstration

Verify the MCP/agent versions and configuration, credential validity, private
operator route, and the actual user's consent. A quick run asks both agents:
**“Call who_am_i and list_my_demo_items; show the safe server receipts.”**
Both must return the same approved user label and dataset. Hosted transport
may prefix tool names with the source label; do not hardcode a different
separator into the model prompt.

Do not rebuild just to repeat the demo. Record actual ACR runs when a rebuild
is necessary: a CLI image-override option is not proof no build occurred.
Refresh Toolbox/agent versions when schemas change, and preserve the canonical
source hashes used for each image.

The operator performs Playground follow-through with the same account.
Identify a second real test user explicitly before testing isolation;
never fabricate a second user or replace them with an application identity.
Test denial, late consent, revocation and expiry separately without disrupting
the retained working demo or falsely classifying a missing user as PASS.

Keep experimental native Hosted/direct out of the validated demo path until
its acceptance gates pass; do not silently route it through Toolbox and report
that as direct-MCP success.
