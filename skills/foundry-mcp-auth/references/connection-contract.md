# Custom OAuth connection contract

Candidate; evidence and remaining acceptance gates are recorded only in the
[validation notes](../../../docs/maintenance/foundry-mcp-auth-validation.md).
**Every action that writes Azure/Entra requires Gate B.**
The tested server accepts Entra v2 tokens for its own API, not Microsoft tokens.

## Prerequisites and setup order

1. Approve the dedicated resource API and separate OAuth client registrations.
   Restrict them to the Foundry project's tenant. Configure the resource API
   with `api.requestedAccessTokenVersion: 2` and expose `demo.read` under
   `api.oauth2PermissionScopes` with the appropriate consent
   policy. The client requests this delegated permission, not an application
   role and not Graph permissions.
2. Confirm the user has project access: Foundry User for building/editing in
   Playground; Foundry Agent Consumer for consumption where sufficient.
   Grant the runtime identity only the platform access it requires.
3. Prepare the [canonical definition](yaml/connection.yaml). Choose a unique,
   approved connection name; its `name` is a literal, not environment expansion.
   Confirm existing-name ownership because **deploy is replacement/upsert**.
4. Inject `MCP_OAUTH_CLIENT_SECRET` via the approved secret channel into the
   process environment. Do not place it in a shell transcript, argv, azd env
   file, repository, response or log. Do not use `--show-credentials`, shell
   tracing or debug HTTP logs. Clear the temporary process environment after
   use; environment references avoid argv but are not a substitute for secret
   custody.
5. After isolated tenant/subscription preflight, use
   [provision_connection.py](python/provision_connection.py) with the standard
   ARM `ResourceManagementClient`, API **2026-05-01**, and the exact approved
   project-connection resource ID. Build properties with
   `build_oauth_properties`; `provision_connection(..., approved=True)` refuses
   implicit overwrite and returns only non-secret readback fields.
   Replacement additionally requires `replace_existing=True`, verified
   ownership/client configuration and the same target/auth type.
   The YAML remains the schema reference for the alternative
   `azure.ai.connections` **1.0.0-beta.6** `azd ai connection deploy` path;
   do not infer equivalent live validation for that alternative.
6. Read the connection without credentials and inspect its configured
   `OAuth2` type, target and scopes. Obtain the **exact redirect URI from the
   Foundry portal's custom OAuth configuration** and register it on the OAuth
   client's web redirect list, preserving other entries. Do not guess hosts,
   hardcode a connector GUID, or substitute the per-user `consent_link`.
7. Recheck the configuration, then use the returned connection ID in the
   canonical SDK builders. Keep target and `server_url` equal: Foundry may
   prefer the connection target if they differ.

GA readback may provide `properties.redirectUrl`. Because it is not guaranteed
by the published schema, the helper returns `None` when absent: obtain it from the portal
instead of inventing a URL. The pinned CLI create response returns name/project/
state, not a callback. Never confuse the redirect URI with a per-user consent link.

## API shapes

`azure.ai.connections` beta.6 deploy accepts the YAML fields in the linked
file and expands `${VAR}` in URLs, scopes and credential values. Credentials
use **`clientId`**, not `clientID`. The wire body places OAuth fields directly
inside `properties`, not inside `metadata`; `scopes` is an array.

Do not add `audience` to this OAuth2 definition: that CLI flag belongs to
identity auth modes. Request `api://<api-id>/demo.read`; validate JWT `aud`
against the API application ID and JWT `scp` against `demo.read`.
Use `offline_access` for refresh. Portal/OAuth scope entry is space-separated;
the canonical file uses separate array elements to avoid CLI parser ambiguity.

`project.connections.get(name, include_credentials=False)` is read-only;
there is no SDK connection create/update in the selected management contract.
Do not mix the CLI definition schema with an ARM body or invent a
`project.connections.create` method. A successful connection write is not a
successful tool invocation.

## User lifecycle

First call: render the platform-provided `oauth_consent_request.consent_link`
or MCP `CONSENT_REQUIRED` URL to the user. They inspect and complete or decline
consent themselves. Resume the supported Responses flow with the prior
response ID. Tool approval (`mcp_approval_request`) is a separate step.

An Entra permission grant alone does not prove Foundry token storage. If a
one-time callback reports `Code ... not found`, do not keep reopening the
same link. Obtain a fresh consent request when needed and let the user
complete it; never automate approval.

Reuse credentials only within the platform's per-user/project/connection
boundary. A new connection may require new consent. Denial returns an
authorization-needed/denied result, not empty business data. Valid refresh
credentials allow renewal; revoked/expired refresh credentials require
reauthorization. Existing access tokens may remain valid until their expiry.
The pinned Hosted wrapper's late-consent gap is **not solved** by these
instructions; keep the corresponding Playground case blocked until proven.

## Failure evidence

Do not mint another client secret simply to retry an unexplained error.
Establish a supported retry path first. A value supplied only through process
memory is unrecoverable after that process exits if the connection write
failed. Revocation/replacement then needs explicit authorization and must not
overlap active demo credentials. For retained demos, replace test-length
credentials with tenant-accepted long validity under the operator's retention
policy; document the technical expiry and renewal without scheduling resource
deletion. Check for brief Entra propagation before treating a freshly created
key's immediate authentication failure as a permanent configuration error.

Record phase (`connection-create`, `connection-read`, `consent`, `invoke`,
`refresh` or `network`), sanitized status/code, version and correlation
receipt. Never store the consent URL query, JWT or client secret. Distinguish
schema 400, credential 401, scope/permission 403, consent-required and DNS/
routing failures before proposing a fix. Do not invent a customer root cause.

Source: [released connection deploy](https://github.com/Azure/azure-dev/blob/azd-ext-azure-ai-connections_1.0.0-beta.6/cli/azd/extensions/azure.ai.connections/internal/cmd/connection_deploy.go),
[released wire fields](https://github.com/Azure/azure-dev/blob/azd-ext-azure-ai-connections_1.0.0-beta.6/cli/azd/extensions/azure.ai.connections/internal/cmd/raw_connection.go).
