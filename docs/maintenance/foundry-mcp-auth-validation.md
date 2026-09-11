# Foundry MCP auth candidate acceptance

**UNRELEASED - THREE LIVE DELEGATED PATHS VERIFIED.** Proposed skill 1.0.0 /
catalog 4.32.0. Not a four-path or multi-user release certification.
This record is not approval to deploy or publish. No real environment identifiers,
tokens, consent links, secrets or user data are stored here.

## Limited live evidence

### September 11: successful user-delegated execution

The same GA `2026-05-01` connection request succeeded. Callback registration,
Prompt agent and Toolbox creation completed; the user completed a fresh OAuth
consent link. Both **Prompt -> direct MCP** and **Hosted -> Toolbox -> MCP**
then executed `who_am_i` and `list_my_demo_items` with the real user over
private networking. Actual tool outputs—not assistant claims—contained the
custom API audience, `demo.read`, `auth_kind: delegated`, `subject_label:
user-a` and server-selected synthetic items. Four receipt correlations from
the final two-path run matched MCP server audit.

The successful sequence required an approved Basic project capability host
with platform-managed backing stores, propagation, the correct agent-bound
Hosted endpoint, a writable Hosted session home, standard-only FastMCP
metadata and a refreshed Toolbox/Hosted binding. The project host was added,
not recreated; no public MCP fallback or service identity substitution was used.

After the user requested permanent demo retention, resource expiry tags and
automatic cleanup were removed. The temporary client credential was replaced
with tenant-accepted long validity, without overlapping active keys. Both
delegated paths passed again after rotation. Access-token expiry/refresh and
late-consent revocation remain independent unproven cases.

The canonical reproduction procedure is
[demo-runbook.md](../../skills/foundry-mcp-auth/references/demo-runbook.md).
Exact IDs, digests, response IDs, safe receipts and server correlations are
stored privately with the working-tree source hashes. A draft checkpoint PR
was subsequently authorized; publication as a fully accepted skill remains
separate. Management uses the canonical GA ARM helper.

Prompt/Toolbox also passed using a native `UserEntraToken` connection to the
first-party Toolbox (audience `https://ai.azure.com`) and the same inner
custom OAuth2 MCP connection. No static bearer was stored in the agent.
The separately deployed native Hosted/direct variant returned HTTP success
with completed/empty output and no tool receipts: it does not pass E2E.
Its logs confirm the call was made; no conclusion of universal platform
non-support is drawn from this particular pinned stack.

### September 10: historical platform failure

An explicitly approved bounded cycle on 2026-09-10 provisioned an internal
MCP environment, private DNS, narrow image-pull roles and the two dedicated
Entra registrations. Two native azd remote server builds succeeded. Private
DNS/TLS, health/PRM 200 and anonymous initialize 401 were observed. SDK and
azd management reads used the private tunnel; none of these prove delegated
end-user calls.

Native custom OAuth connection creation failed with HTTP 400 / UserError /
`ConnectorNamespaceCustomConnectorDirectInvokeRequiresApiDefinitionV3`.
ConnectorGateway requires OpenAPI 3.0 for DirectInvoke. No connection was
present on readback; no Prompt/Hosted agent invocation or OAuth consent was
performed. No shared namespace mode, public MCP fallback or extra grant was
used. Sanitized request shape and correlation evidence remain private.

The failure reproduced through azd/connection CLI on ARM
`2025-04-01-preview`, and the standard ARM SDK on GA `2026-05-01` and newest
registered preview `2026-05-15-preview`. The same
`ConnectorNamespaceCustomConnectorDirectInvokeRequiresApiDefinitionV3` code
was returned each time. No documented per-connection definition selector was
established. Unused run-created credentials were revoked after diagnosis;
zero active demo client secrets remained. This is an actionable service
escalation, not evidence that the original customer incident had this cause.

The operator subsequently authorized initial backend tests with their existing
isolated Azure CLI user credentials, with Playground verification later.
That ordering change does not waive downstream OAuth consent or any final
acceptance row. Credential rotation is not a fix for this service error.

## Local evidence boundary

Local working-tree execution on 2026-09-10 and 2026-09-11 (not CI or a release attestation):

| Local check | Result |
|---|---|
| New candidate suites | 39 passed: policy, HTTP/MCP, provisioning/routing, Hosted staging, metadata, real transport lifetime and lifecycle-boundary regressions |
| Private network module contracts | 2 passed; the bounded composition was also provisioned live |
| Related existing suites | 71 passed; combined focused run 112 passed including the two private-network module tests |
| Exact new pin validation script | Passed all three import markers and dependency checks in separate environments |
| Real local server process | Health/PRM returned 200; anonymous MCP initialize returned 401; process stopped afterward |
| Templates/catalog | Bicep compiled locally; both azd manifests matched the official schema; catalog lint and site link checks passed |
| Container images | MCP and Hosted images built through native azd; actual ACR runs and immutable digests recorded privately |

Tests exercised synthetic concurrent users, not interactive Entra users.
Upstream Authlib deprecation notices remain in the old server cohort.

The candidate has local signed-token policy tests, in-process HTTP/MCP
handshake and concurrent identity tests, SDK serialization/write-opt-in tests,
and released-wrapper import/header-context tests in separate environments.
Signing keys and principals in the tests are synthetic. Wrapper context is
simulated, not a trusted Foundry request. Local imports cannot prove the
credential chain, endpoint reachability, consent or real platform delegation.

The final canonical invocation helper was subsequently run against all three
working live paths, not only mocked: their six tool-result receipts matched
server audit. An independent review found that a shared caller-supplied HTTP
client was closed after one turn. The helper now takes a fresh transport
factory, with a real OpenAI/httpx two-turn continuation regression and a
completed/empty-output guard.

The server uses FastMCP 2.14 / MCP 1.29 / PyJWT 2.10. Management uses Projects
SDK 2.6 separately. Hosted uses core 1.16, OpenAI provider 1.14, Foundry provider
1.10.4, hosting 1.0.0b260730 and Projects 2.3; its import constraints are not
overridden. No package changes are imposed on existing jobs.

## Final acceptance remains unchanged

| Path / behavior | Current status |
|---|---|
| Prompt -> direct custom MCP | LIVE PASS, one real user via API; actual tool receipts matched server audit |
| Hosted -> Toolbox -> custom MCP | LIVE PASS, one real user via API; actual tool receipts matched server audit |
| Prompt -> Toolbox -> custom MCP | LIVE PASS using the native first-party user-token bridge and inner custom OAuth |
| Hosted -> direct custom MCP | Native variant deployed and invoked, but completed with empty output; NOT DEMONSTRATED |
| First user consent | User completed fresh consent successfully; denial and Playground follow-through NOT DEMONSTRATED |
| Late consent / revoked or expired refresh credentials on a shared host | NOT DEMONSTRATED; known host conversion limitation |
| Two independent Entra users, concurrent calls | NOT DEMONSTRATED; synthetic local isolation is a separate result |
| Private runtime paths and consent/Entra egress | Exercised by the three passing delegated API paths; other endpoint combinations remain unproven |
| Literal Entra OBO A->B exchange | NOT IMPLEMENTED; separate optional approved delta |

The live stage was explicitly authorized, including the later project-host
remediation and permanent environment retention. This public record does not
grant permission to modify another environment. CI's unattended reachability
fixture remains distinct from user-delegated evidence. A missing prerequisite
must not be skipped or reported as PASS.

After approved execution, add sanitized evidence linked to the exact candidate
SHA and the [interactive protocol](../../skills/foundry-mcp-auth/test-fixture/playground.md).
Do not substitute a service principal, copied portal token, static bearer
bridge or restarted-per-user host for the final acceptance criteria.

## Checkpoint and CI boundary

This draft is a reviewable checkpoint for the three demonstrated paths, not
permission to merge with the remaining acceptance rows unchecked. Live evidence
was collected manually against the exact canonical source files and mapped to
the candidate in the PR; CI execution is reported separately, never inferred
from the manual result.

The new unattended fixture requires an approved private-reachable endpoint and
`MCP_AUTH_NETWORK_SMOKE_APPROVED=yes`. These inputs are not yet provisioned in
the shared runner configuration; without them, it deliberately fails rather
than inventing a public fallback or declaring delegated success. Its future
PASS would prove only PRM/reachability/anonymous rejection, not interactive
OAuth. The credential-free local job covers three isolated dependency sets.
No required checks or live-testing policy are waived by draft status.

## Hosted/direct triage at the checkpoint

**Unresolved, not classified as impossible.** Bounded public issue/release
research identified a known defect in the pinned hosting package, but did not
establish it as the cause of this live direct-MCP failure.

| Evidence | What it establishes | What it does not establish |
|---|---|---|
| [microsoft/agent-framework#7658](https://github.com/microsoft/agent-framework/issues/7658) and [microsoft/agent-framework#7725](https://github.com/microsoft/agent-framework/issues/7725), both closed | Reports using hosting `1.0.0b260730` describe mid-run `oauth_consent_request` content being dropped, yielding completed/empty output. | Those reproductions observed the nested consent content; the direct-MCP demo's logs do not show its nested response items. |
| [Pinned hosting output converter](https://github.com/microsoft/agent-framework/blob/python-1.13.0/python/packages/foundry_hosting/agent_framework_foundry_hosting/_responses.py#L1966-L2083) | The release source associated with the pin has no OAuth-consent output branch. | Release-source inspection alone is not a byte-for-byte reproduction inside the deployed container. |
| [Later output converter](https://github.com/microsoft/agent-framework/blob/python-1.17.0/python/packages/foundry_hosting/agent_framework_foundry_hosting/_responses.py#L1375-L1403) | A newer implementation emits OAuth consent output explicitly. | It does not prove that upgrading fixes the direct route's outer-user identity propagation. |
| [Azure/azure-sdk-for-python#46696](https://github.com/Azure/azure-sdk-for-python/issues/46696), open when checked | Closely matching native `FoundryChatClient.get_mcp_tool()` architecture fails when Hosted while working locally with a user credential; the reporter confirms the Toolbox path works. | Its reported symptom is an explicit ARA OBO BadRequest, not this demo's nested HTTP 200 and empty outer output. |

No exact public issue matching the entire observed direct-path signature was
found. A swallowed consent request is a plausible explanation **only if**
the nested response contained consent content. Successful Prompt and Hosted
Toolbox controls with the same user/connection/server narrow the investigation
without proving that premise.

The next product-group evidence should include the exact pinned versions and
image digest, request timestamp/correlation, inbound context-presence flags,
nested response/SSE **item types/status/errors**, host dispatch warnings, and
the successful controls. Exclude tokens, consent URLs and private inventory
from public reports. Ask which caller-context contract is supported for
Hosted/direct and whether the nested service returned consent content.
No new ticket, speculative adapter or dependency upgrade is part of this
checkpoint.
